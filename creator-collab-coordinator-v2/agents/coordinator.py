"""
Campaign Coordinator - orchestrates Advisor + Match agents.

Phases run strictly in sequence (Advisor -> Match -> Final Determination)
because each phase's prompt depends on the previous phase's output written to
the Collaboration Ledger — running them in parallel would defeat the whole
point of agents sharing memory. Within each phase, independent sub-steps are
parallelized instead (see advisor_agent.py and match_agent.py).
"""

from openai import AsyncOpenAI
from models.schemas import AgentSource, Severity, CreatorProfile
from memory.ledger import CollaborationLedger
from agents.advisor_agent import AdvisorAgent
from agents.match_agent import MatchAgent
from agents.llm_utils import call_json_model


FINAL_DETERMINATION_SYSTEM_PROMPT = (
    "You are the final decision engine for a brand-creator collaboration system. "
    "Return valid JSON only."
)


class CampaignCoordinator:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.ledger = CollaborationLedger()
        self.advisor_agent = AdvisorAgent(self.client, self.ledger)
        self.match_agent = MatchAgent(self.client, self.ledger)
        self.model = "gpt-4o-mini"

    async def process_collaboration(
        self,
        creator_profile: CreatorProfile,
        guidelines_text: str,
        brand_name: str = "Brand Guidelines",
    ) -> dict:
        await self.ledger.clear()

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PROCESS_START",
            message=f"Campaign Coordinator initiated for {creator_profile.creator_name}.",
            tags=["SYSTEM", "START"],
        )
        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message="Phase 1: Advisor Agent - analyzing creator profile",
            data={"phase": "advisor"},
            tags=["PHASE", "ADVISOR"],
        )

        advisor_result = await self.advisor_agent.analyze_creator_profile(creator_profile)
        if not isinstance(advisor_result, dict):
            advisor_result = {
                "error": "Advisor agent returned malformed result",
                "necessity_assessment": {
                    "necessity_level": "RECOMMENDED",
                    "justification": "Advisor output unavailable; manual review recommended.",
                },
            }

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message="Phase 2: Match Agent - evaluating brand guidelines with ledger context",
            data={"phase": "match"},
            tags=["PHASE", "MATCH"],
        )

        match_result = await self.match_agent.analyze_guidelines(guidelines_text, brand_name)
        if not isinstance(match_result, dict):
            match_result = {
                "error": "Match agent returned malformed result",
                "match_pathway": {
                    "recommended_pathway": "Pending Human Review",
                    "status": "PENDING_REVIEW",
                    "confidence_score": 0.0,
                },
            }

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="PHASE_CHANGE",
            message="Phase 3: Generating final match determination",
            data={"phase": "resolution"},
            tags=["PHASE", "RESOLUTION"],
        )

        final_determination = await self._generate_final_determination(
            creator_profile=creator_profile,
            advisor_result=advisor_result,
            match_result=match_result,
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
            "advisor_analysis": advisor_result,
            "match_analysis": match_result,
            "determination": final_determination,
            "ledger": [e.model_dump() for e in await self.ledger.read_all()],
        }

    async def _call_json_model(self, prompt: str, fallback: dict, max_tokens: int = 1500) -> dict:
        return await call_json_model(
            client=self.client,
            model=self.model,
            system_prompt=FINAL_DETERMINATION_SYSTEM_PROMPT,
            user_prompt=prompt,
            fallback=fallback,
            max_tokens=max_tokens,
        )

    def _default_final_determination(
        self, creator_profile: CreatorProfile, advisor_result: dict, match_result: dict, reason: str
    ) -> dict:
        match_pathway = (
            match_result.get("match_pathway", {}) if isinstance(match_result, dict) else {}
        )
        necessity = (
            advisor_result.get("necessity_assessment", {})
            if isinstance(advisor_result, dict)
            else {}
        )
        deliverable_name = (
            creator_profile.proposed_deliverables.name
            if getattr(creator_profile, "proposed_deliverables", None)
            else "proposed collaboration"
        )
        return {
            "status": "PENDING_REVIEW",
            "pathway": match_pathway.get("recommended_pathway", "Pending Human Review"),
            "determination_text": (
                f"The collaboration for {deliverable_name} requires manual review. "
                f"Advisor fit level is {necessity.get('necessity_level', 'unknown')}."
            ),
            "reasoning": reason,
            "confidence_score": 0.25,
            "collaboration_timeline": match_pathway.get("estimated_timeline", "1-2 business days"),
            "expected_reach": match_pathway.get("expected_reach", "Deferred pending manual review"),
            "documentation_complete": False,
            "missing_items": [],
            "appeal_guidance": "Provide additional creator evidence and guideline justification.",
        }

    async def _generate_final_determination(
        self, creator_profile: CreatorProfile, advisor_result: dict, match_result: dict
    ) -> dict:
        match_pathway = (
            match_result.get("match_pathway", {}) if isinstance(match_result, dict) else {}
        )
        necessity = (
            advisor_result.get("necessity_assessment", {})
            if isinstance(advisor_result, dict)
            else {}
        )
        prompt = f"""Generate a final collaboration determination.

ADVISOR FIT LEVEL: {necessity.get("necessity_level", "UNKNOWN")}
ADVISOR JUSTIFICATION: {necessity.get("justification", "N/A")}
MATCH PATHWAY: {match_pathway.get("recommended_pathway", "N/A")}
MATCH STATUS: {match_pathway.get("status", "UNKNOWN")}
CREATOR: {creator_profile.creator_name}

Return JSON:
{{
  "status": "MATCHED | CONDITIONAL_MATCH | DECLINED | PENDING_REVIEW",
  "pathway": "string",
  "determination_text": "string",
  "reasoning": "string",
  "confidence_score": 0.0,
  "collaboration_timeline": "string",
  "expected_reach": "string",
  "documentation_complete": true,
  "missing_items": ["string"],
  "appeal_guidance": "string"
}}"""

        fallback = self._default_final_determination(
            creator_profile=creator_profile,
            advisor_result=advisor_result,
            match_result=match_result,
            reason="Final determination model output unavailable or malformed.",
        )
        result = await self._call_json_model(prompt, fallback, max_tokens=1200)

        result.setdefault("status", "PENDING_REVIEW")
        result.setdefault("pathway", match_pathway.get("recommended_pathway", "Pending Human Review"))
        result.setdefault("determination_text", fallback["determination_text"])
        result.setdefault("reasoning", fallback["reasoning"])
        result.setdefault("confidence_score", 0.0)
        result.setdefault("collaboration_timeline", match_pathway.get("estimated_timeline", "Unknown"))
        result.setdefault("expected_reach", match_pathway.get("expected_reach", "Unknown"))
        result.setdefault("documentation_complete", False)
        result.setdefault("missing_items", [])
        result.setdefault("appeal_guidance", fallback["appeal_guidance"])
        if not isinstance(result.get("missing_items"), list):
            result["missing_items"] = []
        if result.get("status") not in {"MATCHED", "CONDITIONAL_MATCH", "DECLINED", "PENDING_REVIEW"}:
            result["status"] = "PENDING_REVIEW"

        await self.ledger.write(
            source=AgentSource.SYSTEM,
            event_type="FINAL_DETERMINATION",
            message=(
                f"Final determination generated. "
                f"Status: {result.get('status', 'PENDING_REVIEW')}. "
                f"Confidence: {float(result.get('confidence_score', 0.0)):.0%}."
            ),
            data=result,
            tags=["RESOLUTION", "FINAL_DETERMINATION", result.get("status", "PENDING_REVIEW")],
            severity=Severity.HIGH,
        )
        return result