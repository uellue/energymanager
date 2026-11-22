# Spec Delta

## Purpose

Reads the inverter's own logs, so that the record covers the time before it started and its gaps (E11).

## ADDED Requirements

### Requirement: Logs read back and kept
The collector SHALL read every time series the inverter logs (`logger.*`: 5-minute, daily, monthly and yearly series) back to the oldest entry the inverter returns, and then read the newest entries at least once an hour. It SHALL keep each entry once, with the series, the entry's timestamp as the inverter reports it, and the value, marked as coming from the inverter's log.

#### Scenario: Before the recording started
- **WHEN** the logs have been read once (E11)
- **THEN** the record holds the inverter's 5-minute state of charge, battery, grid and household values for the days before 2026-11-21, as far back as the inverter keeps them

#### Scenario: A gap filled
- **WHEN** the record has a gap of several hours, such as the night to 2026-11-22 (E11)
- **THEN** the inverter's 5-minute entries for that gap are in the record, and nothing marks them as measured by Home Assistant

#### Scenario: Read twice (assumed)
- **WHEN** the same period is read again
- **THEN** no entry is stored twice and no stored entry changes

### Requirement: Only log queries are written
To read a log, the collector SHALL send the inverter a write of a timestamp to a `logger.*` object, and nothing else. It SHALL send no write to any other object (requirements 2.3, exception of 2026-11-22).

#### Scenario: Writes limited (assumed)
- **WHEN** the collector's frames to the inverter are listed over a day
- **THEN** every write frame addresses a `logger.*` object and carries a timestamp

### Requirement: Gentle on the inverter
The collector SHALL space its log queries so that the Home Assistant integration keeps receiving values; a burst of queries SHALL pause when the integration's values stop.

#### Scenario: Integration keeps working during the first import (assumed)
- **WHEN** the first full import runs
- **THEN** the household load in Home Assistant has no gap longer than 2 minutes caused by it
