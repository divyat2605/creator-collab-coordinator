"""
Match Agent - Brand Guideline Search and Collaboration Pathway Selection.

This agent:
1. Reads the Collaboration Ledger to understand Advisor Agent findings.
2. Uses those findings to adapt its search through brand guidelines.
3. Identifies relevant guideline sections and flexibility clauses.
4. Recommends the best collaboration match pathway.
"""

import json
import re
from typing import Any, List

from openai import AsyncOpenAI
from models.schemas import AgentSource, Severity
from memory.ledger import CollaborationLedger


MATCH_SYSTEM_PROMPT = """You are a Match Agent for brand-creator collaboration.
You analyze brand collaboration guidelines and map them to creator strengths,
audience signals, deliverable fit, and risk controls.

Your job is to:
1. Find guideline sections relevant to the creator and campaign.
2. Identify flexible clauses and fast-track pathways.
3. Explain why each section matches.
4. Recommend a final collaboration pathway.

Respond in valid JSON only. No markdown."""


class MatchAgent:
    def __init__(self, client: AsyncOpenAI, ledger: CollaborationLedger):
        self.client = client
        self.ledger = ledger
        self.model = "gpt-4o-mini"

    async def analyze_guidelines(self, guidelines_text: str, brand_name: str) -> dict:
        """Main entrypoint for brand-guideline analysis."""
        advisor_context = await self.ledger.get_advisor_context()
        search_hints = await self.ledger.get_context("brand_search_hints") or []
        fit_level = await self.ledger.get_context("fit_level") or "UNKNOWN"
        flexibility_indicators = await self.ledger.get_context("flexibility_indicators") or []

        await self.ledger.write(
            source=AgentSource.MATCH,
            event_type="LEDGER_READ",
            message=(
                f"Reading collaboration context for {brand_name}. "
                f"Fit level: {fit_level}. "
                f"Applying {len(search_hints)} advisor hint(s)."
            ),
            data={
                "fit_level": fit_level,
                "brand_search_hints": search_hints,
                "flexibility_indicators": flexibility_indicators,
            },
            tags=["LEDGER_READ", "MATCH_CONTEXT"],
        )

        matched_requirements = await self._search_brand_requirements(
            guidelines_text=guidelines_text,
            advisor_context=advisor_context,
            search_hints=search_hints,
            flexibility_indicators=flexibility_indicators,
        )
        flexibility_analysis = await self._analyze_flexibility_clauses(
            advisor_context=advisor_context,
            matched_requirements=matched_requirements,
            flexibility_indicators=flexibility_indicators,
        )
        match_pathway = await self._determine_match_pathway(
            advisor_context=advisor_context,
            matched_requirements=matched_requirements,
            flexibility_analysis=flexibility_analysis,
        )

        await self.ledger.write(
            source=AgentSource.LEDGER,
            event_type="MATCH_CONTEXT_COMPLETE",
            message=(
                f"Match analysis complete. Pathway: "
                f"{match_pathway.get('recommended_pathway', 'PENDING_REVIEW')}."
            ),
            data={
                "match_pathway": match_pathway,
                "flexibility_analysis": flexibility_analysis,
                "matched_requirements_count": len(matched_requirements),
            },
            tags=["LEDGER_WRITE", "MATCH_COMPLETE", match_pathway.get("status", "PENDING_REVIEW")],
            severity=Severity.HIGH,
        )

        return {
            "matched_requirements": matched_requirements,
            "flexibility_analysis": flexibility_analysis,
            "match_pathway": match_pathway,
        }

    def _safe_json_parse(self, text: Any) -> dict:
        if text is None:
            return {"error": "Empty response from model", "raw_text": None}
        if not isinstance(text, (str, bytes, bytearray)):
            return {"error": f"Unexpected response type: {type(text).__name__}", "raw_text": str(text)}
        if isinstance(text, (bytes, bytearray)):
            text = text.decode("utf-8", errors="ignore")
        if not text.strip():
            return {"error": "Empty response from model", "raw_text": text}

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        repaired = cleaned
        repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'")
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)
        repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            return {"error": "Failed to parse JSON from model output", "parse_error": str(e), "raw_text": text}

    async def _call_json_model(self, prompt: str, fallback: dict, max_tokens: int = 1800) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": MATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
            )
        except Exception as e:
            result = dict(fallback)
            result["error"] = f"Model call failed: {e}"
            return result

        result_text = ""
        try:
            result_text = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            pass

        parsed = self._safe_json_parse(result_text)
        if not isinstance(parsed, dict):
            result = dict(fallback)
            result["error"] = "Parsed output was not a JSON object"
            result["raw_text"] = result_text
            return result
        if parsed.get("error"):
            result = dict(fallback)
            result["parse_error"] = parsed.get("error")
            result["raw_text"] = parsed.get("raw_text")
            return result
        return parsed

    def _safe_score(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _build_guideline_chunks(
        self,
        guidelines_text: str,
        chunk_size: int = 3500,
        overlap: int = 400,
    ) -> List[dict]:
        if not guidelines_text:
            return []

        chunks: List[dict] = []
        start = 0
        idx = 1
        text_len = len(guidelines_text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(
                {
                    "chunk_id": f"chunk_{idx}",
                    "start": start,
                    "end": end,
                    "text": guidelines_text[start:end],
                }
            )
            if end >= text_len:
                break
            start = max(end - overlap, start + 1)
            idx += 1
        return chunks

    async def _search_brand_requirements(
        self,
        guidelines_text: str,
        advisor_context: str,
        search_hints: list[str],
        flexibility_indicators: list[str],
    ) -> list[dict]:
        chunks = self._build_guideline_chunks(guidelines_text)
        if not chunks:
            await self.ledger.write(
                source=AgentSource.MATCH,
                event_type="GUIDELINE_SCAN",
                message="Guideline scan skipped because guidelines text was empty.",
                data={"requirements_found": 0, "flexibility_clauses": 0},
                tags=["GUIDELINE_SCAN", "NO_GUIDELINES_TEXT"],
            )
            return []

        all_requirements: List[dict] = []
        for chunk in chunks[:8]:
            prompt = f"""Search this brand-guideline chunk for requirements relevant to the creator context.

ADVISOR SEARCH HINTS:
{json.dumps(search_hints, indent=2)}

FLEXIBILITY INDICATORS:
{json.dumps(flexibility_indicators, indent=2)}

ADVISOR CONTEXT:
{advisor_context}

GUIDELINE CHUNK ID: {chunk["chunk_id"]}
GUIDELINE TEXT:
{chunk["text"]}

Find all relevant sections including:
- mandatory collaboration requirements
- flexible/fast-track clauses
- thresholds or eligibility rules
- disclosure, safety, or quality controls

Respond with JSON:
{{
  "matched_requirements": [
    {{
      "section_id": "string",
      "title": "string",
      "relevant_text": "string",
      "relevance_score": 0.0,
      "is_flexible": true,
      "match_reason": "string",
      "creator_signals_matched": ["string"],
      "chunk_id": "{chunk["chunk_id"]}"
    }}
  ],
  "search_strategy_used": "string"
}}"""

            fallback = {"matched_requirements": [], "search_strategy_used": "fallback_chunk_scan"}
            result = await self._call_json_model(prompt, fallback, max_tokens=1400)
            requirements = result.get("matched_requirements", [])
            if isinstance(requirements, list):
                for req in requirements:
                    if isinstance(req, dict):
                        req.setdefault("chunk_id", chunk["chunk_id"])
                        all_requirements.append(req)

        deduped: List[dict] = []
        seen = set()
        for req in all_requirements:
            key = (
                str(req.get("section_id", "")).strip(),
                str(req.get("title", "")).strip(),
                str(req.get("relevant_text", "")).strip()[:200],
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(req)

        deduped = sorted(
            deduped,
            key=lambda r: self._safe_score(r.get("relevance_score", 0)),
            reverse=True,
        )[:12]

        flexible_count = sum(1 for r in deduped if r.get("is_flexible"))
        await self.ledger.write(
            source=AgentSource.MATCH,
            event_type="GUIDELINE_SCAN",
            message=(
                f"Guideline scan complete. Found {len(deduped)} requirement section(s), "
                f"including {flexible_count} flexible clause(s)."
            ),
            data={"requirements_found": len(deduped), "flexibility_clauses": flexible_count},
            tags=["GUIDELINE_SCAN", "REQUIREMENTS_FOUND"],
            severity=Severity.HIGH if flexible_count > 0 else Severity.NORMAL,
        )

        for req in deduped[:3]:
            tags = ["REQUIREMENT_MATCH"]
            if req.get("is_flexible"):
                tags.append("FLEXIBILITY_CLAUSE")
            await self.ledger.write(
                source=AgentSource.MATCH,
                event_type="SECTION_MATCH",
                message=f"§{req.get('section_id', '?')} - {req.get('title', 'Untitled')}: {req.get('match_reason', 'Relevant guideline matched')}",
                data={
                    "section_id": req.get("section_id"),
                    "relevance_score": req.get("relevance_score"),
                    "is_flexible": req.get("is_flexible"),
                    "chunk_id": req.get("chunk_id"),
                    "text_preview": str(req.get("relevant_text", ""))[:200],
                },
                tags=tags,
                severity=Severity.HIGH if req.get("is_flexible") else Severity.NORMAL,
            )

        return deduped

    async def _analyze_flexibility_clauses(
        self,
        advisor_context: str,
        matched_requirements: list[dict],
        flexibility_indicators: list[str],
    ) -> dict:
        flexible_sections = [r for r in matched_requirements if isinstance(r, dict) and r.get("is_flexible")]
        if not flexible_sections:
            return {
                "applicable_flexibility_clauses": [],
                "best_clause_pathway": "None",
                "recommendation": "No flexibility clauses found; standard requirement pathway applies.",
            }

        focused_guideline_text = "\n\n".join(
            [
                f"SECTION {r.get('section_id', '?')} - {r.get('title', 'Untitled')}\n{r.get('relevant_text', '')}"
                for r in flexible_sections
            ]
        )
        prompt = f"""Evaluate whether this creator-campaign case qualifies for matched flexibility clauses.

ADVISOR CONTEXT:
{advisor_context}

FLEXIBILITY INDICATORS:
{json.dumps(flexibility_indicators, indent=2)}

FLEXIBLE SECTIONS:
{json.dumps(flexible_sections, indent=2)}

GUIDELINE EXCERPTS:
{focused_guideline_text}

Respond with JSON:
{{
  "applicable_flexibility_clauses": [
    {{
      "section_id": "string",
      "title": "string",
      "all_criteria_met": true,
      "criteria_evaluation": [{{"criterion":"string","met":true,"evidence":"string"}}],
      "missing_information": ["string"],
      "confidence": 0.0
    }}
  ],
  "best_clause_pathway": "string",
  "recommendation": "string"
}}"""

        fallback = {
            "applicable_flexibility_clauses": [],
            "best_clause_pathway": "Pending Human Review",
            "recommendation": "Unable to reliably evaluate flexibility clauses; manual review recommended.",
        }
        result = await self._call_json_model(prompt, fallback, max_tokens=1600)
        result.setdefault("applicable_flexibility_clauses", [])
        result.setdefault("best_clause_pathway", "Pending Human Review")
        result.setdefault("recommendation", fallback["recommendation"])
        if not isinstance(result["applicable_flexibility_clauses"], list):
            result["applicable_flexibility_clauses"] = []

        qualifying = [e for e in result["applicable_flexibility_clauses"] if isinstance(e, dict) and e.get("all_criteria_met")]
        await self.ledger.write(
            source=AgentSource.MATCH,
            event_type="FLEXIBILITY_ANALYSIS",
            message=(
                f"Flexibility analysis: {len(qualifying)} of "
                f"{len(result.get('applicable_flexibility_clauses', []))} clause(s) fully satisfied. "
                f"Best clause pathway: {result.get('best_clause_pathway', 'Pending Human Review')}."
            ),
            data={"qualifying_flexibility_clauses": len(qualifying), "best_clause_pathway": result.get("best_clause_pathway")},
            tags=["FLEXIBILITY_ANALYSIS", "CLAUSE_CRITERIA_MET" if qualifying else "CLAUSE_CRITERIA_PARTIAL"],
            severity=Severity.HIGH if qualifying else Severity.NORMAL,
        )
        return result

    async def _determine_match_pathway(
        self,
        advisor_context: str,
        matched_requirements: list[dict],
        flexibility_analysis: dict,
    ) -> dict:
        prompt = f"""Based on advisor context and guideline matching, recommend the collaboration pathway.

ADVISOR CONTEXT:
{advisor_context}

MATCHED REQUIREMENTS:
{json.dumps(matched_requirements[:5], indent=2)}

FLEXIBILITY ANALYSIS:
{json.dumps(flexibility_analysis, indent=2)}

Respond with JSON:
{{
  "recommended_pathway": "string",
  "status": "MATCHED | CONDITIONAL_MATCH | DECLINED | PENDING_REVIEW",
  "estimated_timeline": "string",
  "confidence_score": 0.0,
  "reasoning": "string",
  "requirements_checklist": [{{"item":"string","status":"AVAILABLE | NEEDED | OPTIONAL","source":"string"}}],
  "expected_reach": "string",
  "risk_level": "LOW | MEDIUM | HIGH",
  "alternative_pathways": ["string"]
}}"""

        fallback = {
            "recommended_pathway": "Pending Human Review",
            "status": "PENDING_REVIEW",
            "estimated_timeline": "Unknown",
            "confidence_score": 0.0,
            "reasoning": "Model output was unavailable or malformed, so manual review is required.",
            "requirements_checklist": [],
            "expected_reach": "Unknown",
            "risk_level": "MEDIUM",
            "alternative_pathways": ["STANDARD_REVIEW"],
        }
        result = await self._call_json_model(prompt, fallback, max_tokens=1400)

        result.setdefault("recommended_pathway", fallback["recommended_pathway"])
        result.setdefault("status", "PENDING_REVIEW")
        result.setdefault("estimated_timeline", "Unknown")
        result.setdefault("confidence_score", 0.0)
        result.setdefault("reasoning", fallback["reasoning"])
        result.setdefault("requirements_checklist", [])
        result.setdefault("expected_reach", "Unknown")
        result.setdefault("risk_level", "MEDIUM")
        result.setdefault("alternative_pathways", ["STANDARD_REVIEW"])
        if not isinstance(result["requirements_checklist"], list):
            result["requirements_checklist"] = []
        if not isinstance(result["alternative_pathways"], list):
            result["alternative_pathways"] = ["STANDARD_REVIEW"]

        await self.ledger.write(
            source=AgentSource.MATCH,
            event_type="MATCH_PATHWAY_DETERMINATION",
            message=(
                f"Match pathway determined: {result.get('recommended_pathway', 'Pending Human Review')}. "
                f"Status: {result.get('status', 'PENDING_REVIEW')}. "
                f"Timeline: {result.get('estimated_timeline', 'Unknown')}."
            ),
            data=result,
            tags=["MATCH_PATHWAY", result.get("status", "PENDING_REVIEW")],
            severity=Severity.HIGH,
        )

        return result
