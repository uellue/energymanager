# Design

## Context

The repository holds only design documents so far. Docker Engine 29.10 and Compose v5.8 run in WSL2 (Debian 13.7) on the development machine. WSL2 uses NAT but reaches the home network outbound: the RCT inverter was read on TCP 8899 (walk-through p1-collect-and-view). The development machine does not run around the clock, so its record will have gaps until the move to the mini PC. That is expected, and it is a separate walk.

Facts checked on 2026-11-21 against the projects' sources and APIs:
- Home Assistant 2026.11.2 (Apache-2.0).
- HACS 2.0.5 (MIT). Found on 2026-11-21 while setting up: Home Assistant 2026.11 contains HACS as the built-in integration Marketplace, which takes over the same catalogue and removes a manual HACS install. The pilot uses Marketplace; HACS is no longer a separate dependency.
- RCT integration v0.14.2 (weltenwort, MIT). It polls its frequent values every 30 s by default, configurable; the infrequent ones every 180 s.
- Daikin Onecta v5.0.4 (GPL-3.0). On a connection error, its coordinator raises `UpdateFailed`, and its entities then report unavailable (`entity.py`, `sensor.py`). It uses the `daikin-onecta` 0.6.2 library; OAuth goes to `idp.onecta.daikineurope.com`.
- apexcharts-card v2.2.3 (MIT).
- Python image `python:3.15-slim-trixie`.
- forecast.solar's free estimate returns watts per hour for today and tomorrow.
- Open-Meteo returns hourly `global_tilted_irradiance` for a given tilt and azimuth, plus temperature and cloud cover. It states no issue time.

## Goals / Non-Goals

**Goals:**
- One Compose stack that runs unchanged on the development machine and the mini PC, configured by one local `.env`.
- Every file the person might edit by hand lives in the repository (dashboard, recorder settings). Every file holding site data lives outside it.

**Non-Goals:**
- A Home Assistant add-on (later, for P2; requirements 2.8).
- Alerts (E9).
- Test-case export (E7, S2).
- The Zigbee thermometer, and a heat pump power reading beyond Onecta's daily energy.
- Backups of the recorded data; the walk to the mini PC handles them.

## Decisions

Each line gives who decided and whether the decision is reversible.

- **D1 Home Assistant Container with `network_mode: host`, image pinned to 2026.11.2.** Container is the principal's choice (2.4, 2.8), reversible. Host networking is the agent's choice, reversible. It lets Home Assistant reach the inverter and the archive at `localhost`. The alternative, a bridge network with published ports, works too but complicates local discovery.
- **D2 Runtime data outside the repository.** `.env` (gitignored; `.env.example` is committed) sets `EM_DATA_DIR`, e.g. `~/energymanager-data`. The data goes in `homeassistant/` and `forecasts/` below it. Agent's choice, reversible. This way no `.gitignore` mistake can publish the recorder database or `.storage` (tokens, location). The alternative, a gitignored folder inside the repository, is one typo away from a leak.
- **D3 Versioned Home Assistant configuration as a package.** The repository's `homeassistant/packages/` and `homeassistant/dashboards/` are mounted read-only into `/config`. Onboarding creates `configuration.yaml`, and the person adds two documented lines: the package include and the dashboard entry. Agent's choice, reversible. Alternative: committing all of `configuration.yaml`, which onboarding and the UI also write to.
- **D4 Recorder: default SQLite, nightly purge off (`auto_purge: false`).** This is "kept indefinitely, the model downsamples" (2.4, principal). The setting is reversible, but data already purged cannot be restored. The `/config` check in task 3 confirms that the option name exists in 2026.11. Entities nobody needs (e.g. the RCT integration's static diagnostics) are excluded to limit growth.
- **D5 Weather: Open-Meteo.** The core integration supplies the dashboard's 48 h forecast, and the archive calls the API directly. Agent's choice, reversible. Open-Meteo is chosen because it gives irradiance on the tilted roof plane (35°, azimuth 55°), which E5 needs; met.no, the onboarding default, has no irradiance. The free API is for non-commercial use, which the pilot is. P2 sites may need another provider; that is not decided now.
- **D6 Weather-based production estimate for E5: `GTI × kWp / 1000 W/m²`.** This is the plane's peak power at 1000 W/m², with no loss factor, labelled on the chart as an upper estimate. Proposed by the agent, confirmed by the principal on 2026-11-21 ("gather data and compare against expectations to learn what is what"), reversible. A performance ratio, or a fit against measured production, belongs to S2.
- **D7 Forecast archive: one Python process, standard library only, SQLite.**
  - Table `fetch`: service, fetched time (UTC), issue time if the service states one, HTTP status, raw response body unchanged, error text. Append-only.
  - Before each call it checks whether the service already has an attempt in the current UTC hour, which keeps restarts within the rate limits.
  - A loop sleeps until a few minutes past each hour.
  - Agent's choice, reversible. No new Python dependency. Raw bodies keep E6 independent of how they will be parsed later.
- **D8 Archive → dashboard over a small read-only HTTP endpoint, bound to `127.0.0.1`.** The endpoint returns the hourly series E5 needs for the last 7 days: per hour, the latest forecast issued before it, from both services. A Home Assistant `rest` sensor reads it every 15 min into an attribute, excluded from the recorder; apexcharts-card plots it against measured production. Agent's choice, reversible. The alternative, the archive pushing states to Home Assistant, would put a Home Assistant token into the archive. A pull needs no credential, and the localhost binding keeps the endpoint off the network.
- **D9 Location and keys only in `.env`.** Latitude, longitude, declination, azimuth and kWp for the archive. Home Assistant keeps its own copies in `.storage` after onboarding. Agent's choice, following 2.9.
- **D10 Mocked Daikin outage: a Compose override file.** `compose.mock-daikin-outage.yaml` maps the Onecta hosts to an unroutable address through `extra_hosts`. Switching it on or off recreates the Home Assistant container. Agent's choice, reversible. The library then raises the same connection error as in a real outage, which takes the code path that leads to unavailable (E8).
  - Cost: each switch restarts Home Assistant, so every source has a gap of about a minute, which is documented.
  - Rejected: disabling the integration in the UI takes a different code path. Blocking by IP with iptables breaks when the cloud's addresses change.
- **D11 Dashboard in YAML mode, committed.** Core history-graph cards for the E1 values; apexcharts-card (HACS) for E5, since the core cards cannot plot forecast series from an attribute. Agent's choice, reversible. **Adds a dependency** (see Blocking questions).
- **D12 Private-data check.**
  - A Python standard-library script, `tools/check_private_data.py`, reads the added lines of `git diff --cached`.
  - The hook is `.githooks/pre-commit`, activated with `git config core.hooksPath .githooks`.
  - Patterns:
    - RFC 1918 IPv4 addresses;
    - coordinate pairs: `lat…`/`lon…` keys with a number of 3 or more decimals, or two such numbers separated by a comma or a slash;
    - JSON Web Tokens (Home Assistant's long-lived tokens are JWTs);
    - `token|secret|password|api_key` assignments with a value of 16 or more characters.
  - The test file builds its examples at run time, so the check does not trip on its own tests.
  - Agent's choice, following ledger row 4 (no new dependency), reversible. Rejected: a secret scanner such as gitleaks, a new tool that does not know about coordinates.

## Risks / Trade-offs

- [The recorder database grows without bound] → Measure its size after a week of RCT data at 30 s. Exclude unneeded entities. If it is still large, revisit D4 with the principal; nothing is purged without asking.
- [Onecta's budget of 200 calls per day is shared with any other client, such as a second instance or the app] → The pilot runs one Home Assistant only. Whether the limit is per account or per application stays open.
- [A token refresh during the mocked outage could make Onecta ask for re-authentication instead of reporting unavailable] → Task 6 checks for this. If it happens, the mock is shortened below the token's lifetime, or the finding is recorded and E8 revisited.
- [forecast.solar's 12 calls per hour per IP are shared] → The archive makes 1 call per hour; Home Assistant's integration polls about hourly. Task 4 confirms its interval.
- [The development machine is off at night] → Gaps in the record are expected and show as gaps; they don't count against E2.
- [Daikin Onecta is GPL-3.0] → It is installed at the site through HACS and not redistributed by this repository, so the MIT licence is not affected (2.9).
- [The private-data check misses a pattern, or trips on a version number] → It is a safety net, not a guarantee. Overriding uses git's `--no-verify`. New patterns get added with a concrete example and a test.

## Blocking questions and the assumptions the build may start on

None left. Settled by the principal on 2026-11-21:
- The E5 estimate (D6) is confirmed.
- The dependencies are approved: Home Assistant, HACS, the RCT integration, Daikin Onecta, apexcharts-card and the `python:3.15-slim-trixie` image.
- D4: purging stays off, and the growth is measured after a week. The storage requirement for later is in requirements 2.4.

## Open Questions

- Whether Onecta's budget is per account or per application (only matters once there is a second instance).
- The recorder database's growth rate (measured in the first week).
