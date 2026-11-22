# Design

## Context

The pilot runs on the automation PC (Debian 13, Docker Compose) with Home Assistant 2026.11.2, the forecast archive (`archive/`, design D7/D8 of `collect-and-view`) and alerts (`homeassistant/packages/alerts.yaml`). Facts about the devices are in `design/research/rct-onecta-data.md`. The RCT protocol as documented by `rctclient` (docs: `protocol_timeseries.rst`, `protocol_overview.rst`, `inverter_bitfields.rst`, read 2026-11-22):

- A time series is queried by writing a UNIX timestamp to its object; the inverter returns entries logged before that time. A full day of one series takes about 7 queries.
- The devices "are not meant to communicate with multiple network clients simultaneously"; a second client's request interrupts the first, and frames arrive cut or with wrong checksums.
- The app shows "(calib.)" from two bits of `battery.bat_status` (found empirically by a user).

## Goals / Non-Goals

Goals: E10, E11, E12 as specified; the collector itself watched by an alert (E9).

Non-goals:
- Decoding the state values. They are kept raw and interpreted after the next calibration.
- Merging the inverter's log into Home Assistant's recorder or statistics. It stays in the collector's database until the model (S2) reads it.
- Any write to a device other than the log queries.
- Replacing the Home Assistant integration as the main source of live values.

## Decisions

Each line gives who decided and whether the decision is reversible.

- **C1 One collector service, `collector/`, in its own container, with its own SQLite database `<EM_DATA_DIR>/collector/collector.sqlite`.** Same pattern as the archive (D2, D7). Agent's choice, reversible. Alternatives:
  - extending the archive: it is standard library only and does one thing;
  - three services: more containers for little code.
- **C2 Dependency `rctclient` 0.0.6 (GPL-3.0), pinned.** Principal, 2026-11-22. It brings the protocol's framing and checksum, the registry and the value decoding, including time series. Our code imports it and the image installs it from PyPI; the repository does not contain it. Reversible: the protocol subset needed is small enough to implement ourselves.
- **C3 Tables, append-only, as raw as the source gives them.** Agent's choice, reversible:
  - `state(read_at, object, value)`: one row per object and read. The value is the integer or float as decoded.
  - `log_entry(series, ts, value, read_at)`, unique on `(series, ts)`. `ts` is the inverter's timestamp, stored unchanged. Which zone the inverter's clock uses is not documented, so it is checked once against the live values (task 3.2) and noted.
  - `energy_period(day, period_start_local, period_start_utc, management_point, mode, kwh, read_at)`, unique on `(day, period_start_local, management_point, mode)`.
  - `failure(at, part, error)`.
- **C4 State polling: one TCP connection per minute, five READ frames, then close.** Agent's choice, reversible. Short connections keep the overlap with the integration's 30-second polling small. A cut or bad frame is retried once after 2 s, then recorded as a failure for that minute.
- **C5 Log import: a resumable walk backwards, one query every 10 s.** For each series: query with the oldest timestamp already stored (or now), store the entries, repeat until the inverter returns nothing older. About 40 series × 7 queries per day of the 5-minute series; at one query every 10 s, a month of history takes a few days, which is acceptable. After the walk, the newest entries are fetched hourly. The pace is adjusted if Home Assistant's household load shows gaps during the import (spec: gentle on the inverter). Agent's choice, reversible.
- **C6 Only `logger.*` objects are written to.** The function that sends a write takes a registry entry and refuses any object whose name does not start with `logger.`; a unit test checks the refusal. Principal's exception of 2026-11-22 (requirements 2.3), with the agent's guard.
- **C7 Heat pump periods from Home Assistant's diagnostics.** Once a day at 03:00 local, the collector fetches `/api/diagnostics/config_entry/<id>` of the `daikin_onecta` entry with the long-lived token from `.env`, takes the `day` arrays (first 12 values = yesterday) for each management point with consumption data, and stores the twelve periods per point and mode. If any expected key is missing, it stores nothing and records a failure. The token's scope is the whole Home Assistant, as for the status script; a narrower credential does not exist for this API. Agent's choice, reversible; tracked in issue uellue-bot/energymanager#2.
- **C8 Home Assistant reads the collector like the archive.** A read-only endpoint on 127.0.0.1 (D8 pattern) returns the latest state values and the time of the last success per part; a `rest` sensor shows them, and three binary sensors feed alerts in `alerts.yaml`: state not read for 10 minutes, log not read for 3 hours, periods not stored for yesterday by 06:00. Agent's choice, reversible.

## Risks / Trade-offs

- A second client on the inverter: the integration may get more drop-outs. Mitigation: C4, C5, and watching the integration's unavailable count before and after (task 2.4).
- The diagnostics format may change with any update of the Daikin integration. Mitigation: C7's all-or-nothing parse and its alert.
- `rctclient` is a small project with one maintainer; if it stops, the needed subset can be reimplemented.
- The log import's timestamps: if the inverter's clock or zone is off, entries land at wrong times. Mitigation: task 3.2.

## Blocking questions and the assumptions the build may start on

None block. The build may start on these assumptions:
- the inverter's logs reach back at least a few days;
- a one-minute poll does not disturb the integration measurably;
- yesterday's twelve periods are final at 03:00.

Each is checked by a task.

## Open Questions

- What `power_mng.state` and `battery.bat_status` show during a calibration: answered by the next one, 2026-12-18 to 21.
- Whether the 2-hour periods are worth raising upstream: issue uellue-bot/energymanager#2.
