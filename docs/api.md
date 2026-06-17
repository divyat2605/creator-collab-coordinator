# 📄 API Reference — Creator Collaboration Coordinator

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/campaigns` | List available demo scenarios |
| `GET` | `/api/scenario/{id}` | Get creator profile + collaboration guidelines |
| `GET` | `/api/guidelines` | Fetch full guidelines text |
| `POST` | `/api/match` | Run Advisor + Match Agents (SSE stream) |
| `GET` | `/` | Serve the frontend |

---

## POST `/api/match`

Runs the full Advisor → Ledger → Match pipeline and streams results as Server-Sent Events.

### Request Body — `CollaborationRequest`

```json
{
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
}
```

### Example curl

```bash
curl -X POST http://localhost:8000/api/match \
  -H "Content-Type: application/json" \
  -d '{
    "creator_profile": {
      "creator_name": "Alex Rivera",
      "creator_follower_count": 180000,
      "creator_primary_platform": "TikTok",
      "creator_specialty": "Fitness & wellness",
      "creator_engagement_rate": 0.062
    },
    "brand_guidelines": "We partner with creators who...",
    "brand_name": "AthletiCo",
    "brand_id": "ATHLETICO-001"
  }'
```

---

## SSE Event Schema — `LedgerEntry`

```typescript
interface LedgerEntry {
  source:     "advisor" | "match" | "ledger" | "system"
  event_type: string
  message:    string
  data:       Record<string, any>
  timestamp:  number
  severity?:  "low" | "medium" | "high"
  tags?:      string[]
}
```

### Full Event Taxonomy

| Event Type | Source | Description |
|---|---|---|
| `PROFILE_SCAN_START` | `advisor` | Advisor begins reading creator profile |
| `AUDIENCE_ANALYSIS` | `advisor` | Audience quality, demographics, geographic spread |
| `METRICS_ANALYSIS` | `advisor` | Engagement, completion, save rates — graded |
| `FIT_ASSESSMENT` | `advisor` | Overall creator–brand fit scored and tagged |
| `RISK_FLAGS` | `advisor` | Brand safety, values alignment, past controversies |
| `LEDGER_READ` | `match` | Match Agent reads Advisor's findings |
| `REQUIREMENT_MATCH` | `match` | Brand brief requirements mapped to creator signals |
| `SECTION_MATCH` | `match` | Specific guideline sections cited for/against |
| `PATHWAY_DETERMINATION` | `match` | Proposed route: fast-track, conditional, review |
| `PROCESS_COMPLETE` | `system` | Final verdict with structured rationale |

---

## CreatorProfile Schema

| Field | Type | Description |
|---|---|---|
| `creator_name` | `string` | Full display name |
| `creator_follower_count` | `int` | Total followers/subscribers |
| `creator_primary_platform` | `string` | Instagram / YouTube / TikTok / etc. |
| `creator_specialty` | `string` | Content niche description |
| `creator_engagement_rate` | `float` | Decimal (e.g. `0.082` = 8.2%) |
| `creator_audience_demographics` | `object` | Age, regions, values, device usage |