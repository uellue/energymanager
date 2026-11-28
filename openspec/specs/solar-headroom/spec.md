# solar-headroom Specification

## Purpose
Forecast, for the next 48 h, how much energy the household can use in each coming hour without more grid import (the solar headroom of requirements S5), show it in Home Assistant, and record each forecast against what then happened.

## Requirements

### Requirement: Headroom forecast in 15-minute steps
The forecast archive SHALL provide, at least every 15 minutes, a forecast for the next 48 h in 15-minute steps. For each step it gives the expected PV production, the expected household load, the expected battery state of charge, and the solar headroom of the one-hour window starting at that step, in kWh.

#### Scenario: A full forecast
- **WHEN** a PV forecast for the next 48 h, the inverter's recent records and the battery's state of charge are available
- **THEN** the forecast has 192 steps, each with a start time in UTC, PV, load and headroom in kWh and a state of charge (assumed)

#### Scenario: An input is missing
- **WHEN** no PV forecast newer than 6 hours or no state of charge newer than 2 hours is available (the inverter's records reach the collector about an hour late)
- **THEN** the forecast reports which input is missing and gives no headroom values, never a value computed from stale or invented inputs (E2)

### Requirement: Headroom is the marginal figure
The headroom of a window SHALL be the largest extra energy, spread evenly over that hour, that leaves the total grid import over the 48 h horizon unchanged, with the battery operated for self-consumption within its limits (requirements S5).

#### Scenario: Battery would be full by early afternoon
- **WHEN** a sunny day is forecast and the battery would be full by early afternoon, with the rest of the solar power fed in
- **THEN** windows in the late morning already have headroom, before feed-in starts (E23)

#### Scenario: No sun until morning
- **WHEN** no solar power is forecast until the next morning and the battery will be empty before then
- **THEN** the windows in those hours have no headroom (E24)

#### Scenario: Clear winter day, battery never full
- **WHEN** a cold, clear winter day is forecast whose PV production never exceeds the household load by enough to fill the battery
- **THEN** no window of that day has headroom, although PV production is forecast (E26)

### Requirement: Expected household load
The expected household load SHALL be a daily load curve per day type (weekday or weekend), taken from the inverter's 5-minute records of recent weeks, scaled to the expected energy of that day. The expected energy of a day SHALL be a part independent of the weather plus a part proportional to the day's heating degree days, with the base temperature fitted to the data as in the baseline model (requirements S4, S5).

#### Scenario: A colder day expects more load
- **WHEN** two forecast days of the same day type differ only in their forecast mean outdoor temperature, both below the fitted base temperature
- **THEN** the colder day's expected load is higher, and the shape of the two days' curves is the same (assumed)

### Requirement: Display in Home Assistant
Home Assistant SHALL hold the forecast in one sensor, whose state is the headroom of the next hour in kWh and whose attributes hold the 192 steps; the dashboard SHALL show the headroom over the next 48 h in one chart, with the expected PV and load (requirements S5).

#### Scenario: Reading when to run the washing machine
- **WHEN** a person opens the dashboard
- **THEN** one chart shows the headroom per hour window over the next 48 h, and the hours with headroom can be told from those without at a glance (E23)

### Requirement: Predictions recorded against actuals
Each hour, the forecast archive SHALL record the forecast it serves: per step, the expected PV, load, state of charge and headroom, with the time the forecast was made. The actual PV, load and state of charge come from the inverter's 5-minute records, which are kept already (E25).

#### Scenario: Corrected and uncorrected PV side by side
- **WHEN** the array has produced at least 1 kWh today and more or less than forecast
- **THEN** the record holds, for the rest of today, the forecast as issued and the forecast scaled by today's actual ÷ forecast so far, each with its headroom; the display shows the forecast as issued (assumed)

#### Scenario: A day later
- **WHEN** a day has passed since a forecast was recorded
- **THEN** for each 15-minute step of that day, the forecast's values and the inverter's recorded values can be read side by side by time (E25)
