# Design

## Context

The forecast archive (`archive/forecast_archive.py`) already holds the PV forecasts (forecast.solar and Open-Meteo, hourly, fetched every hour), the outdoor temperature history and forecast, and the baseline model of S4. It reads the collector's database read-only for `/control-strategies`. The collector's database holds the inverter's 5-minute records since 2026-08-27 without gaps longer than an hour (`logger.minutes_eload_log_ts` for household load, `…_soc_…` for the state of charge, `…_ea_…` for PV, `…_ebat_…` for the battery, `…_egrid_load_…` and `…_egrid_feed_…` for the grid), and daily household load since 2024-09-30. The 5-minute values are mean power in W over the 5 minutes, so a value / 12 is Wh (checked 2026-11-27: the sum over a day matches the daily series to the Wh). Their timestamps follow the inverter's clock, which ran 2 h 06 min ahead of UTC on 2026-11-27; the collector's table `clock` gives the offset at each query (`design/research/rct-onecta-data.md`). Home Assistant reports the battery's state-of-charge limits as 7 % and 97 % and a charge capacity of 25 Ah; the principal gave about 5 kWh usable and 5 kW (requirements, PV and battery). See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- A headroom forecast that runs on today's data and improves as data accumulate.
- A record that allows comparing this version with a later one based on the model's or optimizer's output.

**Non-Goals:**
- A view of forecast against actual; the record makes it possible, the view comes later.
- Forecasting EV charging or single appliances; they are part of the load curve's average.
- Controlling anything; the display only informs.

## Decisions

1. **Computed in the forecast archive, served at `/headroom`.** It has the forecasts, the baseline model and read access to the collector's records. Alternative: a new service, rejected (no second user). Agent's decision, reversible.
2. **PV forecast: forecast.solar, Open-Meteo's estimate when forecast.solar has no value for an hour, scaled by forecast.solar ÷ Open-Meteo over the hours both have (the estimate counts no losses; added while building, since forecast.solar covers only today and tomorrow); each hourly value spread evenly over its four quarter hours.** forecast.solar is set up for this array (7.92 kWp, tilt and azimuth). Alternative: the mean of both; left for the comparison that E18 enables. Agent's decision, reversible.
3. **Daily load curve: the mean share of each 15-minute slot in the day's load, per day type (Monday to Friday, weekend), over the last 28 days; the expected daily energy from a fit of the inverter's daily household load against heating degree days with a fitted base temperature, over the days since 2025-01-01** (the baseline's start in S4; the same form as `baseline_model`, daily instead of weekly, on load instead of cost; `inverter_days` reads these series already). The 28 days let the curve follow the season; the daily fit covers two winters. Alternatives: the weekly baseline model itself (weekly cost, no daily load; rejected, wrong quantity); one curve per heating and non-heating day (deferred until a winter has been recorded). The principal asked for the baseline model's weather dependence and a curve from the data; the details are the agent's, reversible.
4. **Battery simulated for self-consumption, in 15-minute steps.** It charges from surplus up to 5 kW and up to 97 % state of charge, discharges for deficit down to 7 %, and anything left goes to or from the grid. Usable energy = 5.7 kWh × 0.90. Round-trip efficiency from the inverter's lifetime counters of energy charged and discharged (91.6 % on 2026-11-27), split as its square root per direction; a constant, since the archive cannot read Home Assistant, where the counters are (changed while building). The simulation starts at the state of charge the collector now reads every minute (`battery.soc`, added at the principal's request on 2026-11-27, one more read per minute), and falls back to the latest 5-minute record, about an hour old, running over that gap on the forecast. The replay of task 2.2 showed the battery going down to 5.5–6 % rather than 7 %; left at 7 % (under 0.1 kWh). Inverter AC limit of 10 kW for PV plus battery. Calibration runs and the inverter's own state-of-charge targets are ignored. Agent's decision, reversible; checked in task 2.
5. **Headroom by bisection.** For each window, a bisection on the extra energy x (0 to 10 kWh, to 10 Wh) finds the largest x for which the simulated grid import over the horizon, plus any energy the battery holds less at the end of it, does not rise by more than 1 Wh (changed after the review: at 10 Wh, rounding showed 0.01 kWh where there was none, and charge left at the end of the horizon counted as free). That's 192 windows × about 10 simulations × 192 steps, well under a second in plain Python. Alternative: a linear programme (the research in issue #12); not needed while the battery follows a fixed rule. Agent's decision, reversible.
6. **Recorded every hour, not every 15 minutes:** a table `headroom_forecast` (made_at, step_start, pv_kwh, pv_corrected_kwh, load_kwh, soc, headroom_kwh, headroom_corrected_kwh) in the archive's database, about 4,600 rows a day. The actuals are not copied, since the collector keeps them. Agent's decision, reversible.
7. **Home Assistant:** a REST sensor `sensor.forecast_archive_solar_headroom` polled every 15 minutes, state = headroom of the next hour; attributes = the steps. The card is an apexcharts bar chart of headroom per window, with PV and load as lines, like the overview's other 48 h charts (changed while building from plotly, which the overview does not use). As for `/control-strategies`.
8. **Correction from today's production, computed and recorded but not shown.** Once the array has produced at least 1 kWh today, the rest of today's PV forecast is scaled by actual ÷ forecast of today so far; the next day is left as forecast. Both variants, with and without the correction, are computed and recorded (decision 6); the display uses the forecast without it until the analysis below shows the correction helps. A replay over the archived days since 2026-11-21 gives both variants' errors now, as a first look, not a verdict. The principal asked for the correction to be checked once there is enough data, not adopted on 7 days (2026-11-27); the 1 kWh threshold and the day boundary are the agent's, reversible.
9. **When the data suffice: a first analysis on 2027-01-31, a second on 2027-04-30.** Comparing two forecast variants day by day needs roughly 30 independent days to see a moderate improvement, and neighbouring days are not independent (weather lasts several days), so about twice that: 70 days from 2026-11-21 is the end of January. Those are short winter days only; the end of April adds long days and a sun high in the sky. Each analysis covers the two PV sources (E18), the correction, and the headroom's error against what happened (E25). Agent's estimate, a rough one; the principal set no date.

## Risks / Trade-offs

- [The inverter does not behave like the simple rule, e.g. it holds a reserve or follows its own targets] → Task 2 replays the last two weeks with actual PV and load and compares the simulated state of charge with the recorded one; a systematic deviation is reported before the display goes live.
- [Hourly PV values spread evenly over the hour] → Shifts headroom within the hour at dawn and dusk; acceptable for a one-hour window.
- [The load curve is an average; the washing machine the person plans is part of it] → Headroom is slightly underestimated on days when the appliance would run anyway; acceptable, it errs on the safe side.
- [The 5-minute records start on 2026-08-27, so the load curve has seen no full winter yet] → It follows the last 28 days and improves by itself; the README says how far to trust the figures.
- [The daily fit includes the baseline's heating behaviour; a different control strategy changes it] → Acceptable before the switchover; the record of E25 shows when it drifts.

## Migration Plan

New table and endpoint, no change to existing data. Rollback: revert the commit; the table can stay.

## Blocking questions

None. The build can start on the premises listed in proposal.md.
