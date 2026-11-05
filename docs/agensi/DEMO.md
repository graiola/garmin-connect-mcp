# Synthetic demonstration

This is a real skill-guided response to an explicitly synthetic input, not a live
Garmin account test or a customer testimonial. The raw fixture is in
[demo-input.json](demo-input.json). Its payload keys are illustrative and do not
promise Garmin's current field names or response schema. No personal measurements
were used. Retain this disclosure when copying the example into Agensi.

## Request

Summarize these three activities from the supplied synthetic connector result.
Compare moving and elapsed time where available, and tell me what is missing.
Do not access a live account.

## Complete response

**Synthetic demonstration — no live Garmin account accessed.**

The supplied run has a **2-minute gap** between moving and elapsed time; the swim
has an **11-minute gap**. Strength training includes elapsed time only, so its
moving-time gap cannot be calculated.

Dates shown are the supplied `calendarDate` values, **2–4 November 2026**. The
example's configured timezone is **Europe/Rome**; its synthetic retrieval timestamp
is **5 November 2026, 12:00 UTC**, not the activity time.

| Date | Activity | Distance | Moving time | Elapsed time | Elapsed − moving |
|---|---|---:|---:|---:|---:|
| 4 Nov 2026 | Running | 6,000 m | 31:00 | 33:00 | 2:00 |
| 3 Nov 2026 | Lap swimming | 1,200 m | 24:00 | 35:00 | 11:00 |
| 2 Nov 2026 | Strength training | Not supplied | Not supplied | 45:00 | Cannot calculate |

Times are **minutes:seconds**, converted from explicitly labelled seconds. The
final column is a calculation, not a supplied rest measurement. These gaps alone
do not establish why time was excluded from moving duration or whether the swim
was continuous or interval-based.

Total elapsed time is **1 hour 53 minutes across all three activities**. Known
moving time totals **55 minutes across two activities**; a three-activity moving
total is unavailable.

Missing from the supplied records:

- Strength moving duration and distance.
- Heart rate, splits/laps, rest segments and swimming stroke details.
- Strength exercise names, performed sets, repetitions and weights.

"Not supplied" does not mean zero or that Garmin cannot hold the information.
Coverage is limited to these **three distinct synthetic activities**; it does not
establish a complete activity history. The example's payload keys are illustrative,
not a guaranteed Garmin response schema.
