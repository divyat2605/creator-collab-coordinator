"""
Collaboration Ledger — Shared Memory System

This is the core innovation: a structured shared memory that both the Advisor Agent
and Match Agent read from and write to. When one agent discovers something, the other
agent's behavior changes in real-time.

Architecture:
- Thread-safe (asyncio locks)
- Event-driven (subscribers get notified on writes)
- Structured entries with typed fields
- Query interface for agents to search the ledger
"""

import asyncio
import uuid
from datetime import datetime, timezone

from models.schemas import AgentSource, LedgerEntry, Severity


class CollaborationLedger:
    def __init__(self):
        self._entries: list[LedgerEntry] = []
        self._lock = asyncio.Lock()
        self._subscribers: list[asyncio.Queue] = []
        self._context_cache: dict = {}  # agents can store derived context here

    async def write(
        self,
        source: AgentSource,
        event_type: str,
        message: str,
        data: dict = None,
        tags: list[str] = None,
        severity: Severity = Severity.NORMAL,
    ) -> LedgerEntry:
        """Write a new entry to the ledger. All subscribers are notified."""
        entry = LedgerEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc),
            source=source,
            event_type=event_type,
            message=message,
            data=data or {},
            tags=tags or [],
            severity=severity,
        )
        async with self._lock:
            self._entries.append(entry)
            # Notify all subscribers
            for queue in self._subscribers:
                await queue.put(entry)
        return entry

    async def read_all(self) -> list[LedgerEntry]:
        """Read all entries in the ledger."""
        async with self._lock:
            return list(self._entries)

    async def read_by_source(self, source: AgentSource) -> list[LedgerEntry]:
        """Read entries written by a specific agent."""
        async with self._lock:
            return [e for e in self._entries if e.source == source]

    async def read_by_tag(self, tag: str) -> list[LedgerEntry]:
        """Search entries by tag."""
        async with self._lock:
            return [e for e in self._entries if tag in e.tags]

    async def read_by_event_type(self, event_type: str) -> list[LedgerEntry]:
        """Read entries of a specific event type."""
        async with self._lock:
            return [e for e in self._entries if e.event_type == event_type]

    async def get_advisor_context(self) -> str:
        """
        Build an advisor context summary from all advisor entries.
        This is what the Match Agent reads to adjust its search.
        """
        advisor_entries = await self.read_by_source(AgentSource.ADVISOR)
        if not advisor_entries:
            return "No advisor data available yet."

        parts = []
        for entry in advisor_entries:
            parts.append(f"[{entry.event_type}] {entry.message}")
            if entry.data:
                for k, v in entry.data.items():
                    if isinstance(v, list):
                        parts.append(f"  {k}: {', '.join(str(x) for x in v)}")
                    else:
                        parts.append(f"  {k}: {v}")
        return "\n".join(parts)

    async def get_match_context(self) -> str:
        """Build a match context summary from all match entries."""
        match_entries = await self.read_by_source(AgentSource.MATCH)
        if not match_entries:
            return "No match findings yet."

        parts = []
        for entry in match_entries:
            parts.append(f"[{entry.event_type}] {entry.message}")
            if entry.data:
                for k, v in entry.data.items():
                    parts.append(f"  {k}: {v}")
        return "\n".join(parts)

    async def get_full_context(self) -> str:
        """Get the complete ledger as a formatted context string."""
        entries = await self.read_all()
        if not entries:
            return "Ledger is empty."

        parts = ["=== COLLABORATION LEDGER ===\n"]
        for entry in entries:
            source_label = entry.source.value.upper()
            parts.append(
                f"[{entry.timestamp.strftime('%H:%M:%S.%f')[:-3]}] "
                f"({source_label}) [{entry.event_type}] {entry.message}"
            )
            if entry.tags:
                parts.append(f"  Tags: {', '.join(entry.tags)}")
            if entry.data:
                for k, v in entry.data.items():
                    parts.append(f"  {k}: {v}")
            parts.append("")
        return "\n".join(parts)

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to ledger updates. Returns a queue that receives new entries."""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from ledger updates."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def set_context(self, key: str, value):
        """Store derived context that agents can share."""
        async with self._lock:
            self._context_cache[key] = value

    async def get_context(self, key: str, default=None):
        """Retrieve shared context."""
        async with self._lock:
            return self._context_cache.get(key, default)

    async def clear(self):
        """Clear the ledger for a new collaboration run."""
        async with self._lock:
            self._entries.clear()
            self._context_cache.clear()
