import asyncio

import pytest

from memory.ledger import CollaborationLedger
from models.schemas import AgentSource, Severity


@pytest.mark.asyncio
async def test_write_and_read_all():
    ledger = CollaborationLedger()
    entry = await ledger.write(
        source=AgentSource.ADVISOR,
        event_type="PROFILE_SCAN_START",
        message="scanning",
        tags=["INIT"],
    )
    all_entries = await ledger.read_all()
    assert len(all_entries) == 1
    assert all_entries[0].id == entry.id
    assert all_entries[0].source == AgentSource.ADVISOR


@pytest.mark.asyncio
async def test_read_by_source_and_tag():
    ledger = CollaborationLedger()
    await ledger.write(source=AgentSource.ADVISOR, event_type="A", message="a", tags=["X"])
    await ledger.write(source=AgentSource.MATCH, event_type="B", message="b", tags=["Y"])

    advisor_entries = await ledger.read_by_source(AgentSource.ADVISOR)
    assert len(advisor_entries) == 1
    assert advisor_entries[0].event_type == "A"

    tagged = await ledger.read_by_tag("Y")
    assert len(tagged) == 1
    assert tagged[0].event_type == "B"


@pytest.mark.asyncio
async def test_subscribers_receive_writes():
    ledger = CollaborationLedger()
    queue = ledger.subscribe()

    await ledger.write(source=AgentSource.SYSTEM, event_type="PING", message="hello")

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.event_type == "PING"

    ledger.unsubscribe(queue)
    await ledger.write(source=AgentSource.SYSTEM, event_type="PONG", message="should not arrive")
    assert queue.empty()


@pytest.mark.asyncio
async def test_context_cache_roundtrip():
    ledger = CollaborationLedger()
    await ledger.set_context("brand_search_hints", ["a", "b"])
    value = await ledger.get_context("brand_search_hints")
    assert value == ["a", "b"]
    assert await ledger.get_context("missing_key", default="fallback") == "fallback"


@pytest.mark.asyncio
async def test_clear_resets_entries_and_context():
    ledger = CollaborationLedger()
    await ledger.write(source=AgentSource.SYSTEM, event_type="X", message="x")
    await ledger.set_context("k", "v")

    await ledger.clear()

    assert await ledger.read_all() == []
    assert await ledger.get_context("k") is None


@pytest.mark.asyncio
async def test_get_advisor_context_includes_written_entries():
    ledger = CollaborationLedger()
    await ledger.write(
        source=AgentSource.ADVISOR,
        event_type="FIT_ASSESSMENT",
        message="Fit assessment: STRONG_FIT.",
        data={"fit_score": 0.9},
        severity=Severity.HIGH,
    )
    context = await ledger.get_advisor_context()
    assert "FIT_ASSESSMENT" in context
    assert "fit_score" in context
