---
name: now
track: bonus
kind: local_knowledge
provider: system clock
requires_env: []
inputs: [timezone, timeframe]
outputs: [now_iso, date, weekday, timezone, resolved_range]
side_effect: false
---
# now

Returns the current date and time, and turns a relative `timeframe`
(`day` / `week` / `month` / `year`) into an explicit `resolved_range` with ISO
start and end dates.

Exists because the agent otherwise guesses at dates. Any request phrased as
"hôm nay" or "trong tuần này" needs a real anchor before a search timeframe can
be filled in correctly.

`zoneinfo` is tried first, but Windows ships no IANA tz database and `tzdata` is
not a project dependency, so the tool falls back to a fixed-offset table. Only
zones without DST are in that table, which keeps the fallback exact for
`Asia/Ho_Chi_Minh` (UTC+7, no DST). An unknown zone falls back to UTC and sets
`warning` rather than failing.
