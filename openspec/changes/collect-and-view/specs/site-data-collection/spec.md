# Spec Delta

## Purpose

Records every measured source of a site (heat pump, inverter and battery, weather) at the rate the source delivers, keeps it indefinitely, and shows a missing source as missing, so that a model can later be fitted and tested on the record.

## ADDED Requirements

### Requirement: Sources recorded
The system SHALL record, read-only, from the pilot's sources:
- outdoor, room, leaving-water (floor supply, or tank inlet while heating hot water) and hot-water tank temperature, and heat pump energy, from the heat pump;
- solar power, battery state of charge, household load, and grid import and export, from the inverter.

#### Scenario: All E1 sources present
- **WHEN** the stack runs with the heat pump, the inverter and battery, the solar forecast and the weather forecast connected (E1)
- **THEN** each value listed above has a recorded history entity with a unit

#### Scenario: Nothing written to devices (assumed)
- **WHEN** the stack runs for a day
- **THEN** no command is sent to the heat pump or the inverter (requirements 2.11)

### Requirement: Recording rate
The system SHALL record each electrical value of the inverter at an interval of 1 min or less, and every other source at the rate it delivers (requirements 2.4).

#### Scenario: Inverter power at least every minute (assumed)
- **WHEN** the household load changes over 10 min
- **THEN** the record holds at least 10 values of household load for that period

### Requirement: Retention
The system SHALL keep recorded measurements indefinitely, without downsampling (requirements 2.4).

#### Scenario: Older than the default purge (assumed)
- **WHEN** a measurement is 11 days old
- **THEN** it is still in the record at its original resolution

### Requirement: Gaps recorded as missing
When a source is unreachable, the system SHALL record its values as unavailable for that period, never as a repeated or invented value.

#### Scenario: Source unreachable for an hour
- **WHEN** a source is unreachable for an hour (E2)
- **THEN** the record shows that hour as unavailable for every value of that source, and the values resume when it is reachable again

### Requirement: Mocked heat pump outage
The project SHALL provide a documented way to make the Daikin cloud unreachable for the stack without touching the unit. The entities SHALL then take the same states as in a real cloud outage.

#### Scenario: Mocked outage
- **WHEN** the mocked outage is switched on for an hour and then off (E8)
- **THEN** the heat pump's entities are unavailable for that hour, the record shows the gap, and the values resume afterwards

### Requirement: Site data stays local
Credentials, tokens and the site's location SHALL be kept in local files that git ignores. The recorded data SHALL stay on the site's machine (requirements 2.9).

#### Scenario: Fresh clone holds no site data (assumed)
- **WHEN** the repository is cloned after the pilot has been set up
- **THEN** the clone contains no credentials, tokens, coordinates or recorded data of the site
