# Proposal

## Why

The model (S2) and the optimizer (S3) need data from every source in the pilot house, recorded at the rate each source delivers, plus every forecast as it was issued. None of this exists yet: there is no Home Assistant installation and no code. Scenario S1 (requirements 2.1) is the start the principal chose: "Collecting data and a nice dashboard to view it sounds like the correct start."

Persona: P1, the pilot operator (design/stakeholders.md).

The request named the full S1 scope: Home Assistant with the heat pump, the inverter and battery, the solar forecast and a weather forecast; our own container that keeps the forecasts as issued; one dashboard. This is the whole need of S1 except the Zigbee thermometer and a heat pump power reading, which wait for hardware (see Premises). Before the first credentials are handled, a pre-commit check against private data goes in (ledger row 4, accepted 2026-11-21).

## What Changes

- A Docker Compose stack for the development machine (WSL2, Debian 13). The same stack moves to the mini PC later:
  - Home Assistant Container;
  - the project's own forecast archive container.
- Home Assistant is set up with HACS and these integrations:
  - the RCT inverter and battery (HACS);
  - Daikin Onecta (HACS, cloud);
  - forecast.solar (core);
  - Open-Meteo weather (core).
  Recorder retention is raised so that measurements are kept indefinitely (2.4).
- The forecast archive fetches the solar forecast and the weather forecast every hour. It keeps every response unchanged, with its issue time, independent of Home Assistant (E6, 2.3).
- One dashboard, kept in the repository, shows the E1 values; solar production against both forecasts (E5); and gaps as gaps (E2).
- A documented way to mock a Daikin cloud outage without touching the unit (E8).
- A pre-commit check that refuses commits containing private data: private IP addresses, coordinates, tokens.
- Site-specific values (location, credentials, tokens) live in local files outside git (2.9).

No behaviour towards devices changes: everything is read-only (2.11). The new behaviour towards the user is the dashboard, plus the pre-commit check for whoever commits.

## Capabilities

### New Capabilities

- `site-data-collection`: which sources are recorded, at which rate, for how long, and how a missing source shows up in the record.
- `forecast-archive`: keeping every solar and weather forecast as issued, with its issue time, and reading them back.
- `dashboard`: what the single dashboard shows.
- `private-data-check`: refusing commits that contain private data of the site.

### Modified Capabilities

None (no specs exist yet).

## Must-examples satisfied

- E1, E2, E6 and E8 (must); E5 (should).
- Not in this change: E9 (alert, should, later), E7 (test-case export, S2), E3 and E4 (S2, S3).
- Every must-example in design/examples.md has a scenario.

## Premises nobody has confirmed

- E6, E7 and E8 are marked [assumed] in design/examples.md. E6 and E8 are part of this change.
- The heat pump's electrical power is only available as daily energy from Onecta. Its interval data waits for the PCB check (2.3, open), so E1's "heat pump energy" is daily energy for now.
- No room temperature until the Zigbee thermometer is ready (2.2). Checked on 2026-11-21: the pilot unit runs on leaving-water control (`leavingWaterTemperature`, weather-dependent), and Onecta reports no room temperature for it. E1's room temperature stays open until then.
- Onecta reports temperatures in whole °C and energy in whole kWh per day (seen on 2026-11-21). This limits how finely the model can be fitted from them (requirements 1.1).
- Whether Onecta's call budget of 200 per day is per account or per application is unknown (walk-through step 4). The pilot runs one instance only.

## Impact

- New: `compose.yaml`, the forecast archive (Python, standard library only), the dashboard YAML, a pre-commit hook script, and setup documentation.
- New third-party components, none of them redistributed by this repository: Home Assistant (Apache-2.0), HACS (MIT), the RCT integration (MIT), Daikin Onecta (GPL-3.0, installed at the site through HACS), and apexcharts-card (MIT). Each needs the person's approval (see design.md).
- External services: forecast.solar (12 calls per hour per IP, shared with Home Assistant), Open-Meteo (free for non-commercial use), and the Daikin cloud (200 calls per day).
