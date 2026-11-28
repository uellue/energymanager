## 1. Fetch

- [x] 1.1 Add `open-meteo-models` to `services_from_env` (design 1–3). Verify: a test in `tests/test_forecast_archive.py` checks the URL's models, variables and `forecast_days` (scenario "A day of fetches").
- [x] 1.2 Add `open-meteo-previous-runs` as a daily service with its range from what is kept (design 4). Verify: tests for the first fetch from 2026-08-27, for the range after a success and after three failed days (scenarios "First fetch after deployment", "Fetches missed for some days").
- [x] 1.3 A failed request of either source leaves the others' fetches unchanged. Verify: test (scenario "Open-Meteo refuses one request").

## 2. Documentation

- [x] 2.1 README, forecast archive section: the two sources, what they are for, how long the past runs reach back. Verify: reread as a newcomer.
- [x] 2.2 Requirements S3: note which sources are archived now; commit the research note `design/research/pv-forecast-sources.md`.

## 3. On the PC

- [x] 3.1 Test deploy; after the first run, both services have a successful fetch; the past-runs response covers 2026-08-27 to yesterday with one-day-ahead values for all three models. Verify: a query on the archive's database, output in the hand-over. Done 2026-11-28 on a test deploy of this branch: both HTTP 200; past runs 2026-08-27 00:00 to 2026-11-27 23:00, 2232 of 2232 hours for every series except ICON-D2 two days ahead (none, as expected), 140 kB; current forecasts 16 kB, ICON-D2 55 h, the others 96 h.

## 4. Hallway test

- [ ] 4.1 Hallway test (kaizen hallway-test) of the README section: can a newcomer tell from it which sources are archived and how to read one model's forecast for a given hour back out, covering the spec's scenarios. Deferred by the principal (2026-11-28) until the project goes beyond a one-off research deployment; the change may be archived with this task open.
