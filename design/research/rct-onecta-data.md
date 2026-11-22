# What the RCT inverter and Daikin Onecta offer beyond the current entities

Question: which data do the inverter (local protocol) and the Onecta cloud provide that Home Assistant does not record yet, in particular a marker for battery calibration (requirements 2.3), finer heat pump energy (for inferring the heat pump's power, 2.3), and history from before the recording started?

Provenance: the session on 2026-11-22, on the automation PC. RCT: the object registry of `rctclient` 0.0.3 (as installed with the RCT Power integration 0.14.2), its `cli.py`, and one read-only connection to the inverter reading the objects in the table. Onecta: the Daikin Onecta integration's diagnostics in Home Assistant (no extra call to the cloud) and its entities. Meanings of values are the registry's descriptions; everything else is marked.

## RCT inverter

The registry knows 895 objects; the integration reads 110 of them.

Read once on 2026-11-22 (not exposed by the integration unless noted):

| Object | Value | Registry description, notes |
|---|---|---|
| `power_mng.state` | 3 | "Battery state machine". Value meanings not documented in the registry. Candidate for the app's "calibrating". |
| `battery.status`, `battery.status2` | 0, 0 | "Battery status", "Battery extra status" |
| `battery.bat_status` | 0 | exposed as "Battery Status" (normal/charging/discharging/…); showed "charging" during the calibration of 2026-11-21 |
| `prim_sm.state` | 6 | "Inverter status" |
| `power_mng.bat_calib_reqularity` | 30 | "Battery calibration interval", days |
| `power_mng.bat_calib_days_in_advance` | 3 | calibration may run up to 3 days early |
| `power_mng.bat_next_calib_date` | 2026-12-21 11:32 UTC | exposed; read 2026-11-24 before the calibration of 2026-11-21, so that one ran 3 days early |
| `power_mng.calib_charge_power` | 4000 W | "Calibration charge power" |
| `bat_mng_struct.bat_calib_soc_threshold` | 0.80 | "SOC threshold for battery calibration in advance" |
| `battery.soh`, `battery.cycles` | 1.0, 395 | exposed |
| `fault[0..3].flt` | 0 | "Error bit field 1–4"; the integration reads `fault.flt` |
| `logger.log_rate` | 300 s | "Data log resolution" |

The inverter keeps its own logs as time series (`logger.minutes_*`, `day_*`, `month_*`, `year_*`): state of charge and its target, battery, grid feed and grid load, household load, external and solar generator energy, phase voltages, battery and heat sink temperatures, at 5-minute resolution for the `minutes_*` series. This is probably what the RCT app's history graphs show (not checked). `rctclient`'s command line reads a time series by sending a WRITE frame with a timestamp, then a READ (`cli.py`, lines 173–176); the WRITE acts as a query, but it is a write command to the device.

### The inverter's clock and its logs (checked 2026-11-22)

- Log entries carry the inverter's clock, not UTC. Fitting `logger.minutes_soc_log_ts` against Home Assistant's state of charge over two hours (a charge from 5.8 to 7.0 %) gives the best agreement at a shift of −120 minutes (mean difference 0.08 percentage points, against 0.56 without shift). The inverter's clock (`flash_rtc.time_stamp`) read about 2 hours ahead of UTC at the same moment: it still runs on summer time (UTC+2), one hour ahead of local time. `flash_rtc.time_stamp_update` reads 2025-04-12, which looks like the last time the clock was set.
- A query returns the entries logged before the given time by that clock, 60 entries (5 hours of the 5-minute series) at most. Of 8 queries in a row, 2 failed with a checksum error and 2 returned fewer entries with a valid checksum; the missing ones were the oldest of the chunk, which the next query of a backwards walk fetches anyway.
- The collector therefore stores entries with the inverter's clock unchanged and records that clock against the host's clock at every query (table `clock`), so that entries can be placed in UTC later, also if the clock gets corrected.

- Assumption, not verified: if the inverter's clock is corrected (or switches to winter time on its own), entries of the hour around the change carry times that may repeat. The collector keeps the first entry for a given time (`UNIQUE (series, ts)`), so up to two hours per series could be lost there; the `clock` table shows when it happened.

## Daikin Onecta

The cloud data (one device "Altherma", type `heating-wlan`) has a gateway, a climate control (space heating), a hot-water tank, and three units with model and software version.

- Climate control: operation mode, on/off, error code, error/warning states, temperature control with its operation modes and setpoints (leaving-water offset in this unit's weather-dependent mode), outdoor and leaving-water temperature, holiday mode, electrical consumption.
- Hot-water tank: the same plus the tank temperature, a schedule and powerful mode.
- Electrical consumption, per management point, for heating and cooling, in whole kWh:
  - `day`: 24 values, 12 two-hour periods of yesterday and 12 of today;
  - `week`: 14 values, one per day for this and last week;
  - `month`: 24 values, one per month for this and last year.

- Assumption, not verified: Daikin's twelve periods are 00–02, 02–04, … 22–24 local time also on the days summer time starts and ends. The collector computes each period's UTC start from that (on 2026-03-29 "02:00" does not exist and is stored as 01:00 UTC), so on those two days the first periods' UTC times may be off by an hour.

Home Assistant exposes daily, weekly, monthly and yearly totals as sensors, but not the two-hour periods; they exist only in the integration's data. All 42 entities of the integration are enabled.

## What this means

- Calibration: the record cannot mark it yet. `power_mng.state` is the best candidate; its value during the next calibration (between 2026-12-18 and 2026-12-21) would tell. Recording it needs either a read-only poller of our own next to the integration (a second client on the inverter, which already drops out about twice an hour) or the integration exposing it.
- History: the inverter's logs could fill the record from before 2026-11-21 and fill gaps such as the 6.5 hours of 2026-11-21/22, but reading them sends write commands (see above), which the first stage excludes ("no writes to devices", 2.3).
- Heat pump energy in two-hour periods would be a much finer check for inferring the heat pump's power from the household load than the daily total. Monthly values for two years give a seasonal baseline at once.
