# Spec Delta

## Purpose

Keeps every solar and weather forecast exactly as it was issued, with its issue time, so that production can later be compared with what was forecast at a given lead time and test cases can use the forecasts known at the time.

## ADDED Requirements

### Requirement: Hourly fetch
The archive SHALL fetch the solar forecast and the weather forecast for the site once per hour. It SHALL run independently of Home Assistant (requirements 2.3).

#### Scenario: A day of fetches (assumed)
- **WHEN** the archive runs for 24 h with both services reachable
- **THEN** it holds 24 solar and 24 weather forecasts, each covering at least the next 24 h

#### Scenario: Home Assistant stopped (assumed)
- **WHEN** Home Assistant is stopped for an hour
- **THEN** the archive still fetches and keeps that hour's forecasts

### Requirement: Kept as issued
The archive SHALL keep each response unchanged, with the time it was fetched and the issue time the service states, if it states one. It SHALL never overwrite or delete a kept forecast.

#### Scenario: Comparing lead times
- **WHEN** solar and weather forecasts have been kept every hour for a week (E6)
- **THEN** for any hour of that week, the forecasts issued 1, 6 and 24 h before it can be read back, each with its issue time

### Requirement: Failed fetch recorded
When a fetch fails, the archive SHALL record the failure with its time and reason, keep running, and try again at the next hour.

#### Scenario: Service down (assumed)
- **WHEN** the solar forecast service is unreachable at one fetch
- **THEN** the archive holds a failure entry for that hour, and no forecast for that hour

### Requirement: Shared rate limits respected
The archive SHALL call each service at most once per hour, and SHALL leave room in forecast.solar's limit of 12 calls per hour per IP for Home Assistant's own calls.

#### Scenario: Restart loop (assumed)
- **WHEN** the archive container is restarted five times within an hour
- **THEN** it calls each service at most once in that hour

### Requirement: Readable from Python
The kept forecasts SHALL be readable from Python with the standard library only, selected by service and issue time.

#### Scenario: Read one issue (assumed)
- **WHEN** a script asks for the weather forecast issued closest before a given time
- **THEN** it gets that response unchanged, with its issue time
