## ⭐ Creator Collaboration Coordinator

**Multi-Agent Brand–Creator Collaboration Platform with Shared Memory**

Two AI agents (Advisor + Match) collaborate through a shared **Collaboration Ledger** to help brands find the right creators, justify decisions, and move from brief to signed collaboration in a fraction of the usual time.

---

### 🏗 Architecture

```text
┌───────────────────┐    ┌───────────────────────────────┐    ┌───────────────────┐
│   Advisor Agent    │───▶│     Collaboration Ledger      │◀───│    Match Agent     │
│ (creator-centric)  │    │        (Shared Memory)        │    │  (brand-centric)   │
│ • Reads profiles   │    │ • Thread-safe async store     │    │ • Reads ledger     │
│ • Scores fit       │    │ • Event-driven subscribers    │    │ • Matches to brief │
│ • Surfaces risks   │    │ • Query interface             │    │ • Proposes pathway │
└───────────────────┘    └───────────────────────────────┘    └───────────────────┘
                                     │
                                     ▼
                         ┌────────────────────────┐
                         │   Match Determination  │
                         │  MATCHED / CONDITIONAL │
                         │  / DECLINED / REVIEW   │
                         └────────────────────────┘
```

#### The Shared Memory USP

This isn’t two agents working independently. The **Collaboration Ledger** is a structured, event-driven shared memory where:

1. **Advisor Agent** analyzes the creator profile and writes structured findings (audience, performance, risk flags, strengths).
2. **Match Agent** reads the ledger and **adapts its behavior** based on what the Advisor Agent found and what the brand brief requires.
3. For strong fits, the system can fast‑track decisions; for edge cases, it routes to “PENDING_REVIEW” with a clear audit trail.

This is the core innovation — agents genuinely collaborate through shared state instead of passing around opaque text blobs.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- An OpenAI API key (`OPENAI_API_KEY`)

### Setup

```bash
# 1. Clone / unzip the project
cd creator-collab-coordinator

# 2. Create virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-key-here"
# macOS / Linux
export OPENAI_API_KEY="sk-your-key-here"

# 5. Run the server
python main.py
```

Open `http://localhost:8000` in your browser to view the web UI.

---

## 🎮 Demo Scenarios

The repo ships with two sample creator profiles and a long-form collaboration guideline document:

- **Fashion Influencer — Sofia Romero**
  - Sustainable fashion creator on Instagram with ~450K followers and ~8.2% engagement.
  - Great for brands launching eco-conscious lines or circular fashion drops.

- **Tech Educator — Marcus Chen**
  - Tech education creator on YouTube with ~280K subscribers and ~72% average video completion.
  - Ideal for developer tools, SaaS onboarding, and complex product education.

The **Match Agent** reads the same collaboration guidelines for both creators but behaves differently because the **Advisor Agent** has written different strengths, risks, and audience fit signals into the Collaboration Ledger.

---

## 📁 Project Structure

```text
creator-collab-coordinator/
├── main.py                 # FastAPI server + SSE streaming
├── agents/
│   ├── advisor_agent.py    # Creator-centric Advisor Agent
│   ├── match_agent.py      # Brand-centric Match Agent (shared context)
│   └── coordinator.py      # CampaignCoordinator orchestration layer
├── memory/
│   └── ledger.py           # CollaborationLedger (shared memory)
├── models/
│   └── schemas.py          # Pydantic data models (CreatorProfile, etc.)
├── data/
│   ├── creator_profile_fashion_influencer.json   # Sample: Sofia Romero
│   ├── creator_profile_tech_educator.json        # Sample: Marcus Chen
│   └── collaboration_guidelines.txt              # 1000+ word framework
├── static/
│   └── index.html          # Frontend (no build step needed)
├── requirements.txt
└── README.md
```

> Note: Some filenames/classes may still carry legacy names (`policy_agent.py`, etc.) but their role in the new architecture is “Match Agent” / brand-side reasoning.

---

## 🔧 API Surface

### REST Endpoints

| Method | Endpoint              | Description                                              |
|--------|-----------------------|----------------------------------------------------------|
| `GET`  | `/api/campaigns`      | List available sample collaboration scenarios           |
| `GET`  | `/api/scenario/{id}`  | Get creator profile + full collaboration guidelines     |
| `GET`  | `/api/guidelines`     | Fetch the full collaboration guidelines text            |
| `POST` | `/api/match`          | Run Advisor + Match Agents (SSE streaming of ledger)    |
| `GET`  | `/`                   | Serve the frontend                                       |

### Streaming (`/api/match`)

`/api/match` streams events as **Server-Sent Events** (SSE). The frontend subscribes and renders entries in real time from the Collaboration Ledger.

Common event types include:

- `PROFILE_ANALYSIS` — Advisor Agent analyzing creator profile.
- `FIT_SCORING` — Advisor Agent writing structured fit metrics to the ledger.
- `LEDGER_READ` — Match Agent reading shared memory.
- `REQUIREMENT_MATCH` — Match Agent matching brand requirements to creator signals.
- `SECTION_MATCH` — Specific collaboration guideline sections cited.
- `PATHWAY_DETERMINATION` — Final match pathway proposed.
- `PROCESS_COMPLETE` — Overall result (MATCHED / CONDITIONAL / DECLINED / PENDING_REVIEW).

Each event includes:

- `source` — `advisor`, `match`, `ledger`, or `system`.
- `event_type` — structured event name.
- `message` — human-readable summary for the UI.
- `data` — structured payload, suitable for programmatic consumption.

---

## 🧪 Custom Data

You can also use your own creator profiles and brand guidelines.

### Via the UI

On the landing page:

1. **Upload Creator Profile (JSON)** — matches the `CreatorProfile` schema.
2. **Upload Brand Guidelines (TXT/PDF)** — long-form copy describing tiers, constraints, and fast-track rules.

The UI will send these as a `CollaborationRequest` into `/api/match` and stream the Advisor/Match interaction, just like the samples.

### Via the API

POST directly to `/api/match` with a JSON body that matches `CollaborationRequest`:

```json
{
  "creator_profile": {
    "creator_name": "Example Creator",
    "creator_follower_count": 120000,
    "creator_primary_platform": "TikTok",
    "creator_specialty": "Beauty tutorials",
    "...": "other CreatorProfile fields"
  },
  "brand_guidelines": "Full text of your collaboration framework...",
  "brand_name": "Your Brand",
  "brand_id": "INTERNAL-ID-123"
}
```

---

## 💡 Technical Highlights

- **Multi-agent orchestration** — Advisor + Match Agents coordinated by a `CampaignCoordinator`.
- **True shared memory** — `CollaborationLedger` is a thread-safe async store with subscribers, not just ad-hoc globals.
- **Structured reasoning** — Both agents write structured events (`LedgerEntry`) with `source`, `tags`, `severity`, and typed `data`.
- **SSE streaming UI** — The frontend renders ledger events in real time, making the agent reasoning legible to humans.
- **Modern Python stack** — FastAPI, Pydantic models, async/await, and OpenAI’s Python client (`>=1.0.0,<2.0.0`).

---

## 📊 Why This Matters for Brands

Traditional creator selection is:

- Spreadsheet-heavy
- Opaque (“someone decided this in a meeting”)
- Hard to audit after the fact

With the Creator Collaboration Coordinator:

- **Faster** — briefs can move from idea to recommended creators in minutes.
- **Safer** — values alignment, brand safety, and performance history are explicit in the ledger.
- **More explainable** — every match, conditional approval, or decline carries a structured rationale.
- **More scalable** — the same playbook can be reused and tuned across markets and teams.

---

Built for brand and creator teams who want AI to *explain* its decisions—not just generate another list of names.```json
