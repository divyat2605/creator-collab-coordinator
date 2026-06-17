<div align="center">

```
 ██████╗██████╗ ███████╗ █████╗ ████████╗ ██████╗ ██████╗      ██████╗ ██████╗ ██╗      ██╗      █████╗ ██████╗ 
██╔════╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗    ██╔════╝██╔═══██╗██║      ██║     ██╔══██╗██╔══██╗
██║     ██████╔╝█████╗  ███████║   ██║   ██║   ██║██████╔╝    ██║     ██║   ██║██║      ██║     ███████║██████╔╝
██║     ██╔══██╗██╔══╝  ██╔══██║   ██║   ██║   ██║██╔══██╗    ██║     ██║   ██║██║      ██║     ██╔══██║██╔══██╗
╚██████╗██║  ██║███████╗██║  ██║   ██║   ╚██████╔╝██║  ██║    ╚██████╗╚██████╔╝███████╗ ███████╗██║  ██║██████╔╝
 ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝     ╚═════╝ ╚═════╝ ╚══════╝ ╚══════╝╚═╝  ╚═╝╚═════╝
```

# ⭐ Creator Collaboration Coordinator

**Multi-Agent Brand–Creator Matching Platform powered by Shared Memory**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT4-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![SSE Streaming](https://img.shields.io/badge/SSE-Streaming-FF6B35?style=for-the-badge&logo=apachekafka&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

> *Two AI agents collaborating through shared memory to match brands with creators — fast, transparently, and at scale.*

</div>

---

## 📸 Live Demo

> Below: The platform in action — Advisor Agent analyzing Sofia Romero's profile in real-time, with the Collaboration Ledger updating live and the Match Agent reading shared state.

| Landing Page | Advisor Agent Live | Fit Assessment | Match Agent Activates |
|:---:|:---:|:---:|:---:|
| ![Landing](assets/landingpage.png) | ![Advisor](assets/advisor_agent.png) | ![Fit](assets/fit_Assessment.png) | ![Match](assets/match_Agent_Activates.png) |
| Select scenario or upload custom data | Ledger populates in real-time with SSE | `STRONG_FIT` tagged within 14s | Match Agent reads shared state & reasons |

---

## 🧠 The Core Idea

Traditional influencer selection is **opaque, slow, and hard to audit**. Someone makes a gut call in a meeting. A spreadsheet gets emailed. No one knows why Creator A was picked over Creator B.

This platform makes AI reasoning **legible**:

```
Brief arrives → Advisor Agent analyzes creator → Writes structured findings to Ledger
                                                               ↓
                                            Match Agent reads Ledger + adapts behavior
                                                               ↓
                                          MATCHED / CONDITIONAL / DECLINED with full audit trail
```

The **Collaboration Ledger** is the innovation. It's not two agents passing opaque text blobs — it's **genuine shared state** with event types, severity flags, timestamps, and structured payloads that the Match Agent reads and reasons over before producing a decision.

---

## 🏗️ System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        CREATOR COLLABORATION COORDINATOR                            │
│                                                                                     │
│   ┌─────────────────┐         ┌──────────────────────────┐       ┌───────────────┐  │
│   │  Advisor Agent  │─────▶   │   Collaboration Ledger   │  ◀────│  Match Agent  │  │
│   │                 │  write  │     (Shared Memory)      │  read │               │  │
│   │  • Profile scan │         │                          │       │ • Reads ledger│  │
│   │  • Audience fit │         │  ┌──────────────────┐   │       │ • Maps brief  │  │
│   │  • Metric grade │         │  │ Thread-safe async│   │       │ • Determines  │  │
│   │  • Risk surface │         │  │ Event-driven     │   │       │   pathway     │  │
│   │  • Fit scoring  │         │  │ Query interface  │   │       │ • Cites rules │  │
│   └─────────────────┘         │  │ Subscriber model │   │       └───────────────┘  │
│           │                   │  └──────────────────┘   │               │           │
│           │                   └──────────────────────────┘               │           │
│           │                                │                              │           │
│           └──────────────── ORCHESTRATED BY CampaignCoordinator ─────────┘           │
│                                            │                                         │
│                                            ▼                                         │
│                              ┌─────────────────────────┐                            │
│                              │    Match Determination   │                            │
│                              │  ┌──────────────────┐   │                            │
│                              │  │ ✅ MATCHED        │   │                            │
│                              │  │ ⚡ CONDITIONAL    │   │                            │
│                              │  │ ❌ DECLINED       │   │                            │
│                              │  │ 🔍 PENDING_REVIEW │   │                            │
│                              │  └──────────────────┘   │                            │
│                              └─────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### SSE Streaming Pipeline

```
Browser                  FastAPI Server              Agents              OpenAI
  │                           │                        │                    │
  │──── POST /api/match ──────▶│                        │                    │
  │                           │──── spawn Advisor ─────▶│                    │
  │                           │                        │──── GPT-4 call ────▶│
  │◀── SSE: PROFILE_SCAN_START │◀─── yield event ───────│◀─── stream ────────│
  │◀── SSE: AUDIENCE_ANALYSIS  │◀─── ledger.write() ────│                    │
  │◀── SSE: METRICS_ANALYSIS   │                        │                    │
  │◀── SSE: FIT_ASSESSMENT     │──── spawn Match ────────▶│                   │
  │◀── SSE: LEDGER_READ        │◀─── ledger.read() ─────│                    │
  │◀── SSE: REQUIREMENT_MATCH  │◀─── yield event ───────│──── GPT-4 call ───▶│
  │◀── SSE: PATHWAY_DETERMINATION│                      │◀─── stream ────────│
  │◀── SSE: PROCESS_COMPLETE   │                        │                    │
```

### Agent Collaboration Model

```
  ╔═══════════════════════════════════════════════════════════════╗
  ║               WHY SHARED LEDGER > MESSAGE PASSING              ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║                                                               ║
  ║  ❌ Naive multi-agent (opaque text blobs):                    ║
  ║     Advisor → "Sofia is good" → Match → "OK, matched"        ║
  ║     No structure. No traceability. No adaption.              ║
  ║                                                               ║
  ║  ✅ Ledger-based (structured shared state):                   ║
  ║     Advisor writes → {                                        ║
  ║       event_type: "FIT_ASSESSMENT",                          ║
  ║       tags: ["STRONG_FIT", "sustainability"],                 ║
  ║       severity: "high",                                      ║
  ║       data: { fit_score: 0.91, risk_flags: [] }              ║
  ║     }                                                         ║
  ║     Match reads → adapts fast-track vs. review routing       ║
  ║     Humans can read the full audit trail                      ║
  ╚═══════════════════════════════════════════════════════════════╝
```

---

## ⚡ Architectural Tradeoffs

| Decision | Chosen Approach | Alternative | Why This Way |
|---|---|---|---|
| **Agent communication** | Shared Ledger (structured state) | Direct message passing | Full audit trail; Match Agent can query specific event types and reason over semantics, not just summarized text |
| **Streaming protocol** | Server-Sent Events (SSE) | WebSockets | SSE is unidirectional, simpler to implement, and sufficient — the client only needs to *receive* ledger events |
| **Orchestration** | `CampaignCoordinator` wrapper | Direct agent-to-agent calls | Clean separation of concerns; coordinator handles phasing, retries, and result aggregation |
| **Data modeling** | Pydantic schemas (`LedgerEntry`) | Raw dicts | Schema validation catches malformed agent outputs; enables typed queries on the ledger |
| **LLM calls** | Sequential (Advisor first, then Match) | Parallel | Match Agent's reasoning depends on Advisor's output — parallelism would defeat the shared memory model |
| **Frontend** | Single `index.html` (no build step) | React + Vite | Zero setup friction for demos; SSE rendering in vanilla JS is straightforward |
| **Memory model** | Async, thread-safe, in-process | Redis / external store | Reduces infra complexity for a demo; swap in Redis for multi-worker production deployments |

### Where This Architecture Shines

```
✅ Explainable AI decisions       — every step has a source, timestamp, and structured payload
✅ Human-in-the-loop ready        — PENDING_REVIEW routes edge cases to human review
✅ Auditable match rationale       — ledger is a first-class artifact, not a debug log
✅ Fast iteration on guidelines    — brands update TXT/PDF; no model retraining required
✅ Extensible event taxonomy       — add new event types without changing agent contracts
```

### Known Limitations & Future Work

```
⚠️  In-process ledger doesn't scale across workers → swap for Redis streams
⚠️  No persistent storage → add a database for historical match analytics
⚠️  Single-turn LLM calls → multi-turn reasoning would improve edge-case handling
⚠️  No creator consent/privacy layer → required before production use
⚠️  OpenAI-only → provider-agnostic via LiteLLM or similar
```

---

## 🚀 Quick Start

### Prerequisites

- Python **3.11+**
- An **OpenAI API key**

### Setup in 60 Seconds

```bash
# 1. Clone / unzip the project
cd creator-collab-coordinator

# 2. Create and activate virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
# macOS / Linux
export OPENAI_API_KEY="sk-your-key-here"

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-key-here"

# 5. Launch
python main.py
```

Open **`http://localhost:8000`** in your browser.

---

## 🎮 Demo Scenarios

The repo ships with two pre-built creator profiles and a 1000+ word collaboration guideline document. The Match Agent reads the **same guidelines** for both creators, but behaves differently because the Advisor Agent writes different findings into the ledger.

### Scenario 1 — Sofia Romero 🌿

```
Platform:    Instagram
Followers:   ~450K
Engagement:  8.2% avg (high)
Specialty:   Sustainable fashion & conscious lifestyle

Ledger Tags: AUDIENCE_ANALYSIS → STRONG_FIT → fast-track eligible
Best for:    Eco-conscious brands, circular fashion drops, ethical apparel launches
```

### Scenario 2 — Marcus Chen 💻

```
Platform:    YouTube
Subscribers: ~280K
Completion:  72% avg video completion (exceptional)
Specialty:   Tech education for beginner–intermediate audiences

Ledger Tags: AUDIENCE_ANALYSIS → EDUCATIONAL_FIT → brand safety verified
Best for:    Developer tools, SaaS onboarding, complex product explainers
```

---

## 📁 Project Structure

```
creator-collab-coordinator/
│
├── main.py                          # FastAPI server + SSE streaming endpoint
│
├── agents/
│   ├── advisor_agent.py             # Creator-centric Advisor Agent
│   │                                #   Writes: audience, metrics, fit, risk → Ledger
│   ├── match_agent.py               # Brand-centric Match Agent
│   │                                #   Reads: Ledger entries → maps to guidelines → decision
│   └── coordinator.py               # CampaignCoordinator orchestration layer
│                                    #   Phases: Advisor → Ledger → Match → Result
│
├── memory/
│   └── ledger.py                    # CollaborationLedger — thread-safe async shared memory
│                                    #   API: write(entry), read(filter), subscribe(event_type)
│
├── models/
│   └── schemas.py                   # Pydantic models
│                                    #   CreatorProfile, LedgerEntry, CollaborationRequest
│
├── data/
│   ├── creator_profile_fashion_influencer.json    # Sample: Sofia Romero
│   ├── creator_profile_tech_educator.json         # Sample: Marcus Chen
│   └── collaboration_guidelines.txt              # 1000+ word brand framework
│
├── static/
│   └── index.html                   # Frontend — no build step, pure SSE rendering
│
├── requirements.txt
└── README.md
```

---

## 🔧 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/campaigns` | List available demo scenarios |
| `GET` | `/api/scenario/{id}` | Get creator profile + collaboration guidelines |
| `GET` | `/api/guidelines` | Fetch full guidelines text |
| `POST` | `/api/match` | **Run Advisor + Match Agents** (SSE stream) |
| `GET` | `/` | Serve the frontend |

### SSE Event Taxonomy

`POST /api/match` streams **Server-Sent Events** in real time. Each event is a `LedgerEntry`:

```typescript
interface LedgerEntry {
  source:     "advisor" | "match" | "ledger" | "system"
  event_type: EventType
  message:    string           // human-readable for UI rendering
  data:       Record<string, any>  // structured payload for programmatic use
  timestamp:  number
  severity?:  "low" | "medium" | "high"
  tags?:      string[]
}
```

| Event Type | Source | Description |
|---|---|---|
| `PROFILE_SCAN_START` | `advisor` | Advisor begins reading creator profile |
| `AUDIENCE_ANALYSIS` | `advisor` | Audience quality, demographics, geographic spread |
| `METRICS_ANALYSIS` | `advisor` | Engagement, completion, save rates — graded |
| `FIT_ASSESSMENT` | `advisor` | Overall creator–brand fit scored and tagged |
| `RISK_FLAGS` | `advisor` | Brand safety, values alignment, past controversies |
| `LEDGER_READ` | `match` | Match Agent reads Advisor's findings |
| `REQUIREMENT_MATCH` | `match` | Mapping brand brief requirements to creator signals |
| `SECTION_MATCH` | `match` | Specific guideline sections cited for/against |
| `PATHWAY_DETERMINATION` | `match` | Proposed route: fast-track, conditional, review |
| `PROCESS_COMPLETE` | `system` | Final verdict with full structured rationale |

### Custom Data via API

```bash
curl -X POST http://localhost:8000/api/match \
  -H "Content-Type: application/json" \
  -d '{
    "creator_profile": {
      "creator_name": "Alex Rivera",
      "creator_follower_count": 180000,
      "creator_primary_platform": "TikTok",
      "creator_specialty": "Fitness & wellness",
      "creator_engagement_rate": 0.062,
      "creator_audience_demographics": {
        "age_primary": "18-34",
        "regions": ["US", "Canada"]
      }
    },
    "brand_guidelines": "Full text of your collaboration framework...",
    "brand_name": "AthletiCo",
    "brand_id": "ATHLETICO-001"
  }'
```

---

## 💡 Technical Highlights

### 1. True Shared Memory (Not Message Passing)

```python
# ledger.py — simplified
class CollaborationLedger:
    def __init__(self):
        self._entries: list[LedgerEntry] = []
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, list[Callable]] = {}

    async def write(self, entry: LedgerEntry):
        async with self._lock:
            self._entries.append(entry)
            await self._notify_subscribers(entry)  # event-driven

    async def query(self, event_type: str | None = None, tags: list[str] | None = None):
        # Match Agent can filter: "show me all FIT_ASSESSMENT entries tagged STRONG_FIT"
        return [e for e in self._entries if matches(e, event_type, tags)]
```

### 2. Structured Agent Reasoning

```python
# advisor_agent.py — the Advisor doesn't just narrate, it writes typed findings
await ledger.write(LedgerEntry(
    source="advisor",
    event_type="FIT_ASSESSMENT",
    message="Fit assessment: STRONG_FIT. Sofia Romero's expertise in sustainable fashion...",
    tags=["STRONG_FIT", "sustainability", "fast-track-eligible"],
    severity="high",
    data={
        "fit_score": 0.91,
        "fit_label": "STRONG_FIT",
        "risk_flags": [],
        "fast_track_eligible": True
    }
))
```

### 3. Match Agent Adapts to Ledger State

```python
# match_agent.py — Match Agent behavior changes based on what Advisor wrote
fit_entries = await ledger.query(event_type="FIT_ASSESSMENT")
if fit_entries[0].data.get("fast_track_eligible"):
    # Skip extended review → write PATHWAY: FAST_TRACK
else:
    # Route to PENDING_REVIEW with flagged concerns
```

---

## 📊 Why This Matters for Brands

```
Traditional creator selection         Creator Collaboration Coordinator
─────────────────────────────────     ──────────────────────────────────────
❌ Spreadsheet-heavy                  ✅ Automated analysis in minutes
❌ Opaque decisions ("someone         ✅ Full audit trail — every match,
   decided in a meeting")                conditional, or decline has
❌ Hard to audit after the fact          structured rationale in the Ledger
❌ Difficult to scale across          ✅ Same playbook reusable across
   teams and markets                     markets and teams
❌ No structured risk assessment      ✅ Values alignment, brand safety,
                                         and performance graded explicitly
```

---

## 🏭 Built For

| Role | How You Use It |
|---|---|
| **Brand Partnership Teams** | Upload your collaboration brief (TXT/PDF), select a creator, get a structured match decision with cited rationale in minutes |
| **Creator Agencies** | Run your creator roster against multiple brand briefs; the ledger becomes an exportable audit document |
| **AI/ML Engineers** | Study the Advisor → Ledger → Match pattern as a reference implementation of structured multi-agent collaboration |
| **Product Managers** | Prototype AI-assisted workflows for any domain that involves structured matching (jobs, products, services) |

---

## 🛠️ Stack

```
Backend     FastAPI · Pydantic · asyncio · Python 3.11+
LLM         OpenAI Python Client >=1.0.0,<2.0.0 (GPT-4)
Streaming   Server-Sent Events (SSE) via FastAPI StreamingResponse
Frontend    Vanilla HTML/JS — zero build step
Memory      In-process async CollaborationLedger (Redis-swappable)
Validation  Pydantic v2 models for all agent I/O
```

---

<div align="center">

**Built for brand and creator teams who want AI to *explain* its decisions — not just generate another list of names.**

---

*Made with ⭐ and structured shared memory*

</div>