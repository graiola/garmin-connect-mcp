# Read-only workflows

Contents: [Activities](#find-and-summarize-activities),
[Swimming](#compare-swimming-sessions), [Strength](#inspect-strength-training),
[Trends](#read-a-trend), [Day detail](#inspect-one-day), [Answer](#write-the-answer).

Use the examples as input-contract illustrations, not fixed dates or fabricated
results. Substitute dates/IDs grounded in the user's request or actual tool output.

## Find and summarize activities

1. Use explicit dates when the user provided them. Resolve relative dates with
   status and state the inclusive window/timezone.
2. Request only enough records for the question. A starting call for three recent
   sessions is `garmin_list_activities({"limit": 3, "offset": 0})`.
3. Inspect returned timestamps and type keys; do not invent a field schema or
   assume that sorting the returned page proves it covers the whole period.
4. Fetch detail only for activities needed to answer the question. Activity IDs
   must come from the user or an actual response.
5. Report measurements that exist. Avoid unnecessary activity titles or notes.

Example call:

```json
{"tool":"garmin_list_activities","arguments":{"start_date":"2026-10-26","end_date":"2026-11-01","activity_type":"running","offset":0,"limit":20}}
```

For a complete selected-period report, advance `offset` by the requested `limit`.
Stop when a page contains fewer records than requested. If a full page returns no
new activity IDs, or the response shape cannot be confidently paged, stop and
explain the incomplete coverage. Deduplicate by activity ID. Never go past offset
10000. Respect the skill's ten-data-read budget before asking to continue.

## Compare swimming sessions

Fetch each requested activity's details. Retain separate moving and elapsed
durations. Rest-inclusive pace and moving pace answer different questions; label
them separately and compute only with known distance/time units and nonzero
distance. A fast moving pace with long rest does not establish sustained ability.
Only discuss laps, interval structure, stroke or rest segments if supplied.

Example call (the ID must first be supplied or discovered):

```json
{"tool":"garmin_get_activity","arguments":{"activity_id":12345}}
```

## Inspect strength training

Fetch the activity, then associated workouts only when relevant:

```json
{"tool":"garmin_get_activity_workouts","arguments":{"activity_id":12345}}
```

The associated-workouts endpoint may describe a plan rather than performed sets.
Do not relabel planned values as executed work. Empty or absent sets, edited names,
weights or repetitions are not recoverable by this connector. Say what was returned
and what is missing. Suggest checking Garmin Connect or a user-provided export;
do not promise that a FIT file exists or that this server can download/decode it.
Compare loads only when exercise, unit, machine and execution context are known.

## Read a trend

Choose the metric actually requested, then request no more than 31 inclusive days:

```json
{"tool":"garmin_get_health_range","arguments":{"metric":"steps","start_date":"2026-10-26","end_date":"2026-11-01"}}
```

For 1 September through 5 November 2026, contiguous non-overlapping valid windows
are 1 September–1 October, 2 October–1 November, and 2–5 November. Do not reuse the
previous end date as the next start. Do not silently fetch all seven metrics.

Report requested days, distinct observed days, missing days and incomplete current
days. A mean over observed days must use that observed-day denominator, not the
full requested range. For multiple same-day readings, preserve raw readings or
declare a daily aggregation such as the daily median before averaging daily values.
For weekly comparisons, use equivalent calendar windows and a common known unit.
If data is missing, compare like-for-like coverage or explicitly qualify the result.

Weight/BIA, sleep scores, stress and Body Battery are device estimates. A trend
alone does not establish a diagnosis, fitness clearance or actual tissue changes.
Do not treat zero, negative sentinels, missing or null as interchangeable; apply
an endpoint's sentinel rules only if verified. Otherwise flag ambiguous values.

## Inspect one day

Use the dedicated tool only for its three supported detail metrics:

```json
{"tool":"garmin_get_day_detail","arguments":{"metric":"hrv","date":"2026-11-01"}}
```

For a single day's weight, use `garmin_get_health_range` with equal start/end dates.
For heart rate across several days, explain that only day detail is available,
then read only the necessary days within the budget. Do not invent a heart-rate
range metric. Do not equate a recording timestamp with a calendar day without
considering its timezone.

## Write the answer

Use a concise structure, adapting to the request:

1. Direct answer and chosen period/timezone.
2. Available measurements and clearly labelled calculations.
3. Coverage: returned records or observed days, gaps and partial pages/windows.
4. Limits that change the interpretation and, only when useful, the next read.

Do not fill a table with invented values to make it look complete. If no read was
possible, state that clearly and give the relevant connection or authentication
step rather than generating a plausible fitness report.
