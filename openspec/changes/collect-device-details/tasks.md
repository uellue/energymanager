# Tasks

The state polling (group 2) goes first: the next calibration is due between 2026-12-18 and 21.

## 1. Collector skeleton

- [x] 1.1 `collector/` with a Dockerfile (`python:3.15-slim-trixie`, `rctclient==0.0.6`), the SQLite tables of C3 (append-only, unique keys), settings from `.env` (inverter host and port, Home Assistant URL, token, CA file), and a service in `compose.yaml` with `<EM_DATA_DIR>/collector`. Verify: `docker compose up -d collector` starts; `git status` shows no data file.
- [x] 1.2 The write guard of C6 and its unit test. Verify: the test shows a write to `power_mng.state` (or any non-`logger.*` object) refused before any frame is built.

## 2. Inverter state (E10)

- [x] 2.1 Read the five state objects once a minute (C4) and store them; record failures. Unit tests against a fake inverter (a local TCP server answering recorded frames) cover a normal read, a cut frame with retry, and an unreachable inverter (gap, failure recorded). Verify: tests cite E10 and E2.
- [x] 2.2 Endpoint on 127.0.0.1 and `rest` sensor (C8); the dashboard shows the battery state machine and raw battery status. Verify: on the automation PC, both sensors have values within 2 minutes of start.
- [ ] 2.3 Alert "collector state not read for 10 minutes" in `alerts.yaml`. Verify: stopping the collector for 15 minutes raises it on the phone; starting it clears it.
- [ ] 2.4 Check the load on the inverter: compare the integration's unavailable count over 24 h before and after the collector started. Verify: numbers in the hand-over; if worse, adjust C4 and say how.

## 3. Inverter logs (E11)

- [x] 3.1 The backwards walk of C5, resumable, with the guard of 1.2. Unit tests against the fake inverter cover a walk to the end, a restart in the middle (no entry stored twice), and a repeated read (nothing changes). Verify: tests cite E11.
- [x] 3.2 On the automation PC, read one day of `logger.minutes_soc_log_ts` and compare it with Home Assistant's state of charge for the same hours; note the inverter's clock zone in `design/research/rct-onecta-data.md`. Verify: the two agree within the 5-minute resolution once the zone is applied.
- [ ] 3.3 Run the full import, then hourly reads. Verify: how far back the logs reach, the number of entries per series, and that the night to 2026-11-22 is covered; household load in Home Assistant has no gap over 2 minutes during the import.
- [ ] 3.4 Alert "inverter log not read for 3 hours". Verify as in 2.3.

## 4. Heat pump energy periods (E12)

- [x] 4.1 The daily read of C7 with an all-or-nothing parse. Unit tests with a diagnostics document recorded on the automation PC, with identifiers replaced by placeholders, cover a normal day, a missing key (nothing stored, failure recorded) and a repeated read (no duplicate). Verify: tests cite E12.
- [ ] 4.2 On the automation PC, after two nights: twelve periods each for space heating and hot water per day, and their sums equal the integration's daily totals for those days. Verify: the numbers in the hand-over.
- [ ] 4.3 Alert "heat pump periods missing for yesterday at 06:00". Verify: with the diagnostics URL pointed at a wrong entry, the alert is raised the next morning, or by calling the check directly.

## 5. Documentation and review

- [x] 5.1 README section "Collector": what it records, the one write exception, settings, how to check it. Verify: the private-data check passes; the section reads correctly for someone who has not seen this change.
- [x] 5.2 Independent review of the collector (it sends frames to a device and writes data on its own; standing instructions). Verify: findings fixed or listed in the hand-over.

## 6. Hallway test

- [ ] 6.1 Deferred by the principal (2026-11-22: "Having someone else set it up comes much later, after we have actual control"). Hallway test (kaizen hallway-test): a fresh agent with only the README, the requirements and the examples sets up the collector against the fake inverter and a recorded diagnostics document, and checks E10, E11 and E12 as far as possible without the devices. Verify: a record in `design/hallway/`, findings fixed or filed.

## Notes from the build (2026-11-22)

- 4.1: the test document is synthetic, shaped like the diagnostics of `daikin_onecta` 5.0.4 as observed on the automation PC, rather than a recorded one with identifiers replaced; it holds no value from the site.
- 5.2: the review found, among others, that gaps longer than one answer were never filled, that an unexpected diagnostics shape could crash the collector in a loop, that an all-NaN answer stalled the walk, and a guard that allowed `logger.log_rate`. All are fixed with tests; two assumptions (clock correction, DST days) are recorded in `design/research/rct-onecta-data.md`.
- 2.3: the first test showed the alert firing after 37 s, because the sensor turns unavailable at once on a restart; a 5-minute delay was added. Its verification is still to be repeated.
