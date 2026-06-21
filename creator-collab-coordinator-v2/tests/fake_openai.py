"""
Fake AsyncOpenAI client used across the test suite.

None of these tests make real network calls. Instead they patch
`agents.coordinator.AsyncOpenAI` (the only place a real client is
constructed — it's then shared into AdvisorAgent and MatchAgent) with this
fake, which inspects the *content* of each prompt to decide which canned
JSON response to hand back. That keeps the fake honest: it's responding to
"what is being asked", not just returning the same blob for every call.
"""

import json
from types import SimpleNamespace


def _response(text: str):
    """Mimic the shape of an OpenAI ChatCompletion response far enough for
    `response.choices[0].message.content` to work."""
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class FakeChatCompletions:
    def __init__(self, outer: "FakeAsyncOpenAI"):
        self._outer = outer

    async def create(self, model, messages, max_tokens=None, **kwargs):
        self._outer.calls += 1
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        text = self._outer.responder(system_prompt, user_prompt)
        return _response(text)


class FakeChat:
    def __init__(self, outer: "FakeAsyncOpenAI"):
        self.completions = FakeChatCompletions(outer)


class FakeAsyncOpenAI:
    """Drop-in stand-in for `openai.AsyncOpenAI` used in tests.

    `responder(system_prompt, user_prompt) -> str` decides what JSON text to
    return for a given call. `api_key` is accepted (and ignored) so this can
    be constructed with the same signature as the real client.
    """

    def __init__(self, api_key: str = "test-key", responder=None):
        self.api_key = api_key
        self.calls = 0
        self.responder = responder or default_responder
        self.chat = FakeChat(self)


def default_responder(system_prompt: str, user_prompt: str) -> str:
    """Routes each prompt to a plausible canned JSON response based on
    distinctive phrases that only appear in one specific prompt template."""

    if "Analyze this creator's audience" in user_prompt:
        return json.dumps({
            "audience_quality": "HIGH",
            "primary_segments": ["18-29 sustainability-curious"],
            "brand_fit_signals": ["high story engagement"],
            "audience_risks": [],
            "summary": "Strong values-aligned audience.",
        })

    if "Evaluate this creator's social metrics" in user_prompt:
        return json.dumps({
            "overall_performance": "STRONG",
            "standout_metrics": ["Average Engagement Rate"],
            "below_threshold_metrics": [],
            "performance_summary": "Engagement well above category norms.",
        })

    if "assess overall brand collaboration fit" in user_prompt:
        return json.dumps({
            "necessity_assessment": {
                "necessity_level": "STRONG_FIT",
                "justification": "High engagement and values alignment.",
            },
            "brand_search_hints": ["sustainability", "fast-track eligibility"],
            "flexibility_indicators": ["returning partner"],
            "key_strengths": ["audience trust"],
            "key_risks": [],
        })

    if "Search this brand-guideline chunk" in user_prompt:
        return json.dumps({
            "matched_requirements": [
                {
                    "section_id": "2.1",
                    "title": "Fast-Track Eligibility",
                    "relevant_text": "Creators with 5%+ engagement qualify for fast-track review.",
                    "relevance_score": 0.92,
                    "is_flexible": True,
                    "match_reason": "Engagement exceeds threshold.",
                    "creator_signals_matched": ["engagement_rate"],
                }
            ],
            "search_strategy_used": "keyword + semantic match",
        })

    if "Evaluate whether this creator-campaign case qualifies" in user_prompt:
        return json.dumps({
            "applicable_flexibility_clauses": [
                {
                    "section_id": "2.1",
                    "title": "Fast-Track Eligibility",
                    "all_criteria_met": True,
                    "criteria_evaluation": [
                        {"criterion": "engagement >= 5%", "met": True, "evidence": "8.2% engagement"}
                    ],
                    "missing_information": [],
                    "confidence": 0.9,
                }
            ],
            "best_clause_pathway": "FAST_TRACK",
            "recommendation": "Approve via fast-track pathway.",
        })

    if "recommend the collaboration pathway" in user_prompt:
        return json.dumps({
            "recommended_pathway": "FAST_TRACK",
            "status": "MATCHED",
            "estimated_timeline": "2-3 business days",
            "confidence_score": 0.91,
            "reasoning": "Strong fit and satisfied fast-track criteria.",
            "requirements_checklist": [{"item": "Disclosure", "status": "AVAILABLE", "source": "section 2.1"}],
            "expected_reach": "450K+ impressions",
            "risk_level": "LOW",
            "alternative_pathways": [],
        })

    if "Generate a final collaboration determination" in user_prompt:
        return json.dumps({
            "status": "MATCHED",
            "pathway": "FAST_TRACK",
            "determination_text": "Strong audience overlap and engagement; approved for fast-track collaboration.",
            "reasoning": "Advisor and Match agents agree on strong fit.",
            "confidence_score": 0.91,
            "collaboration_timeline": "2-3 business days",
            "expected_reach": "450K+ impressions",
            "documentation_complete": True,
            "missing_items": [],
            "appeal_guidance": "N/A",
        })

    # Fallback: an empty-ish object the caller's fallback/defaults will fill in.
    return json.dumps({})
