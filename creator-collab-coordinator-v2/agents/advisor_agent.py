"""
Advisor Agent — Creator Profile Analysis for Brand Collaboration.

This agent:
1. Analyzes the creator profile (audience, metrics, expertise, deliverables).
2. Writes structured findings to the Collaboration Ledger.
3. Provides brand_search_hints so the Match Agent adapts its guideline search.
4. Assesses overall creator fit level.

Audience analysis and metrics analysis are independent of each other (both
only depend on the raw creator profile), so they run concurrently via
asyncio.gather. The fit assessment depends on both, so it always runs last.
"""

import asyncio
import json

from openai import AsyncOpenAI
from models.schemas import AgentSource, CreatorProfile, Severity
from memory.ledger import CollaborationLedger
from agents.llm_utils import call_json_model

ADVISOR_SYSTEM_PROMPT = """You are an Advisor Agent for brand-creator collaboration.
You analyze creator profiles — audience demographics, social metrics, expertise areas,
proposed deliverables, and past collaboration history.

Your job is to:
1. Assess how strong a fit the creator is for a brand collaboration.
2. Surface key audience and performance signals.
3. Identify flexibility indicators (e.g. returning partner, high engagement niche educator).
4. Provide search hints so a downstream Match Agent knows which guideline sections to prioritize.

Respond in valid JSON only. No markdown."""

# Bounds how many concurrent OpenAI calls this agent makes at once.
_CONCURRENCY_LIMIT = 4


class AdvisorAgent:
    def __init__(self, client: AsyncOpenAI, ledger: CollaborationLedger):
        self.client = client
        self.ledger = ledger
        self.model = "gpt-4o-mini"
        self._semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)

    async def analyze_creator_profile(self, creator_profile: CreatorProfile) -> dict:
        """Main entrypoint — analyze creator profile and write findings to ledger."""

        await self.ledger.write(
            source=AgentSource.ADVISOR,
            event_type="PROFILE_SCAN_START",
            message=f"Advisor Agent scanning profile: {creator_profile.creator_name} ({creator_profile.creator_primary_platform}, {creator_profile.creator_follower_count:,} followers).",
            data={
                "creator_name": creator_profile.creator_name,
                "platform": creator_profile.creator_primary_platform,
                "follower_count": creator_profile.creator_follower_count,
                "specialty": creator_profile.creator_specialty,
            },
            tags=["PROFILE_SCAN_START", "INIT"],
        )

        # Audience + metrics analysis are independent — run them concurrently.
        audience_analysis, metrics_analysis = await asyncio.gather(
            self._analyze_audience(creator_profile),
            self._analyze_metrics(creator_profile),
        )

        fit_assessment = await self._assess_fit(
            creator_profile=creator_profile,
            audience_analysis=audience_analysis,
            metrics_analysis=metrics_analysis,
        )

        # Write structured context to ledger for Match Agent to consume
        await self.ledger.set_context("brand_search_hints", fit_assessment.get("brand_search_hints", []))
        await self.ledger.set_context("fit_level", fit_assessment.get("necessity_assessment", {}).get("necessity_level", "UNKNOWN"))
        await self.ledger.set_context("flexibility_indicators", fit_assessment.get("flexibility_indicators", []))

        await self.ledger.write(
            source=AgentSource.ADVISOR,
            event_type="ADVISOR_CONTEXT_COMPLETE",
            message=(
                f"Advisor context written to ledger. "
                f"Fit level: {fit_assessment.get('necessity_assessment', {}).get('necessity_level', 'UNKNOWN')}. "
                f"{len(fit_assessment.get('brand_search_hints', []))} search hint(s) for Match Agent."
            ),
            data={
                "fit_level": fit_assessment.get("necessity_assessment", {}).get("necessity_level"),
                "brand_search_hints": fit_assessment.get("brand_search_hints", []),
                "flexibility_indicators": fit_assessment.get("flexibility_indicators", []),
            },
            tags=["ADVISOR_COMPLETE", "LEDGER_WRITE"],
            severity=Severity.HIGH,
        )

        return fit_assessment

    # ── helpers ────────────────────────────────────────────────────

    async def _call(self, prompt: str, fallback: dict, max_tokens: int) -> dict:
        return await call_json_model(
            client=self.client,
            model=self.model,
            system_prompt=ADVISOR_SYSTEM_PROMPT,
            user_prompt=prompt,
            fallback=fallback,
            max_tokens=max_tokens,
            semaphore=self._semaphore,
        )

    async def _analyze_audience(self, creator_profile: CreatorProfile) -> dict:
        prompt = f"""Analyze this creator's audience for brand collaboration potential.

CREATOR: {creator_profile.creator_name}
PLATFORM: {creator_profile.creator_primary_platform}
FOLLOWERS: {creator_profile.creator_follower_count:,}
SPECIALTY: {creator_profile.creator_specialty}
AUDIENCE DEMOGRAPHICS:
{json.dumps(creator_profile.audience_demographics, indent=2)}

Respond with JSON:
{{
  "audience_quality": "HIGH | MEDIUM | LOW",
  "primary_segments": ["string"],
  "brand_fit_signals": ["string"],
  "audience_risks": ["string"],
  "summary": "string"
}}"""

        fallback = {
            "audience_quality": "MEDIUM",
            "primary_segments": [],
            "brand_fit_signals": [],
            "audience_risks": [],
            "summary": "Audience analysis unavailable.",
        }
        result = await self._call(prompt, fallback, max_tokens=800)

        await self.ledger.write(
            source=AgentSource.ADVISOR,
            event_type="AUDIENCE_ANALYSIS",
            message=f"Audience analysis complete. Quality: {result.get('audience_quality', 'UNKNOWN')}. {result.get('summary', '')}",
            data=result,
            tags=["AUDIENCE_ANALYSIS"],
            severity=Severity.NORMAL,
        )
        return result

    async def _analyze_metrics(self, creator_profile: CreatorProfile) -> dict:
        metrics_list = [
            {"name": m.name, "value": m.value, "unit": m.unit, "flag": m.flag.value, "reference_range": m.reference_range}
            for m in creator_profile.social_metrics
        ]

        prompt = f"""Evaluate this creator's social metrics for brand collaboration readiness.

CREATOR: {creator_profile.creator_name}
PLATFORM: {creator_profile.creator_primary_platform}
SOCIAL METRICS:
{json.dumps(metrics_list, indent=2)}

Respond with JSON:
{{
  "overall_performance": "STRONG | ACCEPTABLE | WEAK",
  "standout_metrics": ["string"],
  "below_threshold_metrics": ["string"],
  "performance_summary": "string"
}}"""

        fallback = {
            "overall_performance": "ACCEPTABLE",
            "standout_metrics": [],
            "below_threshold_metrics": [],
            "performance_summary": "Metrics analysis unavailable.",
        }
        result = await self._call(prompt, fallback, max_tokens=600)

        await self.ledger.write(
            source=AgentSource.ADVISOR,
            event_type="METRICS_ANALYSIS",
            message=f"Metrics analysis complete. Performance: {result.get('overall_performance', 'UNKNOWN')}. {result.get('performance_summary', '')}",
            data=result,
            tags=["METRICS_ANALYSIS"],
            severity=Severity.HIGH if result.get("overall_performance") == "STRONG" else Severity.NORMAL,
        )
        return result

    async def _assess_fit(
        self,
        creator_profile: CreatorProfile,
        audience_analysis: dict,
        metrics_analysis: dict,
    ) -> dict:
        deliverable = creator_profile.proposed_deliverables
        deliverable_info = {
            "name": deliverable.name,
            "category": deliverable.category,
            "brand_objective": deliverable.brand_objective,
        } if deliverable else {}

        prompt = f"""Based on the full creator profile and analysis, assess overall brand collaboration fit.

CREATOR: {creator_profile.creator_name}
PLATFORM: {creator_profile.creator_primary_platform}
SPECIALTY: {creator_profile.creator_specialty}
BIO: {creator_profile.bio}
PREVIOUS COLLABORATIONS: {json.dumps(creator_profile.previous_collaborations, indent=2)}
PROPOSED DELIVERABLE: {json.dumps(deliverable_info, indent=2)}

AUDIENCE ANALYSIS:
{json.dumps(audience_analysis, indent=2)}

METRICS ANALYSIS:
{json.dumps(metrics_analysis, indent=2)}

Respond with JSON:
{{
  "necessity_assessment": {{
    "necessity_level": "STRONG_FIT | RECOMMENDED | CONDITIONAL | NOT_RECOMMENDED",
    "justification": "string"
  }},
  "brand_search_hints": ["string"],
  "flexibility_indicators": ["string"],
  "key_strengths": ["string"],
  "key_risks": ["string"]
}}"""

        fallback = {
            "necessity_assessment": {
                "necessity_level": "CONDITIONAL",
                "justification": "Fit assessment unavailable; manual review recommended.",
            },
            "brand_search_hints": ["standard collaboration requirements", "engagement thresholds"],
            "flexibility_indicators": [],
            "key_strengths": [],
            "key_risks": [],
        }
        result = await self._call(prompt, fallback, max_tokens=1000)

        result.setdefault("necessity_assessment", fallback["necessity_assessment"])
        result.setdefault("brand_search_hints", fallback["brand_search_hints"])
        result.setdefault("flexibility_indicators", [])
        result.setdefault("key_strengths", [])
        result.setdefault("key_risks", [])

        await self.ledger.write(
            source=AgentSource.ADVISOR,
            event_type="FIT_ASSESSMENT",
            message=(
                f"Fit assessment: {result['necessity_assessment'].get('necessity_level', 'UNKNOWN')}. "
                f"{result['necessity_assessment'].get('justification', '')}"
            ),
            data=result,
            tags=["FIT_ASSESSMENT", result["necessity_assessment"].get("necessity_level", "UNKNOWN")],
            severity=Severity.HIGH,
        )
        return result
