# 📄 API Reference — Creator Collaboration Coordinator

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe — also reports whether `OPENAI_API_KEY` is configured |
| `GET` | `/api/campaigns` | List available demo scenarios |
| `GET` | `/api/scenario/{id}` | Get creator profile + collaboration guidelines |
| `GET` | `/api/guidelines` | Fetch full guidelines text |
| `POST` | `/api/match` | Run Advisor + Match Agents (SSE stream) |
| `GET` | `/` | Serve the frontend |

---

## POST `/api/match`

Runs the full Advisor → Ledger → Match pipeline and streams results as Server-Sent Events.

### Request Body — `CollaborationRequest`

This mirrors the `CreatorProfile` Pydantic model in `models/schemas.py` exactly —
the sample files in `data/` are valid examples of this shape.

```json
{
  "creator_profile": {
    "creator_name": "Alex Rivera",
    "creator_follower_count": 180000,
    "creator_primary_platform": "TikTok",
    "creator_specialty": "Fitness & wellness",
    "focus_area": "Beginner-friendly strength training and habit-building content",
    "audience_demographics": [
      "Primary: 18-34, fitness-curious beginners",
      "55% US, 20% UK, 25% other English-speaking markets"
    ],
    "social_metrics": [
      {
        "name": "Average Engagement Rate",
        "value": "6.2",
        "unit": "%",
        "flag": "high",
        "reference_range": "3-5% typical for fitness creators at this scale"
      }
    ],
    "expertise_areas": [
      {
        "skill_id": "habit_building_101",
        "category": "EDUCATION",
        "description": "Breaks down behavior-change research into simple weekly challenges."
      }
    ],
    "proposed_deliverables": {
      "deliverable_id": "rivera_drop1",
      "category": "POST",
      "name": "30-Day Starter Program Launch",
      "brand_objective": "Drive app installs via a guided onboarding series."
    },
    "previous_collaborations": ["FitGear Co. — 8-week transformation series"],
    "bio": "Alex turns exercise science into approachable daily routines."
  },
  "brand_guidelines": "Full text of your collaboration framework...",
  "brand_name": "AthletiCo",
  "brand_id": "ATHLETICO-001"
}
```

Only `creator_name`, `creator_follower_count`, `creator_primary_platform`,
`creator_specialty`, and `brand_guidelines` are required — every other field
has a default (empty string/list/`None`) so partial profiles still validate.

### Example curl

```bash
curl -N -X POST http://localhost:8000/api/match \
  -H "Content-Type: application/json" \
  -d '{
    "creator_profile": {
      "creator_name": "Alex Rivera",
      "creator_follower_count": 180000,
      "creator_primary_platform": "TikTok",
      "creator_specialty": "Fitness & wellness"
    },
    "brand_guidelines": "We partner with creators who...",
    "brand_name": "AthletiCo",
    "brand_id": "ATHLETICO-001"
  }'
```

(`-N` disables curl's output buffering so you see SSE events as they arrive
instead of all at once at the end.)

---

## SSE Event Schema — `LedgerEntry`

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

The stream also emits two control frames that aren't `LedgerEntry`s:

- `event: result` — sent once, right before the stream ends, carrying the
  full pipeline output: `{ advisor_analysis, match_analysis, determination, ledger }`.
  `determination` is the exact object the frontend's outcome panel renders —
  see the `MatchResult`-shaped fields below.
- `event: keepalive` — sent every 120s of inactivity so proxies don't time out the connection.
- `event: error` — sent if the pipeline raises an unrecoverable error.
- `event: done` — always sent last, signals the stream is finished.

### Real Event Taxonomy (as actually emitted by the agents)

| Event Type | Source | Description |
|---|---|---|
| `PROCESS_START` | `system` | Coordinator begins a new run |
| `PHASE_CHANGE` | `system` | Marks the start of the advisor / match / resolution phase |
| `PROFILE_SCAN_START` | `advisor` | Advisor begins reading the creator profile |
| `AUDIENCE_ANALYSIS` | `advisor` | Audience quality, segments, brand-fit signals (runs concurrently with metrics) |
| `METRICS_ANALYSIS` | `advisor` | Engagement/completion/save-rate metrics graded (runs concurrently with audience) |
| `FIT_ASSESSMENT` | `advisor` | Overall creator–brand fit scored and tagged |
| `ADVISOR_CONTEXT_COMPLETE` | `advisor` | Advisor's findings committed to shared ledger context |
| `LEDGER_READ` | `match` | Match Agent reads the Advisor's shared context |
| `GUIDELINE_SCAN` | `match` | Guideline document chunks scanned (concurrently) for relevant sections |
| `SECTION_MATCH` | `match` | A specific guideline section cited (tagged `FLEXIBILITY_CLAUSE` if applicable) |
| `FLEXIBILITY_ANALYSIS` | `match` | Evaluates whether flexible/fast-track clauses are satisfied |
| `MATCH_PATHWAY_DETERMINATION` | `match` | Recommended pathway + status from the Match Agent |
| `MATCH_CONTEXT_COMPLETE` | `ledger` | Match Agent's findings committed to the ledger |
| `FINAL_DETERMINATION` | `system` | Final status/pathway synthesized from both agents |
| `PROCESS_COMPLETE` | `system` | Terminal event — `data` is the full `determination` object |
| `ERROR` | `system` | Emitted if any phase raises an unrecoverable exception |

---

## `CreatorProfile` Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `creator_name` | `string` | ✅ | Full display name |
| `creator_follower_count` | `int` | ✅ | Total followers/subscribers |
| `creator_primary_platform` | `string` | ✅ | Instagram / YouTube / TikTok / etc. |
| `creator_specialty` | `string` | ✅ | Content niche description |
| `focus_area` | `string` | – | One-line positioning statement |
| `audience_demographics` | `string[]` | – | Free-text demographic/values notes |
| `social_metrics` | `SocialMetric[]` | – | `{name, value, unit, flag, reference_range}` |
| `expertise_areas` | `ExpertiseArea[]` | – | `{skill_id, category, description}` |
| `proposed_deliverables` | `Deliverable \| null` | – | `{deliverable_id, category, name, brand_objective}` |
| `previous_collaborations` | `string[]` | – | Past brand partnerships |
| `bio` | `string` | – | Short creator bio |

## `MatchResult` / final `determination` Schema

This is what the frontend's outcome panel reads from the `event: result` payload's `determination` field:

| Field | Type | Description |
|---|---|---|
| `status` | `string` | One of `MATCHED`, `CONDITIONAL_MATCH`, `DECLINED`, `PENDING_REVIEW` |
| `pathway` | `string` | Recommended collaboration pathway (e.g. `FAST_TRACK`) |
| `determination_text` | `string` | Human-readable rationale |
| `reasoning` | `string` | Shorter internal reasoning summary |
| `confidence_score` | `float` | 0.0–1.0 |
| `collaboration_timeline` | `string` | Estimated turnaround |
| `expected_reach` | `string` | Estimated audience reach |
| `documentation_complete` | `bool` | Whether all required documentation was present |
| `missing_items` | `string[]` | Anything still needed for a full match |
| `appeal_guidance` | `string` | What to provide if the creator wants to contest the outcome |

> ⚠️ These are the exact keys the frontend (`static/index.html`'s `showOutcome()`)
> reads. If you add a new field upstream, update both sides — `tests/test_api.py`
> has a regression test (`test_full_match_pipeline_matched_outcome`) that checks
> this contract stays intact.
