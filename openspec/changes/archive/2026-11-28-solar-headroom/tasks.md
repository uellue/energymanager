# Tasks

## 1. Expected PV and household load

- [x] 1.1 PV per 15-minute step for the next 48 h from the latest forecast.solar issue, Open-Meteo where it has no value, each hour spread over four steps (design 2). Verify: unit test with a stored forecast body; the 192 steps sum to the forecast's energy for those hours.
- [x] 1.2 Daily load curve per day type over the last 28 days from `logger.minutes_eload_log_ts`, shares summing to 1 (design 3). Verify: unit test on synthetic 5-minute records with a known shape; the shares reproduce it.
- [x] 1.3 Expected daily load = constant + slope × heating degree days with a fitted base temperature, from the daily records since 2025-01-01 (design 3). Verify: unit test where a colder day of the same type expects more load with the same curve shape (spec "A colder day expects more load"); on the PC, a read-only run prints the fit and its error per day.

- [x] 1.4 Correction of the rest of today's PV from today's production (design 8). Verify: unit test where a day produced 1.5× its forecast by noon and the afternoon is scaled by 1.5, and one below 1 kWh where nothing is scaled; a replay over the archived days since 2026-11-21 reports both variants' hourly errors per day, in the hand-over, marked as a first look.

## 2. Battery simulation

- [x] 2.1 Self-consumption rule in 15-minute steps with the limits and efficiency of design 4, efficiency read from the lifetime counters. Verify: unit tests for charging up to 97 %, discharging down to 7 %, the 5 kW and 10 kW limits.
- [x] 2.2 Replay the last 14 days on the PC with actual PV and load from the 5-minute records, starting from the recorded state of charge each midnight; compare the simulated with the recorded state of charge. Verify: the mean and largest deviation per day, reported in the hand-over; a systematic deviation is raised before 3.1 goes live.

## 3. Headroom and endpoint

- [x] 3.1 Headroom per window by bisection (design 5). Verify: unit tests for E23 (headroom in the late morning of a sunny day before feed-in) E24 (no headroom on a winter evening with an emptying battery) and E26 (no headroom on a clear winter day whose battery never fills).
- [x] 3.2 `/headroom` serves the 192 steps; a missing or stale input gives the reason and no headroom values (spec "An input is missing", E2). Verify: handler tests for both cases.
- [x] 3.3 Table `headroom_forecast`, written once an hour, with and without the correction (design 6, 8). Verify: unit test that a run writes 192 rows and a second run in the same hour writes none; a query shows forecast and inverter values side by side for one day (E25).

## 4. Home Assistant and documentation

- [x] 4.1 REST sensor and apexcharts card (design 7), first card on the overview. Verify: after a test deploy, the sensor's state and attributes read through Home Assistant's API; the card's rendering checked by the principal.
- [x] 4.2 README section: what the headroom means, what it is built from, how far to trust it now. Verify: read by a fresh agent with only the README section and the principal's questions; findings fixed.
- [x] 4.3 Independent review of the branch before the pull request; findings listed with what became of them.

## 5. Hallway test

- [ ] 5.1 Hallway test (kaizen hallway-test) of the card and the README section, covering the scenarios of `specs/solar-headroom/spec.md` (E23, E24, E25). Deferred by the principal (2026-11-28) until the project goes beyond a one-off research deployment; the principal found the card readable. The change may be archived with this task open.

## Workflow follow-up

- Archive the change after the merge.
