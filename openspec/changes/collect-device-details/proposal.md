# Proposal

## Why

The record lacks three things the model (S2) needs and the devices already hold (`design/research/rct-onecta-data.md`):

- **Calibration phases.** The battery calibrates every 30 days and then behaves unlike normal operation (requirements 2.3). The integration's "Battery Status" showed "charging" during the calibration of 2026-11-21, so the record cannot mark it. The next one is due between 2026-12-18 and 21; if the inverter's state is not recorded by then, the next chance comes a month later.
- **History.** The inverter logs its values every 5 minutes. Reading those logs would cover the time before the recording started (2026-11-21) and gaps such as the 6.5 hours of the night to 2026-11-22.
- **Heat pump energy per 2-hour period.** Daikin provides it for yesterday and today only; every day not collected is lost. It is a much finer check for inferring the heat pump's power from the household load than the daily total.

Persona: P1, the pilot operator (design/stakeholders.md).

The principal asked for exactly these three (2026-11-22: "49, 50 Yes please", "I'd really like to have these values"). They are the whole request; the form (one collector service) is the agent's proposal.

## What Changes

- A collector service next to the forecast archive, in its own container with its own SQLite database in the data folder, the same way as the archive:
  - every minute, it reads the inverter's battery and inverter state objects (read only) and stores their raw values (E10);
  - once, it reads the inverter's logs back as far as they go, then keeps reading the newest entries (E11); this uses the timestamp queries that are the one allowed exception to "no writes to devices" (requirements 2.3, `logger.*` only);
  - once a day, it takes yesterday's twelve 2-hour periods of heat pump energy, for space heating and hot water, from the Daikin Onecta integration's diagnostics through Home Assistant's API (E12). No extra call to the Daikin cloud.
- Home Assistant shows the current battery state machine value and alerts when the collector stops or a part of it fails (E9).

Behaviour towards the user: one new sensor on the dashboard and new alerts; nothing else changes. Nothing is written to devices beyond the log queries.

## Capabilities

### New Capabilities
- `inverter-state-record`: the inverter's battery and inverter state objects recorded every minute, raw.
- `inverter-log-import`: the inverter's own logs read back and kept, marked as such.
- `heat-pump-energy-periods`: the heat pump's electrical energy per 2-hour period, per day, for space heating and hot water.

### Modified Capabilities
(none: `collect-and-view` is not archived yet, so `openspec/specs/` is empty.)

## Must-examples and premises

- Examples served: E10, E11, E12 (should, added 2026-11-22), and E9 (alerts) for the collector itself. No must-example; none without a scenario.
- Premises nobody has confirmed:
  - `power_mng.state` or the raw `battery.bat_status` change during a calibration. The library's documentation says the app shows "(calib.)" from two bits of `battery.bat_status`, found empirically; `power_mng.state` is a guess from its name ("Battery state machine").
  - The inverter tolerates a second client polling every minute next to the Home Assistant integration. The library warns that the devices "are not meant to communicate with multiple network clients simultaneously".
  - How far back the inverter's logs reach.
  - The diagnostics format of `daikin_onecta` 5.0.4 stays as observed; it is not an interface.
  - Yesterday's twelve periods are final when read after midnight. The integration's tracker had an issue about the day's last period arriving late.

## Impact

- New: `collector/` (Python, container), its tests, a service in `compose.yaml`, a REST sensor and alerts in `homeassistant/packages/`, README section.
- Dependency: `rctclient` 0.0.6 (GPL-3.0), approved by the principal 2026-11-22.
- The inverter gets one more client and, for the log import, bursts of queries; the Home Assistant integration may see more drop-outs.
- Home Assistant's long-lived token (already in `.env`) is used by the collector to read diagnostics.
