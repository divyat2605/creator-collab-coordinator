<div align="center">

# ⭐ Creator Collaboration Coordinator

**Multi-Agent Brand–Creator Matching Platform powered by Shared Memory**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![SSE Streaming](https://img.shields.io/badge/SSE-Live_Streaming-FF6B35?style=for-the-badge&logo=apachekafka&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br/>

> *Two AI agents collaborating through shared memory to match brands with creators —*
> *fast, transparently, and at scale.*

</div>

---

## 🎬 Demo Video

[![Watch Demo on Loom](https://img.shields.io/badge/▶%20Watch%20Demo-625DF5?style=for-the-badge&logo=loom&logoColor=white)](https://www.loom.com/share/173f5ce5e2174c2b8d4963585ff8f229)

> *Watch the Advisor Agent populate the Collaboration Ledger in real time, then the Match Agent read shared state and produce a structured decision — live.*

---

## 📸 Screenshots

| Landing Page | Advisor Agent Live | Fit Assessment | Match Agent Activates |
|:---:|:---:|:---:|:---:|
| ![Landing](assets/landingpage.png) | ![Advisor](assets/advisor_agent.png) | ![Fit](assets/fit_Assessment.png) | ![Match](assets/match_Agent_Activates.png) |
| Select scenario or upload custom data | Ledger populates in real-time via SSE | `STRONG_FIT` tagged within 14s | Match Agent reads shared state & reasons |

---

## ✨ Why This Project Stands Out

- 🧠 **Genuine multi-agent collaboration** — Advisor and Match Agents share a structured memory store, not opaque text blobs
- 📒 **Collaboration Ledger** — typed, timestamped, queryable shared state with event-driven subscribers
- 📡 **Live SSE streaming** — agent reasoning rendered in real time in the browser; no polling, no refresh
- 🔍 **Fully auditable decisions** — every match, conditional approval, or decline carries a structured rationale
- ⚡ **Production-inspired async orchestration** — `CampaignCoordinator` phases agents sequentially (each phase reads the previous one's ledger state), while independent sub-steps *within* a phase — audience vs. metrics analysis, guideline-chunk scanning — run concurrently via `asyncio.gather`
- 🔁 **Real retry logic** — every LLM call goes through a shared helper (`agents/llm_utils.py`) with exponential backoff on rate limits/timeouts/5xx, not just a try/except that gives up
- ✅ **Tested** — `pytest` suite covering the ledger, JSON-repair/retry logic, and a full mocked end-to-end pipeline run that pins down the exact backend↔frontend field contract
- 🔌 **Zero-retraining iteration** — update brand guidelines as a TXT/PDF; no model fine-tuning required

---

## 📊 Example Outcome

> **Creator:** Sofia Romero &nbsp;|&nbsp; **Brand:** Sustainable Fashion Co.

| Field | Value |
|---|---|
| **Result** | ✅ MATCHED |
| **Fit Score** | 91% |
| **Risk Flags** | 0 |
| **Pathway** | ⚡ FAST\_TRACK |
| **Reason** | Strong audience overlap (18–29, sustainability-curious), high engagement (8.2%), values alignment confirmed, no brand safety concerns found |

---

## 🚀 Quick Start

**Prerequisites:** Python 3.11+ · OpenAI API key

```bash
# Clone and enter project
cd creator-collab-coordinator

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
venv\Scripts\activate             # Windows PowerShell

# Install
pip install -r requirements.txt

# Configure your API key — either export it directly...
export OPENAI_API_KEY="sk-your-key-here"   # or $env: on Windows
# ...or copy .env.example to .env and fill it in (auto-loaded on startup)
cp .env.example .env

python main.py
```

Open **`http://localhost:8000`**. Check `http://localhost:8000/healthz` any time to confirm the server is up and the API key is configured.

### 🧪 Testing

```bash
pytest
```

25 tests covering the `CollaborationLedger` (writes, subscriptions, queries,
context cache), the shared `llm_utils` JSON-repair and retry logic (including
a test that injects rate-limit errors and asserts the backoff-then-recover
path), and a full mocked end-to-end `/api/match` run — that last one is a
regression test for the exact field names the frontend reads off the final
determination, so a backend/frontend contract drift fails CI instead of
showing up as a silently broken outcome panel in the browser. No real OpenAI
calls are made; a fake client routes each prompt to a scripted JSON response.

---

## 🧠 Core Idea

Traditional influencer selection is opaque and hard to audit. This platform makes AI reasoning **legible**:

- Every agent decision is **structured, tagged, and timestamped** in the Collaboration Ledger
- The Match Agent **reads and adapts** to what the Advisor Agent wrote — not a summary, the actual typed state
- Every outcome ships with a **full audit trail**: cited guideline sections, risk flags, fit scores

```mermaid
flowchart LR
    A([📋 Brand Brief]) --> B[Advisor Agent]
    B -->|writes structured findings| C[(Collaboration Ledger)]
    C -->|reads shared state| D[Match Agent]
    D --> E{Decision}
    E -->|✅| F([MATCHED])
    E -->|⚡| G([CONDITIONAL])
    E -->|❌| H([DECLINED])
    E -->|🔍| I([PENDING REVIEW])

    style C fill:#1a1a2e,stroke:#e94560,color:#fff
    style B fill:#16213e,stroke:#0f3460,color:#fff
    style D fill:#16213e,stroke:#0f3460,color:#fff
    style F fill:#1b4332,stroke:#40916c,color:#fff
    style G fill:#33270a,stroke:#d4a017,color:#fff
    style H fill:#3b0a0a,stroke:#e63946,color:#fff
    style I fill:#1a1a2e,stroke:#8338ec,color:#fff
```

---

## 🎮 Demo Scenarios

The Match Agent reads the **same guidelines** for both creators — but reasons differently because the Advisor Agent writes different findings into the Ledger.

```mermaid
flowchart LR
    subgraph S1["🌿 Scenario 1 — Sofia Romero"]
        P1["Instagram · 450K followers\n8.2% engagement · Sustainable fashion"]
        T1["Tags: STRONG_FIT · fast-track-eligible"]
        B1["Best for: Eco brands, circular fashion,\nethical apparel launches"]
        P1 --> T1 --> B1
    end

    subgraph S2["💻 Scenario 2 — Marcus Chen"]
        P2["YouTube · 280K subscribers\n72% video completion · Tech education"]
        T2["Tags: EDUCATIONAL_FIT · brand-safety-verified"]
        B2["Best for: Dev tools, SaaS onboarding,\nproduct explainers"]
        P2 --> T2 --> B2
    end

    style S1 fill:#0a2d1a,stroke:#40916c
    style S2 fill:#0a1a2d,stroke:#0f3460
```

---

## 🏗️ System Architecture

### 🏛 Architecture at a Glance

```
Brand Brief
    ↓
Advisor Agent  —  analyzes creator profile, scores fit, surfaces risks
    ↓
Collaboration Ledger  —  thread-safe async shared memory (typed, queryable)
    ↓
Match Agent  —  reads ledger, maps to brand brief, cites guidelines
    ↓
Decision + Audit Trail  (MATCHED / CONDITIONAL / DECLINED / PENDING_REVIEW)
```

### Full Agent Collaboration Model

```mermaid
graph TD
    subgraph INPUT["📥 Input Layer"]
        CP[Creator Profile JSON]
        BG[Brand Guidelines TXT/PDF]
    end

    subgraph ADVISOR["🟢 Advisor Agent — Creator-Centric"]
        A1[Profile Scan]
        A2[Audience Analysis]
        A3[Metrics Grading]
        A4[Risk Surfacing]
        A5[Fit Scoring]
        A1 --> A2 --> A3 --> A4 --> A5
    end

    subgraph LEDGER["🔴 Collaboration Ledger — Shared Memory"]
        L1[Thread-safe async store]
        L2[Event-driven subscribers]
        L3[Typed query interface]
        L1 --- L2 --- L3
    end

    subgraph MATCH["🔵 Match Agent — Brand-Centric"]
        M1[Read Ledger State]
        M2[Map to Brand Requirements]
        M3[Cite Guideline Sections]
        M4[Determine Pathway]
        M1 --> M2 --> M3 --> M4
    end

    subgraph OUTPUT["📤 Output Layer"]
        O1[✅ MATCHED]
        O2[⚡ CONDITIONAL]
        O3[❌ DECLINED]
        O4[🔍 PENDING_REVIEW]
    end

    CP --> ADVISOR
    BG --> MATCH
    ADVISOR -->|writes LedgerEntry| LEDGER
    LEDGER -->|reads structured state| MATCH
    MATCH --> OUTPUT
```

### SSE Streaming Pipeline

Each LLM call is a single (non-streamed) completion — what's actually
streamed live to the browser is the *ledger event*, the moment each agent
writes a structured finding. Independent sub-steps fan out concurrently
instead of awaiting one call at a time:

```mermaid
sequenceDiagram
    participant B as 🌐 Browser
    participant F as ⚡ FastAPI
    participant C as 🎯 Coordinator
    participant ADV as 🟢 Advisor
    participant MAT as 🔵 Match
    participant OAI as 🤖 GPT-4o-mini

    B->>F: POST /api/match
    F->>C: process_collaboration(request)
    C->>ADV: Phase 1 — analyze creator
    ADV-->>B: SSE: PROFILE_SCAN_START
    par concurrent sub-analyses
        ADV->>OAI: audience analysis
    and
        ADV->>OAI: metrics analysis
    end
    ADV-->>B: SSE: AUDIENCE_ANALYSIS, METRICS_ANALYSIS
    ADV->>OAI: fit assessment (needs both results above)
    ADV-->>B: SSE: FIT_ASSESSMENT, ADVISOR_CONTEXT_COMPLETE

    Note over ADV,MAT: Ledger populated with Advisor findings

    C->>MAT: Phase 2 — match to brief
    MAT-->>B: SSE: LEDGER_READ
    par concurrent guideline-chunk scan (bounded by a semaphore)
        MAT->>OAI: scan chunk 1
    and
        MAT->>OAI: scan chunk N
    end
    MAT-->>B: SSE: GUIDELINE_SCAN, SECTION_MATCH
    MAT->>OAI: flexibility analysis, then pathway determination
    MAT-->>B: SSE: FLEXIBILITY_ANALYSIS, MATCH_PATHWAY_DETERMINATION
    C->>OAI: final determination call
    C-->>B: SSE: FINAL_DETERMINATION, PROCESS_COMPLETE + result
```

Any call in the diagram above that fails transiently (rate limit, timeout,
5xx) is retried with exponential backoff before falling back to a safe
default — see `agents/llm_utils.py`.

### Shared Ledger vs. Message Passing

```mermaid
flowchart LR
    subgraph NAIVE["❌ Naive Multi-Agent"]
        direction LR
        N1[Advisor] -->|"Sofia is good"| N2[Match]
        N2 --> N3[Result — no trail]
    end

    subgraph LEDGER["✅ Ledger-Based — This System"]
        direction LR
        L1[Advisor] -->|"LedgerEntry { event_type, tags,\nfit_score, risk_flags }"| L2[(Ledger)]
        L2 -->|typed query| L3[Match]
        L3 --> L4[Result + Full Audit Trail]
    end

    style NAIVE fill:#2d0a0a,stroke:#e63946
    style LEDGER fill:#0a2d1a,stroke:#40916c
```

---

## ⚡ Architectural Tradeoffs

```mermaid
flowchart TD
    D1{"Agent Communication"} -->|chosen| S1[Shared Ledger]
    D1 -->|alternative| A1[Message passing]
    S1 --> R1["Full audit trail — Match queries semantics not summaries"]

    D2{"Streaming"} -->|chosen| S2[SSE]
    D2 -->|alternative| A2[WebSockets]
    S2 --> R2["Unidirectional is sufficient — client only receives"]

    D3{"Memory"} -->|chosen| S3[Async in-process Ledger]
    D3 -->|alternative| A3[Redis]
    S3 --> R3["Zero infra for demos — Redis-swappable for prod"]

    D4{"LLM Calls"} -->|chosen| S4["Sequential across phases,\nparallel within a phase"]
    D4 -->|alternative| A4["Fully parallel"]
    S4 --> R4["Match needs Advisor's ledger output, so phases stay sequential —\nbut independent calls inside a phase (audience+metrics, guideline chunks)\nfan out concurrently via asyncio.gather"]

    style S1 fill:#0f3460,stroke:#e94560,color:#fff
    style S2 fill:#0f3460,stroke:#e94560,color:#fff
    style S3 fill:#0f3460,stroke:#e94560,color:#fff
    style S4 fill:#0f3460,stroke:#e94560,color:#fff
```

### Known Limitations

| Limitation | Suggested Fix |
|---|---|
| In-process ledger doesn't scale across workers | Swap for Redis Streams |
| No persistent storage | Add Postgres for historical analytics |
| Single-turn LLM calls | Multi-turn for better edge-case handling |
| No creator consent/privacy layer | Required before production use |
| OpenAI-only | Provider-agnostic via LiteLLM |

---

## 💡 Technical Highlights

**1. True Shared Memory** — `memory/ledger.py`
```python
class CollaborationLedger:
    async def write(self, source, event_type, message, data=None, tags=None, severity=...) -> LedgerEntry:
        entry = LedgerEntry(id=..., timestamp=..., source=source, event_type=event_type,
                             message=message, data=data or {}, tags=tags or [], severity=severity)
        async with self._lock:
            self._entries.append(entry)
            for queue in self._subscribers:          # event-driven: SSE consumers
                await queue.put(entry)                # get notified immediately
        return entry

    async def read_by_event_type(self, event_type) -> list[LedgerEntry]:
        async with self._lock:
            return [e for e in self._entries if e.event_type == event_type]
```

**2. Structured Agent Reasoning** — `agents/advisor_agent.py`
```python
await self.ledger.write(
    source=AgentSource.ADVISOR,
    event_type="FIT_ASSESSMENT",
    message=f"Fit assessment: {necessity_level}. {justification}",
    data=result,  # {necessity_assessment, brand_search_hints, flexibility_indicators, ...}
    tags=["FIT_ASSESSMENT", necessity_level],     # e.g. "STRONG_FIT"
    severity=Severity.HIGH,
)
```

**3. Match Agent Adapts to Ledger State** — `agents/match_agent.py`
```python
fit_level = await self.ledger.get_context("fit_level")               # set by Advisor
search_hints = await self.ledger.get_context("brand_search_hints")   # set by Advisor
# ... guideline chunks are scanned with those hints baked into the prompt,
# so the Match Agent searches differently depending on what the Advisor found —
# not a static keyword search re-run on every profile.
```

---

## 🔧 API Reference

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe + config check |
| `GET` | `/api/campaigns` | List demo scenarios |
| `GET` | `/api/scenario/{id}` | Creator profile + guidelines |
| `POST` | `/api/match` | **Run agents** — SSE stream |
| `GET` | `/` | Frontend |

### SSE Event Flow

```mermaid
flowchart LR
    E1[PROFILE_SCAN_START] --> E2["AUDIENCE_ANALYSIS +\nMETRICS_ANALYSIS (concurrent)"]
    E2 --> E3[FIT_ASSESSMENT] --> E4[LEDGER_READ]
    E4 --> E5["GUIDELINE_SCAN\n(chunks scanned concurrently)"] --> E6[SECTION_MATCH]
    E6 --> E7[FLEXIBILITY_ANALYSIS] --> E8[MATCH_PATHWAY_DETERMINATION]
    E8 --> E9[FINAL_DETERMINATION] --> E10[PROCESS_COMPLETE]

    style E1 fill:#1b4332,stroke:#40916c,color:#fff
    style E10 fill:#0f3460,stroke:#e94560,color:#fff
```

Each event is a typed `LedgerEntry`:

```typescript
interface LedgerEntry {
  id:         string
  source:     "advisor" | "match" | "ledger" | "system"
  event_type: string
  message:    string                  // human-readable
  data:       Record<string, any>     // structured payload
  timestamp:  string                  // ISO 8601, UTC
  severity:   "normal" | "high" | "critical"
  tags:       string[]
}
```

> 📄 Full API examples and custom payload schema → [`docs/api.md`](docs/api.md)

---

## 📁 Project Structure

```
creator-collab-coordinator/
├── main.py                       # FastAPI server + SSE streaming
├── agents/
│   ├── advisor_agent.py          # Creator-centric analysis → writes to Ledger (concurrent sub-steps)
│   ├── match_agent.py            # Brand-centric matching → reads from Ledger (concurrent chunk scan)
│   ├── coordinator.py            # CampaignCoordinator orchestration (sequential phases)
│   └── llm_utils.py              # Shared JSON-repair + retry/backoff wrapper for all LLM calls
├── memory/
│   └── ledger.py                 # CollaborationLedger — shared async memory
├── models/
│   └── schemas.py                # Pydantic: CreatorProfile, LedgerEntry, etc.
├── data/
│   ├── creator_profile_fashion_influencer.json
│   ├── creator_profile_tech_educator.json
│   └── collaboration_guidelines.txt
├── static/
│   └── index.html                # Frontend — no build step
├── tests/
│   ├── test_ledger.py            # CollaborationLedger unit tests
│   ├── test_llm_utils.py         # JSON-repair + retry/backoff tests
│   ├── test_api.py               # Full mocked end-to-end pipeline + endpoint tests
│   └── fake_openai.py            # Scripted fake OpenAI client used by the tests above
├── pytest.ini
├── .env.example                  # Copy to .env to auto-load OPENAI_API_KEY
├── assets/                       # Screenshots + demo video
└── docs/
    └── api.md                    # Full API reference + custom payload examples
```

---

## 🛠️ Stack

```mermaid
flowchart LR
    subgraph BE["Backend"]
        B1[FastAPI] --- B2[Pydantic v2] --- B3[asyncio · Python 3.11+]
    end
    subgraph AI["AI Layer"]
        A1[OpenAI GPT-4o-mini] --- A2[Structured prompting + retry/backoff]
    end
    subgraph FE["Frontend"]
        F1[Vanilla HTML/JS] --- F2[SSE · No build step]
    end
    subgraph MEM["Memory"]
        M1[CollaborationLedger] --- M2[Redis-swappable]
    end
    subgraph TEST["Testing"]
        T1[pytest] --- T2[Fake OpenAI client · no network calls]
    end
    BE <--> AI
    BE <--> FE
    BE <--> MEM
    TEST -.-> BE
```

---

## 🏭 Built For

| Persona | Use Case |
|---|---|
| **Brand Partnership Teams** | Upload brief → get a structured match decision with cited rationale in minutes |
| **Creator Agencies** | Run your roster against multiple briefs; ledger becomes an exportable audit document |
| **AI/ML Engineers** | Reference implementation of structured multi-agent collaboration via shared state |
| **Hackathon Judges** | End-to-end demo with real agent reasoning, live streaming, and explainable outcomes |

---

<div align="center">

**Built for teams who want AI to *explain* its decisions — not just generate another list of names.**

<br/>

*Made with ⭐ and structured shared memory*

</div>