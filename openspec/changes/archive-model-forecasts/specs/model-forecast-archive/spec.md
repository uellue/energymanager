## ADDED Requirements

### Requirement: Current forecasts of named models
The archive SHALL fetch, once per hour, Open-Meteo's forecast of global tilted irradiance on the site's roof plane from the models DWD ICON-D2, DWD ICON-EU and ECMWF IFS, hourly and in 15-minute steps, for at least the next 48 hours, independently of Home Assistant and of the other sources.

#### Scenario: A day of fetches (assumed)
- **WHEN** the archive runs for 24 h with Open-Meteo reachable
- **THEN** it holds 24 responses of this source, and each gives, per model, an irradiance value for every hour that model covers, labelled with the model's name

### Requirement: Past forecasts of named models
The archive SHALL fetch, once per UTC day, the same models' past forecasts from Open-Meteo's Previous Runs API for every hour up to the end of the previous UTC day: the value of the latest run, of the run one day earlier and of the run two days earlier. The first successful fetch SHALL reach back to 2026-08-27; each later fetch SHALL start early enough to cover the days since the last successful one.

#### Scenario: First fetch after deployment (assumed)
- **WHEN** the archive fetches past forecasts for the first time
- **THEN** the response covers every hour from 2026-08-27 to the end of the previous UTC day, with one-day-ahead values for all three models

#### Scenario: Fetches missed for some days (assumed)
- **WHEN** past-forecast fetches failed for three days and then one succeeds
- **THEN** the hours of those three days are in the successful response

### Requirement: Kept as fetched, failures recorded
The archive SHALL keep each response of both sources unchanged, with its fetch time and service name, in the same store as the other forecasts, and never overwrite or delete it. A failed fetch SHALL be recorded with its reason and SHALL NOT affect the other sources.

#### Scenario: Open-Meteo refuses one request (assumed)
- **WHEN** the named-model request fails and the other sources succeed
- **THEN** that hour has a failure entry for the named-model source and the other sources' responses are kept as usual
