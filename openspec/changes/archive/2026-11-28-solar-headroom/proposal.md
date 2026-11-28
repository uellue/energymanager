# Proposal: solar headroom, first version

## Why

The household decides by hand when to run the washing machine, dishwasher, oven self-cleaning or vehicle charging. A display of the solar headroom over the next 48 h (requirements S5, issue uellue-bot/energymanager#12) shows when that costs no grid import. The optimizer that S5 originally relied on does not exist yet. Everything a first estimate needs is recorded already: the PV forecasts, the inverter's 5-minute records since 2026-08-27, the battery's state, and the baseline model's weather dependence (S4). So a first version can run now and improve as data accumulate (principal, 2026-11-27).

Persona: P1, the pilot operator, who judges results on dashboards. Later P3, a household member, who only needs to read when to run what.

The request named a card that uses the control-strategy model for the weather-dependent load and a daily load curve. That is one solution to the need in S5. The need itself is to know when extra consumption is free of grid import. The chosen solution is the one recorded in S5 for the time before the optimizer exists.

## What Changes

- The forecast archive computes, every 15 minutes, the expected PV production and household load for the next 48 h in 15-minute steps, simulates the battery, and derives the solar headroom for each sliding one-hour window (the marginal figure of S5).
- The expected household load is a daily load curve from the inverter's 5-minute records, scaled to an expected daily energy fitted on the inverter's daily records since 2025-01-01. That energy has a part independent of the weather and a heating part from degree days with a fitted base temperature, as in the baseline model of S4.
- A new endpoint serves the result; a Home Assistant sensor holds it; a plotly card on the dashboard shows it.
- Every forecast run's predictions are recorded so they can later be compared with what the inverter recorded (E25). Comparing a model-based version against this one is a later step.
- Behaviour towards the user: a new card and a new sensor; nothing existing changes.

## Capabilities

### New Capabilities
- `solar-headroom`: the 48 h forecast of the solar headroom, its inputs (expected PV, expected household load, battery simulation), its display, and the record of its predictions.

### Modified Capabilities
None.

## Premises nobody has confirmed

- The inverter runs the battery for self-consumption: charging from surplus, discharging for deficit, within the state-of-charge limits it reports (7 % and 97 %). Its own state-of-charge targets and calibration runs are ignored. Task 2 checks the simulation against the recorded state of charge.
- The battery's round-trip losses: the inverter's lifetime counters give about 92 % (energy discharged over energy charged, read 2026-11-27); the power limit of 5 kW is the principal's figure.
- One daily load curve per day type (weekday or weekend) from recent weeks is good enough for a first version (principal: "doesn't have to be super accurate").

## Examples

Satisfied: E23, E24 and E26 (must), E25 (should). All four have scenarios.

## Impact

- `archive/forecast_archive.py`: new functions and an endpoint `/headroom`; a new table in the archive's database. It reads the collector's database read-only, as `/control-strategies` does.
- `collector/collector.py`: the battery's state of charge (`battery.soc`) is read every minute with the other live objects, read-only.
- `homeassistant/packages/forecast_archive.yaml`: one REST sensor. `homeassistant/dashboards/energymanager.yaml`: one card.
- README: a short section on what the headroom is and how far to trust it.
- No new dependency. Nothing writes to a device.
