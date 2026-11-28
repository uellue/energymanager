# PV forecasts against measured production: a first look

Question: how well do the irradiance forecasts of three named weather models predict this array's production, one and two days ahead? A first look ahead of the analysis due 2027-01-31 (requirements S3, issue uellue-bot/energymanager#17), on the past runs the forecast archive fetched on 2026-11-28.

Provenance: computed on 2026-11-28 with `tools/compare_pv_forecasts.py` on the automation PC, from the archive's latest `open-meteo-previous-runs` fetch and the inverter's 5-minute energy records. Not reviewed by a person.

## For people

90 days, 2026-08-26 to 2026-11-27. Forecast = global tilted irradiance × 7.92 kWp, no losses. Measured mean: 25 kWh/day in August and September, 17 in October, 10 in November.

| Model | Lead | Forecast ÷ measured | Error, kWh/day | Correlation | Error after scaling |
|---|---|---|---|---|---|
| DWD ICON-D2 | same day | 1.13 | 3.1 | 0.95 | 2.2 |
| DWD ICON-D2 | 1 day | 1.17 | 4.1 | 0.91 | 2.8 |
| DWD ICON-EU | same day | 1.09 | 3.2 | 0.93 | 2.6 |
| DWD ICON-EU | 1 day | 1.17 | 4.1 | 0.92 | 2.8 |
| DWD ICON-EU | 2 days | 1.16 | 4.8 | 0.86 | 3.6 |
| ECMWF IFS | same day | 1.33 | 6.2 | 0.93 | 2.5 |
| ECMWF IFS | 1 day | 1.36 | 6.9 | 0.90 | 3.3 |
| ECMWF IFS | 2 days | 1.35 | 6.9 | 0.86 | 3.5 |
| "Tomorrow like today" | — | — | 6.7 | 0.59 | — |

- **All three follow the weather** far better than assuming tomorrow will be like today.
- **ICON forecasts 10–20 % too much**, about what real losses (inverter, temperature, wiring) take; **ECMWF a third too much**.
- **The excess grows towards winter**: forecast ÷ measured in November 1.29–1.32 for ICON-D2, about 1.5 for ECMWF. A fixed loss factor won't fit; low sun, shading, snow or fog the models miss are candidates.
- **Hourly, one day ahead** (hours with production or forecast above 50 Wh): correlation 0.84–0.86; error 590–610 Wh per hour for the ICON models, 760 Wh for ECMWF.
- **Production peaks 0.25–0.45 h earlier than forecast** in every month (production-weighted mean hour: measured 11.5–12.1 h UTC, ECMWF 12.0–12.4 h UTC). Afternoon shading or an orientation other than the configured one would do this; not checked.

## Caveats

- Three months, late summer into autumn, one site.
- "Error after scaling" divides each forecast by its own ratio, fitted on the same days it is tested on, so it is optimistic.
- ICON-D2 reaches 48 h, so it has no two-day lead. Open-Meteo moves the ICON models to their native grid on 2026-11-30; analyses should split at that date.
- forecast.solar is not included: the archive has kept it only since 2026-11-21.

## Method

- Forecast: hourly values labelled by the end of their hour (Open-Meteo's convention); a day counts only if all 24 UTC hours have values.
- Measured: the inverter's 5-minute mean powers of both inputs (`logger.minutes_ea_log_ts`, `…eb…`), value / 12 = Wh, summed per UTC hour; a day counts only if all 288 records are there.
- **The inverter's clock follows local time.** Its offset from UTC is recorded only since 2026-11-22 (7584 s). The production-weighted mean hour jumps by about 1.3 h at 2026-10-25, the end of summer time, so before that date the clock was an hour further ahead; the tool corrects records by the change in the UTC offset of the local time zone. Inferred from the data, not from a recorded clock.
