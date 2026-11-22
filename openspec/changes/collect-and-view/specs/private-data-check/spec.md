# Spec Delta

## Purpose

Stops the household's private data and credentials from entering the public repository by checking every commit before it is made (requirements 2.9).

## ADDED Requirements

### Requirement: Commit refused on private data
Before each commit, the check SHALL scan the staged changes and refuse the commit if an added line contains a private IPv4 address, a geographic coordinate pair, or a token-like secret. It SHALL name the file, the line and the kind of finding, without printing the matched value.

#### Scenario: Private IP address (assumed)
- **WHEN** a staged file adds the line `host: 192.168.x.y`, with x and y digits
- **THEN** the commit is refused, with the file, the line number and "private IP address"

#### Scenario: Coordinates (assumed)
- **WHEN** a staged file adds a latitude or a longitude key with a value of 3 or more decimals, or a pair of such numbers separated by a comma or a slash (e.g. in a forecast.solar URL)
- **THEN** the commit is refused, with "coordinates"

#### Scenario: Token (assumed)
- **WHEN** a staged file adds a JSON Web Token or a long-lived access token
- **THEN** the commit is refused, with "token"

#### Scenario: Clean change (assumed)
- **WHEN** the staged changes contain none of these
- **THEN** the commit goes ahead, with no output from the check

### Requirement: Check is active after setup
The setup documentation SHALL include the one command that activates the check in a clone.

#### Scenario: Fresh clone (assumed)
- **WHEN** a person clones the repository and runs the documented command
- **THEN** the check runs at their next commit

### Requirement: Deliberate override
A person SHALL be able to commit despite a finding by skipping the hook deliberately with git's own option. The refusal message SHALL say how.

#### Scenario: False positive (assumed)
- **WHEN** the check refuses a line that is not private, such as a version number that looks like coordinates
- **THEN** the message names `git commit --no-verify` as the way to commit anyway
