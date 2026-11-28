# Design

## Context

The forecast archive (`archive/forecast_archive.py`) fetches each source in `services_from_env` once per hour (or once per UTC day with `daily=True`) and keeps the response body unchanged in the append-only table `fetch`, with the service name, the fetch time and any error. Open-Meteo is fetched today with its default model choice ("best match"), whose response names no model. The temperature history (`HISTORY`) shows the pattern for a daily fetch whose range depends on what is kept: from a fixed start until one fetch has succeeded, then from a few days before the last success. A probe from the automation PC on 2026-11-28 confirmed the parameters below: the Previous Runs API returned `global_tilted_irradiance_previous_day1_<model>` for all three models on 2026-08-27 and 2026-11-20, `…_previous_day2_<model>` for ICON-EU and ECMWF IFS, and nothing for January 2024; the forecast API returned all three models hourly and in `minutely_15`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Three more PV-relevant forecasts, each with its model's name, for the analysis of 2027-01-31.
- Past forecasts back to 2026-08-27, so the analysis can use three months more than the archive has.

**Non-Goals:**
- Showing them, or using them in the headroom; that waits for the analysis.
- DWD MOSMIX, Solcast and the others in the research note; later changes if wanted.

## Decisions

1. **Two new services, `open-meteo-models` (hourly) and `open-meteo-previous-runs` (daily), in the existing table.** Same mechanism as every other source; the model names are in the response's keys (`…_dwd_icon_d2`), so nothing else needs storing. The default Open-Meteo service stays as it is, since the headroom and the E5 chart read it and its series should not break. Agent's decision, reversible.
2. **Models: `dwd_icon_d2`, `dwd_icon_eu`, `ecmwf_ifs`.** ICON-D2 is the high-resolution German model (2 km, 15-minute native, to about 48 h); ICON-EU covers the second day fully; ECMWF IFS is an independent model. As the research note recommends; the principal agreed on 2026-11-28. Reversible.
3. **Variables: `global_tilted_irradiance` only, hourly and `minutely_15`, `forecast_days` 4.** GTI is what the PV estimate uses; temperature and cloud cover are in the default service already. 4 days as for the default service. Agent's decision, reversible.
4. **Past runs: `global_tilted_irradiance`, `…_previous_day1`, `…_previous_day2`, hourly, from 2026-08-27 until one fetch has succeeded, then from 3 days before the last success to the end of yesterday (UTC).** 2026-08-27 is when the inverter's 5-minute records start, so earlier forecasts have no hourly production to compare with. Past runs do not change, so a short overlap is enough to cover missed days; it follows the history service's pattern. Agent's decision, reversible.
5. **The ICON grid change of 2026-11-30 is not recorded separately.** The model names stay the same; the date is known, so the analysis can split at it. Agent's decision.

## Risks / Trade-offs

- [Open-Meteo counts a long request as several calls] → The first past-runs request (about 95 days) counts as a few calls of the 10,000 a day; the hourly requests are small.
- [All four Open-Meteo sources share one provider and one transposition] → Differences in the transposition stay invisible; an independent source (MOSMIX) is a later change.
- [Archive growth of about 1.5 MB a day] → Acceptable on the PC; the backups by hand get larger.

## Migration Plan

New services only; no change to existing data. Rollback: revert the commit; the kept responses can stay.

## Blocking questions

None. This branch starts from `solar-headroom`, which also changes `forecast_archive.py`, so its pull request follows that one.
