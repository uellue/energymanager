# Spec Delta

## Purpose

One Home Assistant dashboard shows a site's heat pump, electricity and forecasts together, replacing the vendors' separate apps, and shows production against the forecasts.

## ADDED Requirements

### Requirement: One dashboard with all sources
The dashboard SHALL show on one page:
- outdoor, room, floor supply and hot-water temperature;
- heat pump energy, solar power, battery state of charge, household load, and grid import and export;
- the solar forecast and the weather forecast for the next 48 h, or as far as the service provides.

#### Scenario: E1 values visible
- **WHEN** the person opens the dashboard with all sources connected (E1)
- **THEN** every value listed above is visible on that page

### Requirement: Gaps shown as gaps
The dashboard's history charts SHALL show a period of unavailable data as a gap, not as a line drawn across it.

#### Scenario: Outage on the chart
- **WHEN** a source was unreachable for an hour (E2, E8)
- **THEN** that source's charts show a gap for that hour

### Requirement: Production against both forecasts
The dashboard SHALL show measured solar production against the solar forecast and against a production estimate derived from the weather forecast, over several days.

#### Scenario: Judging the forecasts
- **WHEN** several days of production and both forecasts have been recorded (E5)
- **THEN** one chart shows hourly production, the solar forecast and the weather-based estimate for those days

### Requirement: Dashboard kept in the repository
The dashboard definition SHALL be kept in the repository and SHALL refer only to entities, never to site-specific values.

#### Scenario: Moving to the mini PC (assumed)
- **WHEN** the stack is set up on a second machine with the same integrations
- **THEN** the same dashboard appears without being edited in the user interface
