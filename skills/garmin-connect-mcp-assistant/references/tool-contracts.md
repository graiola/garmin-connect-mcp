# Connector contract

Reference target: `graiola/garmin-connect-mcp` version `0.2.0`.
Check the connected server's schemas for changes. A host may prefix tool names;
match by the tool's advertised purpose and input schema, not a guessed namespace.

## Inputs

All tool argument objects reject additional properties. Dates use `YYYY-MM-DD`.
Do not pass secrets, URLs, user identifiers, units or unsupported filters.

| Tool | Accepted arguments |
|---|---|
| `garmin_connector_status` | `{}` |
| `garmin_list_activities` | Optional `start_date`, `end_date`, `activity_type`; integer `offset` default 0, range 0–10000; integer `limit` default 20, range 1–50 |
| `garmin_get_activity` | Required integer `activity_id`, range 1–9223372036854775807 |
| `garmin_get_activity_workouts` | Required integer `activity_id`, same range |
| `garmin_get_health_range` | Required `start_date`, `end_date`, `metric`; ordered range of at most 31 inclusive days |
| `garmin_get_day_detail` | Required `date`, `metric` |

Health-range metrics: `weight`, `steps`, `stress`, `sleep`, `hrv`, `body_battery`,
`daily_summary`. Day-detail metrics: `sleep`, `hrv`, `heart_rate`. These are
different enumerations: `heart_rate` is not a range metric, and `weight` is not a
day-detail metric. Use a one-day health range for a day's weight or steps.

Activity-type keys are lowercase Garmin keys, for example `running`,
`lap_swimming`, `strength_training`; they are not exercise names. The validated
syntax is a lowercase letter followed by up to 63 lowercase letters, digits or
underscores. Syntax acceptance does not prove the key exists in Garmin. Infer no
extra types; use a returned type key or omit the optional filter when uncertain.

Activity date filters are optional, but when both are supplied, start must not
follow end. The 31-day cap applies to health ranges, not activity listings.
The server does not automatically page, split ranges or normalize timestamps.

## Output envelope

Successful tool responses expose equivalent JSON in `structuredContent` and the
text content. Consume one, not both. The envelope contains:

- `source`: `Garmin Connect Personal API` (also present for local status).
- `retrieved_at`: UTC ISO timestamp of the tool result, not the measurement time.
- `timezone`: connector configuration, default `Europe/Rome`.
- `data`: original upstream JSON after selected privacy filtering; may be null,
  an array or an object. Inner field names and shapes vary by endpoint.
- `notes`: data-integrity and privacy cautions.

Do not interpret `source` as proof of an upstream request. Status makes no Garmin
call: its `data` reports `version`, `read_only`, `garmin_authenticated` set to
`not_checked`, local `today`, `tools`, and `fit_decoding: false`.
There are no normalized activity, weight or sleep schemas supplied by this skill.
Use the actual payload and authoritative field definitions; never assume a unit.

`GARMIN_MCP_TIMEZONE` affects local `today` and metadata. It does not convert Garmin
timestamps or reinterpret supplied date filters. Preserve Garmin calendar dates,
and distinguish them from UTC retrieval timestamps.

## Boundaries and errors

| Result | Response |
|---|---|
| Local status succeeds | Connector is callable; Garmin authentication is still untested |
| Local `doctor` succeeds | Authentication and one activity endpoint passed; agent connection and other endpoints remain untested |
| Tool `isError: true` | Read failed; do not render it as zero records |
| JSON-RPC invalid parameters | Check the advertised schema and correct only the invalid arguments |
| Missing/expired API key or upstream authentication failure | Ask the user to configure/rotate the key locally; never request it in chat |
| Permission denial | Stop; do not fall back to scraping or another account |
| HTTP 429/rate-limit message | Stop and wait for a later user-directed retry; do not run a retry loop |
| Timeout, upstream failure or oversized result | Report partial coverage; offer a narrower request when appropriate |
| 204 / empty array / empty object | Report no returned measurement for that request, not a measured zero |

The transport may surface errors as sanitized text without a numeric HTTP code.
Do not infer an exact cause or permissions change from a generic error.
The server caps a tool result at 512 KiB and upstream responses at 2 MiB by default.
It admits at most four concurrent calls, each with a 45-second execution timeout
after admission; time waiting for that concurrency slot is not included.
Do not exploit those limits to pull an entire account by default.

The server cannot edit/delete/upload activities, create workouts, decode/download
FIT files, browse arbitrary URLs or read arbitrary local files. Its local HTTP
transport is loopback-only and requires a bearer token independent of the Garmin
key; it is not an OAuth authorization server or a public multi-user service.
