import json

import httpx
import pytest
from httpx import ASGITransport

from tests.fake_openai import default_responder


async def _get_client(app):
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_healthz(app):
    async with await _get_client(app) as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["openai_key_configured"] is True


@pytest.mark.asyncio
async def test_list_scenarios(app):
    async with await _get_client(app) as client:
        resp = await client.get("/api/campaigns")
        assert resp.status_code == 200
        body = resp.json()
        ids = {s["id"] for s in body["scenarios"]}
        assert {"fashion_influencer", "tech_educator"}.issubset(ids)
        assert body["guidelines_available"] is True


@pytest.mark.asyncio
async def test_get_scenario_returns_profile_and_guidelines(app):
    async with await _get_client(app) as client:
        resp = await client.get("/api/scenario/fashion_influencer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["creator_profile"]["creator_name"] == "Sofia Romero"
        assert body["guidelines_length"] > 0


@pytest.mark.asyncio
async def test_get_unknown_scenario_returns_404(app):
    async with await _get_client(app) as client:
        resp = await client.get("/api/scenario/does-not-exist")
        assert resp.status_code == 404


async def _run_match_and_collect(app, payload) -> dict:
    """Posts to /api/match and parses the SSE stream, returning the final
    `result` event payload (the same object the frontend's showOutcome()
    receives)."""
    transport = ASGITransport(app=app)
    result_payload = None
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        async with client.stream("POST", "/api/match", json=payload) as resp:
            assert resp.status_code == 200
            pending_event_name = None
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    pending_event_name = line[len("event: "):].strip()
                elif line.startswith("data: "):
                    if pending_event_name == "result":
                        result_payload = json.loads(line[len("data: "):])
                    pending_event_name = None
    return result_payload


@pytest.mark.asyncio
async def test_full_match_pipeline_matched_outcome(app, patch_openai):
    patch_openai()  # default_responder -> MATCHED scenario

    async with await _get_client(app) as client:
        scenario = await client.get("/api/scenario/fashion_influencer")
        scenario_data = scenario.json()

    payload = {
        "creator_profile": scenario_data["creator_profile"],
        "brand_guidelines": scenario_data["guidelines_text"],
        "brand_name": "Test Brand",
        "brand_id": "TEST-001",
    }

    result = await _run_match_and_collect(app, payload)
    assert result is not None

    determination = result["determination"]

    # This is the contract the frontend's showOutcome() depends on. These
    # exact key names previously didn't match what the UI was reading
    # (it read det.match_pathway / det.estimated_processing_time, which
    # don't exist) — this test pins the real contract down so that drift
    # is caught here instead of silently in the browser.
    for key in (
        "status", "pathway", "determination_text", "reasoning",
        "confidence_score", "collaboration_timeline", "expected_reach",
    ):
        assert key in determination, f"missing expected field: {key}"

    assert determination["status"] in {"MATCHED", "CONDITIONAL_MATCH", "DECLINED", "PENDING_REVIEW"}
    assert determination["status"] == "MATCHED"
    assert isinstance(determination["confidence_score"], (int, float))

    # Ledger should contain entries from every phase.
    event_types = {e["event_type"] for e in result["ledger"]}
    assert "PROFILE_SCAN_START" in event_types
    assert "FIT_ASSESSMENT" in event_types
    assert "LEDGER_READ" in event_types
    assert "MATCH_PATHWAY_DETERMINATION" in event_types
    assert "PROCESS_COMPLETE" in event_types


@pytest.mark.asyncio
async def test_full_match_pipeline_declined_outcome(app, patch_openai):
    def declined_responder(system_prompt, user_prompt):
        text = default_responder(system_prompt, user_prompt)
        # Flip the two status-bearing responses to DECLINED so we can verify
        # the full pipeline (and the status enum) handles that path too.
        if '"recommended_pathway"' in text:
            return text.replace('"status": "MATCHED"', '"status": "DECLINED"')
        if '"determination_text"' in text:
            return text.replace('"status": "MATCHED"', '"status": "DECLINED"')
        return text

    patch_openai(responder=declined_responder)

    async with await _get_client(app) as client:
        scenario = await client.get("/api/scenario/tech_educator")
        scenario_data = scenario.json()

    payload = {
        "creator_profile": scenario_data["creator_profile"],
        "brand_guidelines": scenario_data["guidelines_text"],
        "brand_name": "Test Brand",
        "brand_id": "TEST-002",
    }

    result = await _run_match_and_collect(app, payload)
    assert result is not None
    assert result["determination"]["status"] == "DECLINED"


@pytest.mark.asyncio
async def test_match_without_api_key_returns_500(app, monkeypatch):
    import main as main_module
    monkeypatch.setattr(main_module, "API_KEY", "")

    async with await _get_client(app) as client:
        resp = await client.post("/api/match", json={
            "creator_profile": {
                "creator_name": "X",
                "creator_follower_count": 1,
                "creator_primary_platform": "Instagram",
                "creator_specialty": "test",
            },
            "brand_guidelines": "guidelines",
        })
        assert resp.status_code == 500
