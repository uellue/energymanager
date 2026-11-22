# Tasks

Steps marked (person) need the principal at a browser or with an account; the agent prepares them and checks the result.

## 1. Private-data check (first: before any credential exists)

- [x] 1.1 Write `tools/check_private_data.py` (D12) and `tests/test_check_private_data.py` (unittest). Cover each scenario of `private-data-check`: private IP, coordinates as keys, as a comma pair and as a slash pair, JWT, token assignment, clean change, and a message that names the file, the line and `--no-verify` without printing the value. Verify: `python3 -I -m unittest discover -s tests` passes.
- [x] 1.2 Add `.githooks/pre-commit` and the activation command to `README.md` (new, setup section). Verify: after `git config core.hooksPath .githooks`, a scratch commit adding a 192.168 address is refused and a clean commit passes. Throwaway branch, deleted afterwards.
- [x] 1.3 Run the check over every tracked file once. Verify: no finding, or each finding listed for the principal. History is not rewritten.
- [x] 1.4 Review of the hook and script by an agent that did not write them (standing instructions: a hook). Verify: review findings resolved or listed in the hand-over.

## 2. Forecast archive

- [x] 2.1 Write `archive/` (D7): fetch forecast.solar and Open-Meteo (temperature, cloud cover and global tilted irradiance for the roof plane, 48 h), store raw responses in SQLite, record failures, limit calls to one per service per UTC hour. Settings only from environment variables. Verify: unit tests against a local fake HTTP server (standard library) cover "A day of fetches" (simulated clock), "Service down", "Restart loop" and "Kept as issued" (E6).
- [x] 2.2 Find out where forecast.solar states its issue time in the response, if anywhere, and store it. Verify: a test with a recorded response from a generic location (not the site) reads the issue time; Open-Meteo stores none.
- [x] 2.3 Add the reader (closest issue before a given time) and the read-only HTTP endpoint for E5 (D8), bound to `127.0.0.1`. Verify: unit tests cover "Read one issue" and the E5 series (latest issue before each hour, both services, 7 days); `ss -ltnp` shows the port on 127.0.0.1 only.
- [x] 2.4 Add the Dockerfile (`python:3.15-slim-trixie`), `compose.yaml` with the archive service, `.env.example`, and `EM_DATA_DIR` (D2, D9). Document them in `README.md`. Verify: `docker compose up -d archive`, then after the next full hour `sqlite3` (or Python) shows one row per service; `git status` shows no data file.

## 3. Home Assistant stack

- [x] 3.1 Add the `homeassistant` service to `compose.yaml` (D1), pinned to 2026.11.2, with `/config` in `EM_DATA_DIR` and the repository's `homeassistant/packages` and `homeassistant/dashboards` mounted read-only (D3). Verify: `docker compose config` is valid and http://localhost:8123 opens in the Windows browser.
- [x] 3.2 (person) Onboarding: user, location, time zone. Then the two documented lines in `configuration.yaml`. Verify: the location appears nowhere in the repository (the check from 1 passes on the next commit).
- [x] 3.3 Add `homeassistant/packages/recorder.yaml` (D4: `auto_purge: false`, excluded entities). Verify: Home Assistant's configuration check passes and the recorder starts without warnings in the log.

## 4. Integrations

- [x] 4.1 (person) Open Marketplace and accept its warning about third-party code. Since 2026.11, HACS is part of Home Assistant as the built-in Marketplace (catalogue `hacs/default`); it removes a manual `custom_components/hacs` install, and needs no GitHub login. Verify: `marketplace/info` over the WebSocket API reports `warning_accepted: true`.
- [x] 4.2 (person, agent prepares) RCT integration v0.14.2 from HACS, frequent interval 30 s. Verify, through Home Assistant's history API with a long-lived token kept in `.env`: solar power, state of charge, household load, and grid import and export have at least 10 values in 10 min ("Inverter power at least every minute").
- [x] 4.3 (person) Daikin Onecta v5.0.4: Developer Portal application and OAuth. Verify: outdoor, room, leaving-water and tank temperature and daily heat pump energy have values; note the polling interval and the resulting calls per day (at most 200). Result 2026-11-21: outdoor, leaving-water and tank temperature and daily energy have values (whole °C, whole kWh); the unit reports no room temperature (see proposal). Polling 10/30 min, about 108 calls per day by the defaults; the integration's remaining-calls sensor confirms the real count after a day.
- [x] 4.4 forecast.solar (core) for the one roof plane, and Open-Meteo (core) for the weather. Verify: both have entities with a forecast; note forecast.solar's polling interval, and confirm that together with the archive it stays under 12 calls per hour.
- [ ] 4.5 Verify E1's sources: a script lists the E1 entities with unit and last value, and none is missing. Verify "Nothing written to devices": no service calls to the Daikin or RCT entities in the logbook for a day.

## 5. Gaps and the mocked outage

- [x] 5.1 Confirm the Onecta API host names in `daikin-onecta` 0.6.2. Write `compose.mock-daikin-outage.yaml` (D10) and its documentation. Verify: the file maps every Onecta host.
- [ ] 5.2 Run the mock for an hour, then switch it off (E8, E2). Verify through the history API: the Daikin entities are `unavailable` for that hour with no repeated values, values resume afterwards, and no re-authentication is requested.
- [ ] 5.3 Verify E2 for the inverter without touching it: stop Home Assistant's access to it for 10 min (e.g. a wrong port in the integration's options, then back). The record shows the gap.

## 6. Dashboard

- [x] 6.1 Install apexcharts-card v2.2.3 from Marketplace.
- [x] 6.2 Write `homeassistant/dashboards/energy.yaml` (D11): the E1 values; the 48 h solar and weather forecasts; and the `rest` sensor for the archive endpoint, excluded from the recorder. Verify: the person opens it, and every E1 value is visible ("E1 values visible"). A screenshot goes in the hand-over.
- [ ] 6.3 Add the E5 chart: hourly production, the solar forecast, and the weather-based estimate (D6), labelled as an upper estimate. Verify after 3 or more recorded days: the chart shows all three series for those days.
- [ ] 6.4 Verify "Gaps shown as gaps": the history and apexcharts cards show the hour from 5.2 as a gap, not a line drawn across it. Screenshot.
- [x] 6.5 Verify "Moving to the mini PC" on paper: the dashboard file holds only entity IDs (the check from 1 passes on it). The real move is the separate walk.

## 7. Hallway test

- [ ] 7.1 Run a hallway test (kaizen hallway-test): a fresh agent with only `README.md`, the requirements and the examples sets up the archive and checks the private-data check. The person covers the Home Assistant steps it cannot do. Coverage: S1 with E1, E2, E5, E6 and E8. Verify: a record in `design/hallway/`, with findings fixed or filed.

## Workflow follow-up

- Measure the recorder database's growth after a week (design: Risks).
- Archive the change once the principal accepts the hallway test.
