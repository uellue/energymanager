# Spec Delta

## Purpose

Keeps the heat pump's electrical energy per 2-hour period, which Daikin provides for yesterday and today only (E12, requirements 2.3).

## ADDED Requirements

### Requirement: Yesterday's periods kept daily
Once a day, after Daikin has published the previous day's last period, the collector SHALL store that day's twelve 2-hour periods of electrical energy, for space heating and for hot water, in kWh as Daikin reports them, with the period's start time in local time and UTC. It SHALL make no call to the Daikin cloud of its own; it SHALL take the values from what Home Assistant's Daikin integration already holds.

#### Scenario: A day recorded
- **WHEN** a day has passed (E12)
- **THEN** the record holds twelve values for space heating and twelve for hot water for that day, and their sum equals the integration's daily total for that day

#### Scenario: A missed day (assumed)
- **WHEN** the collector did not run on one day but runs the next
- **THEN** it stores the day that is still available as "yesterday", and the missed day stays missing; nothing is invented for it

### Requirement: Broken source noticed
When the values cannot be found where they were found before, the collector SHALL record the failure and raise an alert, and SHALL store nothing for that day.

#### Scenario: Integration updated (assumed)
- **WHEN** an update of the Daikin integration changes the format the values are taken from
- **THEN** an alert reaches the phone within a day, and the record has no wrong values for that day
