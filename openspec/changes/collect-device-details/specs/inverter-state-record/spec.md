# Spec Delta

## Purpose

Records the inverter's battery and inverter state objects, raw, so that calibration and other special phases of the battery can be found in the record (requirements 2.3).

## ADDED Requirements

### Requirement: State recorded every minute
The collector SHALL read the inverter's battery state machine (`power_mng.state`), battery status (`battery.bat_status`, `battery.status`, `battery.status2`) and inverter status (`prim_sm.state`) at least once a minute and keep each raw value with the time it was read. It SHALL only read; it SHALL send no write to the inverter for these objects.

#### Scenario: A calibration recorded
- **WHEN** the battery runs a calibration (E10)
- **THEN** for every minute of it the record holds all five values, raw, so that a change at the calibration's start and end can be looked for without decoding the values first

#### Scenario: Inverter unreachable (assumed)
- **WHEN** the inverter does not answer for 10 minutes
- **THEN** those minutes have no values (a gap, E2), the failure is recorded with its time, and reading resumes when the inverter answers

### Requirement: Shown in Home Assistant
Home Assistant SHALL show the latest battery state machine value and the raw battery status as sensors, recorded by its recorder.

#### Scenario: Current state visible (assumed)
- **WHEN** the collector has read the inverter within the last 2 minutes
- **THEN** the dashboard shows both values with their time
