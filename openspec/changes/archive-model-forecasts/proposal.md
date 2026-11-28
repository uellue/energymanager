# Proposal: archive the forecasts of named weather models

## Why

The analysis due on 2027-01-31 (issue uellue-bot/energymanager#17) compares PV forecasts with what the array produced (E18, requirements S3 and S5). The archive keeps two sources: forecast.solar, and Open-Meteo's default model choice, whose response does not say which weather model it came from. On 2026-11-30 Open-Meteo moves DWD's ICON models to a new grid, during the period that analysis covers. Open-Meteo also serves the forecasts of named models, both current runs and past runs back to before the inverter's 5-minute records start (2026-08-27). Archiving them gives the analysis three more sources with known model names, and three months of past forecasts at once instead of waiting for them. The principal chose this from the research note `design/research/pv-forecast-sources.md` (2026-11-28).

Persona: P1, the pilot operator, who decides which PV forecast the headroom and later the optimizer use.

The request named Open-Meteo's named models with their past runs. The need (S3) is more sources to compare; this is the first and cheapest of the note's recommendations. DWD MOSMIX and Solcast remain options for later.

## What Changes

- The forecast archive fetches, every hour, Open-Meteo's forecast of global tilted irradiance on the roof plane from three named models: DWD ICON-D2, DWD ICON-EU and ECMWF IFS, hourly and in 15-minute steps, for 4 days.
- Once a day, it fetches the same models' past forecasts from Open-Meteo's Previous Runs API: for each past hour, the value the latest run gave, the run a day earlier and the run two days earlier. The first fetch reaches back to 2026-08-27; later ones fill the days since the last successful fetch.
- Both are kept as fetched, in the archive's existing table, like the other sources.
- Behaviour towards the user: none. No card, no sensor; the existing forecasts and the headroom are unchanged.

## Capabilities

### New Capabilities
- `model-forecast-archive`: keeping the forecasts of named weather models, current and past runs, for later comparison with production.

### Modified Capabilities
None. The existing forecast fetches have no spec and do not change.

## Premises nobody has confirmed

- Open-Meteo's past runs stay available as the probe of 2026-11-28 found them: one-day-ahead values for all three models on 2026-08-27 and 2026-11-20, two-day-ahead values for ICON-EU and ECMWF IFS (ICON-D2 reaches only 48 h), none in January 2024.
- Open-Meteo's global tilted irradiance (isotropic sky, 20 % albedo) is good enough for comparing models with each other; it is the same transposition as today's source.
- The extra requests stay within Open-Meteo's free, non-commercial terms ("personal home automation" is named as allowed): 24 more per day plus one daily, against a limit of 10,000.

## Examples

Serves E18 (should) as an input; no must-example. E18 has no scenario of its own here, since its display is not part of this change; the scenarios are assumed.

## Impact

- `archive/forecast_archive.py`: two more services in `services_from_env`; no new table.
- `tests/test_forecast_archive.py`: the new URLs and the daily range.
- README: the archive section lists the new sources.
- Archive size, estimated from the number of values, not measured: about 60 kB per hourly response, so about 1.5 MB a day; the first past-runs response about 1 MB. Task 3.1 measures it.
- No new dependency. Nothing writes to a device.
