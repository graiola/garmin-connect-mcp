# Verified API contract and provenance

Verification date: **2026-11-05**. No live user account was queried.

Primary sources:

- Garmin Personal API: https://developer.garmin.com/gc-developer-program/personal/personal-api/
- FAQ: https://developer.garmin.com/gc-developer-program/personal/personal-faq/
- Swagger entry: https://developer.garmin.com/gc-developer-program/personal/swagger-docs/
- Official client: https://github.com/garmin/connect-personal-api-python
- Source revision inspected: `ac111a0ff8e37dfbc24c616fcc27691520c7278b`
  - `src/garmin_personal_api/client.py`
  - `src/garmin_personal_api/auth.py`

This project is an independently implemented HTTP/MCP adapter. It does not copy
or vendor Garmin's Python client. API paths and exchange behavior below follow
that official reference; mock tests assert these paths.

## Authentication

Base origin is fixed: `https://personal.connectapi.garmin.com`.

`POST /personalapitoken-service/personal-api/personal-api-key/token`
uses `Authorization: ApiKey <personal-key>`. The official reference reads the
response as a raw JWT string, extracts `exp` for renewal scheduling, then uses
`Authorization: Bearer <token>` for data reads. Garmin documents 24-hour access
tokens or earlier personal-key expiry and no refresh tokens.

This adapter keeps the token in memory, renews before expiry, retries once on 401,
and also accepts JSON-string/access_token response shapes defensively. These
compatibility shapes are not a claim that Garmin currently emits them.

## Exposed data paths

| Tool/data | Path | Query |
|---|---|---|
| Activity list | `/activitylist-service/activities/search/activities` | start, limit, optional startDate/endDate/activityType |
| Activity detail | `/activity-service/activity/{id}` | — |
| Associated workouts | `/activity-service/activity/{id}/workouts` | — |
| Weight | `/weight-service/weight/range/{start}/{end}` | includeAll=true |
| Steps | `/usersummary-service/stats/steps/daily/{start}/{end}` | — |
| Stress | `/usersummary-service/stats/stress/daily/{start}/{end}` | — |
| Sleep summaries | `/sleep-service/sleep/dailySleepSummariesByDate` | startDate, endDate |
| Sleep detail | `/sleep-service/sleep/dailySleep` | date |
| HRV summaries | `/hrv-service/hrv/daily/{start}/{end}` | — |
| HRV detail | `/hrv-service/hrv/{date}` | — |
| Body Battery | `/wellness-service/wellness/bodyBattery/reports/daily` | startDate, endDate |
| Daily summary | `/usersummary-service/v2/dailysummaries` | startDate, endDate |
| Heart-rate detail | `/wellness-service/wellness/dailyHeartRate` | date |

No endpoint requiring a guessed Garmin display name is used. No writes to workout
plans, courses, training calendars or account settings are supported.

## Intentional limits

The official client also has download/profile and other health methods. They are
not automatically exposed here: use a minimal collection of useful personal tools.
No general `get_url`, no local filesystem read tool, no user-supplied API base URL.
No FIT decoding, workout editing or guaranteed per-set strength/swim details.
An empty/404/403 response is reported, not filled with guessed or stale values.

Raw JSON shapes and units are preserved, apart from explicit privacy filtering.
Garmin can change response coverage. Validate one real strength and one real swim
activity before treating this as a replacement for detailed Connect exports.

## MCP contract

- https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools

Tools-only implementation supports initialize, ping, tools/list, tools/call and
notifications. Negotiated versions: 2025-11-25, 2025-06-18, 2025-03-26.
HTTP returns JSON instead of SSE, which is permitted for Streamable HTTP. No
MCP-Session-Id is issued. GET and DELETE on `/mcp` return 405. Requests without a
protocol header use the spec's backward-compatible 2025-03-26 default. This is not
a complete SDK implementation: no server-initiated requests, prompts, resources,
subscriptions, tasks, or cancellation of in-progress serial stdio calls.
