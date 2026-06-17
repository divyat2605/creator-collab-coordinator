"""
Campaign Coordinator — Orchestrates Advisor + Match Agents

Manages the end-to-end flow:
1. Advisor Agent analyzes creator profile
2. Findings are written to the Collaboration Ledger (shared memory)
3. Match Agent reads the ledger and adapts its brand guideline search
4. Final matching determination is produced

All events are streamed via SSE for real-time UI updates.
"""

import json
import re
from typing import Any, Dict

from openai import AsyncOpenAI
from models.schemas import AgentSource, Severity, CreatorProfile, MatchResult
from memory.ledger import CollaborationLedger
from agents.clinical_agent import ClinicalAgent
from agents.policy_agent import PolicyAgent


FINAL_DETERMINATION_SYSTEM_PROMPT = (
    "You are the final decision engine for a medical prior authorization system. "
    "Provide clear, well-reasoned determinations in valid JSON format only."
)


class CampaignCoordinator:
    def __init__(self, api_key: str):
        # Initializing OpenAI client (AsyncOpenAI defaults to api.openai.com)
        self.client = AsyncOpenAI(
            api_key=api_key,
        )
        self.ledger = CollaborationLedger()
        self.clinical_agent = ClinicalAgent(self.client, self.ledger)
        self.policy_agent = PolicyAgent(self.client, self.ledger)
        self.model = "gpt-4o-mini"

    async def process_claim(
        self, ehr: CreatorProfile, policy_text: str, plan_name: str = "Brand Guidelines"
    ) -> dict:
        """
        Process a creator-brand match end-to-end. Returns the complete result.
        Subscribe to self.ledger for real-time events.
        """
        # Clear previous state
        await self.ledger.clear()

        # System start
        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PROCESS_START",
            message=(
                f"Campaign Coordinator initiated for creator {ehr.creator_name}. "
                f"Starting dual-agent analysis."
            ),
            tags=["SYSTEM", "START"],
        )

        # Phase 1: Advisor Agent
        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message="Phase 1: Advisor Agent — Analyzing creator profile",
            data={"phase": "advisor"},
            tags=["PHASE", "ADVISOR"],
        )

        clinical_result = await self.clinical_agent.analyze_ehr(ehr)
        if not isinstance(clinical_result, dict):
            clinical_result = {
                "error": "Advisor agent returned malformed result",
                "necessity_assessment": {
                    "necessity_level": "RECOMMENDED",
                    "justification": "Advisor output unavailable; manual review recommended.",
                },
            }

        # Phase 2: Match Agent (reads ledger from Phase 1)
        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message=(
                "Phase 2: Match Agent — Searching guidelines with advisor context "
                "from shared ledger"
            ),
            data={"phase": "match"},
            tags=["PHASE", "MATCH"],
        )

        policy_result = await self.policy_agent.analyze_policy(policy_text, plan_name)
        if not isinstance(policy_result, dict):
            policy_result = {
                "error": "Match agent returned malformed result",
                "auth_pathway": {
                    "recommended_pathway": "Pending Manual Review",
                    "expected_status": "PENDING_REVIEW",
                    "confidence_score": 0.0,
                },
            }

        # Phase 3: Final determination
        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message="Phase 3: Generating final match determination",
            data={"phase": "resolution"},
            tags=["PHASE", "RESOLUTION"],
        )

        final_determination = await self._generate_final_determination(
            ehr, clinical_result, policy_result
        )

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PROCESS_COMPLETE",
            message=(
                f"Processing complete. Status: {final_determination.get('status', 'UNKNOWN')}. "
                f"Pathway: {final_determination.get('pathway', 'N/A')}."
            ),
            data=final_determination,
            tags=["SYSTEM", "COMPLETE", final_determination.get("status", "UNKNOWN")],
            severity=Severity.CRITICAL,
        )

        return {
            "clinical_analysis": clinical_result,
            "policy_analysis": policy_result,
            "determination": final_determination,
            "ledger": [e.model_dump() for e in await self.ledger.read_all()],
        }

    def _safe_json_parse(self, text: Any) -> dict:
        """
        Robust JSON parsing for model output.

        Handles:
        - None responses
        - markdown code fences
        - extra prose around JSON
        - trailing commas
        - smart quotes
        - Python literals (True/False/None)
        - common delimiter issues in long outputs
        """
        if text is None:
            return {"error": "Empty response from model", "raw_text": None}

        if not isinstance(text, (str, bytes, bytearray)):
            return {
                "error": f"Unexpected response type: {type(text).__name__}",
                "raw_text": str(text),
            }

        if isinstance(text, (bytes, bytearray)):
            text = text.decode("utf-8", errors="ignore")

        if not text.strip():
            return {"error": "Empty response from model", "raw_text": text}

        cleaned = text.strip()

        # Strip markdown fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Extract the largest JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        repaired = cleaned
        repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'")
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)

        # Remove trailing commas
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

        # Mild last-mile delimiter repairs
        repaired = re.sub(r'(\})(\s*)(\{)', r'\1,\2\3', repaired)
        repaired = re.sub(r'(\])(\s*)(\{)', r'\1,\2\3', repaired)
        repaired = re.sub(r'(\})(\s*)(")', r'\1,\2\3', repaired)
        repaired = re.sub(r'(\])(\s*)(")', r'\1,\2\3', repaired)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            return {
                "error": "Failed to parse JSON from model output",
                "parse_error": str(e),
                "raw_text": text,
            }

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _serialize_for_prompt(self, value: Any) -> Any:
        """
        Convert arbitrary objects into JSON-serializable prompt-safe structures.
        """
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, list):
            return [self._serialize_for_prompt(v) for v in value]

        if isinstance(value, dict):
            return {k: self._serialize_for_prompt(v) for k, v in value.items()}

        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass

        if hasattr(value, "dict"):
            try:
                return value.dict()
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            return {
                k: self._serialize_for_prompt(v)
                for k, v in value.__dict__.items()
                if not k.startswith("_")
            }

        return str(value)

    def _default_final_determination(
        self,
        ehr: CreatorProfile,
        clinical_result: dict,
        policy_result: dict,
        reason: str = "Final determination could not be fully synthesized automatically.",
    ) -> dict:
        """
        Human-in-the-loop fallback so the coordinator never hard crashes.
        """
        auth_pathway = policy_result.get("auth_pathway", {}) if isinstance(policy_result, dict) else {}
        necessity = (
            clinical_result.get("necessity_assessment", {})
            if isinstance(clinical_result, dict)
            else {}
        )

        deliverable_name = (
            ehr.proposed_deliverables.name
            if getattr(ehr, "proposed_deliverables", None)
            else "proposed collaboration"
        )

        missing_items = []
        try:
            documentation = auth_pathway.get("documentation_checklist", [])
            if isinstance(documentation, list):
                for item in documentation:
                    if isinstance(item, dict) and item.get("status") == "NEEDED":
                        missing_items.append(item.get("item", "Missing documentation"))
        except Exception:
            pass

        return {
            "status": "PENDING_REVIEW",
            "pathway": auth_pathway.get("recommended_pathway", "Pending Manual Review"),
            "determination_text": (
                f"The collaboration with {deliverable_name} requires manual review. "
                f"Advisor review indicates {necessity.get('necessity_level', 'unknown fit')} "
                f"and brand review identified a provisional pathway of "
                f"{auth_pathway.get('recommended_pathway', 'Pending Manual Review')}. "
                f"Final automated synthesis was not available, so the case has been routed for human evaluation."
            ),
            "reasoning": reason,
            "confidence_score": 0.25,
            "collaboration_timeline": auth_pathway.get(
                "estimated_processing_time", "1-2 business days"
            ),
            "expected_reach": auth_pathway.get(
                "admin_cost_savings_estimate", "Deferred pending manual review"
            ),
            "documentation_complete": len(missing_items) == 0,
            "missing_items": missing_items,
            "appeal_guidance": (
                "If the collaboration is not finalized, submit the full creator profile, "
                "engagement metrics, prior collaboration history, and any brand requirement exception criteria."
            ),
        }

    async def _call_json_model(self, prompt: str, fallback: dict, max_tokens: int = 1500) -> dict:
        """
        Safe model-call wrapper used by the final determination phase.
        Prevents NoneType crashes and always returns a dict.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": FINAL_DETERMINATION_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
            )
        except Exception as e:
            result = dict(fallback)
            result["reasoning"] = f"{result.get('reasoning', '')} Model call failed: {e}".strip()
            result["error"] = f"Model call failed: {e}"
            return result

        result_text = ""
        try:
            result_text = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            result_text = ""

        parsed = self._safe_json_parse(result_text)

        if not isinstance(parsed, dict):
            result = dict(fallback)
            result["error"] = "Parsed output was not a JSON object"
            result["raw_text"] = result_text
            return result

        if parsed.get("error"):
            result = dict(fallback)
            result["error"] = parsed.get("error")
            result["raw_text"] = parsed.get("raw_text")
            if parsed.get("parse_error"):
                result["parse_error"] = parsed.get("parse_error")
            return result

        return parsed

    async def _generate_final_determination(
        self, ehr: CreatorProfile, clinical_result: dict, policy_result: dict
    ) -> dict:
        """
        Generate the final, unified match determination.

        Battle-hardened against:
        - None model responses
        - malformed JSON
        - markdown-wrapped JSON
        - partial upstream failures
        """
        try:
            ledger_context = await self.ledger.get_full_context()
        except Exception:
            ledger_context = {}

        auth_pathway = policy_result.get("auth_pathway", {}) if isinstance(policy_result, dict) else {}
        necessity_assessment = (
            clinical_result.get("necessity_assessment", {})
            if isinstance(clinical_result, dict)
            else {}
        )

        deliverable_name = (
            ehr.proposed_deliverables.name
            if getattr(ehr, "proposed_deliverables", None)
            else "N/A"
        )
        deliverable_id = (
            ehr.proposed_deliverables.deliverable_id
            if getattr(ehr, "proposed_deliverables", None)
            else "N/A"
        )

        prompt = f"""You are generating the FINAL collaboration match determination.
This determination synthesizes findings from both an Advisor Agent and a Match Agent.

FULL LEDGER CONTEXT (all agent communications):
{json.dumps(self._serialize_for_prompt(ledger_context), indent=2, ensure_ascii=False)}

ADVISOR ANALYSIS SUMMARY:
- Fit Level: {necessity_assessment.get('necessity_level', 'UNKNOWN')}
- Justification: {necessity_assessment.get('justification', 'N/A')}

BRAND MATCH SUMMARY:
- Recommended Pathway: {auth_pathway.get('recommended_pathway', 'N/A')}
- Expected Status: {auth_pathway.get('expected_status', 'UNKNOWN')}
- Confidence: {auth_pathway.get('confidence_score', 0)}

CREATOR: {ehr.creator_name}
DELIVERABLE: {deliverable_name} ({deliverable_id})

Generate the final match determination. Respond with JSON:
{{
    "status": "MATCHED | DECLINED | PENDING_REVIEW",
    "pathway": "string - the collaboration pathway used",
    "determination_text": "string - 3-4 sentence formal determination that cites specific brand requirements and creator metrics",
    "reasoning": "string - detailed reasoning",
    "confidence_score": 0.0,
    "collaboration_timeline": "string",
    "expected_reach": "string",
    "documentation_complete": true,
    "missing_items": ["list of any missing information"],
    "appeal_guidance": "string - if declined, what to do"
}}"""

        fallback = self._default_match_determination(
            ehr=ehr,
            clinical_result=clinical_result,
            policy_result=policy_result,
            reason=(
                "Final determination model output was unavailable or malformed. "
                "Case routed to manual review."
            ),
        )

        result = await self._call_json_model(prompt, fallback, max_tokens=1500)

        # Normalize output shape
        result.setdefault("status", "PENDING_REVIEW")
        result.setdefault(
            "pathway",
            auth_pathway.get("recommended_pathway", "Pending Manual Review"),
        )
        result.setdefault(
            "determination_text",
            fallback["determination_text"],
        )
        result.setdefault(
            "reasoning",
            "Final determination required manual review.",
        )
        result.setdefault("confidence_score", 0.0)
        result.setdefault(
            "collaboration_timeline",
            auth_pathway.get("estimated_processing_time", "Unknown"),
        )
        result.setdefault(
            "expected_reach",
            auth_pathway.get("admin_cost_savings_estimate", "Unknown"),
        )
        result.setdefault("documentation_complete", False)
        result.setdefault("missing_items", [])
        result.setdefault(
            "appeal_guidance",
            "If declined, submit additional creator metrics and brand requirement justification.",
        )

        if not isinstance(result.get("missing_items"), list):
            result["missing_items"] = []

        if not isinstance(result.get("documentation_complete"), bool):
            result["documentation_complete"] = bool(result["missing_items"] == [])

        result["confidence_score"] = self._safe_float(result.get("confidence_score", 0.0), 0.0)

        allowed_statuses = {"APPROVED", "DENIED", "PENDING_REVIEW"}
        if result.get("status") not in allowed_statuses:
            result["status"] = "PENDING_REVIEW"

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="FINAL_DETERMINATION",
            message=(
                f"Final determination generated. "
                f"Status: {result.get('status', 'PENDING_REVIEW')}. "
                f"Confidence: {result.get('confidence_score', 0.0):.0%}."
            ),
            data=result,
            tags=["RESOLUTION", "FINAL_DETERMINATION", result.get("status", "PENDING_REVIEW")],
            severity=(
                Severity.CRITICAL
                if result.get("status") in {"APPROVED", "DENIED"}
                else Severity.HIGH
            ),
        )

        return result