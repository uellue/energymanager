# energymanager

Collects data from a home with a heat pump, solar power and a battery, and will plan the heat pump's operation to use more of the home's own solar power. The pilot is a Daikin Altherma with an RCT inverter and battery, connected through Home Assistant.

Status: early prototype. It is developed as a living lab: built, run and corrected in one real household, with real devices and real data, by a person working with coding agents. Expect gaps and changes. The design documents are in `design/`; the specifications are in `openspec/`. The explanations here are written for readers who know some physics and maths but are not specialists in building energy.

License: MIT, see `LICENSE`.

## Setup

### Host

Runs on a Linux machine that stays on, in the same network as the inverter. Tested on Debian 13 (trixie), and on Debian 13 in WSL2 under Windows.

Required:

- Docker Engine with the Compose plugin, from Docker's apt repository (https://docs.docker.com/engine/install/debian/): `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`. Check: `sudo docker run --rm hello-world`.
- `git` to clone this repository.
- Python 3 to run the private-data check and the tests (Debian's `python3`; standard library only).
- Network: the inverter's TCP port 8899 reachable from the host, and outgoing HTTPS to the Daikin cloud, forecast.solar and Open-Meteo.

Recommended:

- No sleep, so the record has no gaps: `sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target` (undo with `unmask`). While the host sleeps, nothing is recorded, and Home Assistant's history draws the last value straight across the gap.
- Security updates: `sudo apt install unattended-upgrades`.
- `rsync` to copy the data folder between machines, `sqlite3` to look into the databases, `curl`.
- For a separate user that runs the stack: membership in the `docker` group (`sudo usermod -aG docker <user>`, effective at the next login). The group grants root-level access to the host.

Deploy with `tools/deploy.sh` in the host's clone (cloned from `uellue/energymanager`, so `origin` is the principal's repository). Without arguments it brings the clone to `origin/main` and starts the stack. `tools/deploy.sh --test BRANCH REASON` runs a branch of the fork `uellue-bot/energymanager` instead, for a test before review. Run the script without arguments to return to main. Both refuse when the clone has local changes or commits, or when `EM_DATA_DIR` is exported with a value other than the one in `.env`. Before starting the stack, both log the time, user, commit, branch and reason in `<EM_DATA_DIR>/deploy.log`: a line there means the code was checked out, not that the stack started. Both restart Home Assistant at the end, so that it reads the deployed packages and dashboards; its sensor history shows a gap of about a minute then, shortly after the time logged.

### Private-data check

Every commit, including its message, is checked for private data of the site: private IP addresses, coordinates and tokens. Activate the check once per clone:

```sh
git config core.hooksPath .githooks
```

A commit with a finding is refused, with the file, the line and the kind of finding. Move the value to a file that git ignores, such as `.env`. If a finding is not private (for example a version number that looks like coordinates), commit anyway with `git commit --no-verify`.

To check files directly: `python3 -I tools/check_private_data.py --files <file>...`

### Forecast archive

Keeps every solar forecast (forecast.solar) and weather forecast (Open-Meteo) as it was issued, once per hour, in an SQLite database outside the repository. Also once per hour, it keeps Open-Meteo's satellite-derived irradiance of the previous UTC day (service `open-meteo-satellite`): global horizontal, direct normal and diffuse irradiance, and the irradiance on the roof plane, each the mean of the hour before its time stamp. Once per day, it keeps Open-Meteo's historical hourly temperature up to the previous day (service `open-meteo-history`): the first fetch reaches back to January 2025, later ones start 14 days before the last successful fetch, since Open-Meteo still revises its most recent days and days missed while fetches failed are filled that way. Needs Docker Engine with Compose.

For comparing PV forecast sources, two more Open-Meteo services name the weather model each value comes from: DWD ICON-D2, DWD ICON-EU and ECMWF IFS. Every hour, `open-meteo-models` keeps their forecast of the irradiance on the roof plane for 4 days, hourly and in 15-minute steps (ICON-D2 reaches about 2 days). Once per day, `open-meteo-previous-runs` keeps their past forecasts up to the previous UTC day: for each hour, the value of the latest run and of the runs one and two days earlier (ICON-D2 has no two-day value). The first fetch reaches back to 27 August 2026, when the inverter's 5-minute records start; later ones start 3 days before the last successful fetch. In the response, each series carries the model in its name, e.g. `global_tilted_irradiance_previous_day1_ecmwf_ifs`, and each value is the mean over the hour (or quarter hour) before its time stamp.

1. Copy `.env.example` to `.env` and fill it in: the data folder and the roof plane. `.env` holds the site's location and is ignored by git.
2. Create the data folder: `mkdir -p "<EM_DATA_DIR>/forecasts"`
3. Start: `docker compose up -d --build archive`
4. Check: `docker compose logs archive` shows one line per service and hour, e.g. `forecast.solar: ok`. A restart within the same hour logs `skipped` and makes no call.

The database is `<EM_DATA_DIR>/forecasts/forecasts.sqlite`, table `fetch`: one row per attempt, with the service, the fetch time and the issue time (UTC), the HTTP status, the response body unchanged, and the error if the fetch failed. Rows are never changed or deleted. The response bodies contain the caller's public IP address and place name, so they belong in no repository.

To read the satellite irradiance of one hour from Python (values in W/m², `None` where the service had none; the latest response covering the hour is used):

```python
import sys; sys.path.insert(0, "archive")
from datetime import datetime, timezone
import forecast_archive as fa
conn = fa.connect("<EM_DATA_DIR>/forecasts/forecasts.sqlite")
fa.satellite_hour(conn, datetime(2026, 11, 22, 11, tzinfo=timezone.utc))  # the hour 11:00 to 12:00 UTC
```

Open-Meteo's data are under CC BY 4.0: wherever they are shown, credit Open-Meteo with a link (https://open-meteo.com/en/licence). The free API is for non-commercial use only.

The endpoint `http://127.0.0.1:8765/e5?days=7` returns, per hour of the last days, the latest solar forecast and the weather-based production estimate fetched before that hour began. The estimate is the irradiance on the roof plane × kWp, with no losses, so it is an upper estimate. The endpoint is reachable from this machine only.

A first try at comparing control strategies (examples E20 to E22; to be tested on the data): `http://127.0.0.1:8765/control-strategies` returns one entry per complete ISO week from January 2025: the household's net electricity cost (grid import × `EM_GRID_PRICE_EUR_PER_KWH` − feed-in × `EM_FEED_IN_PRICE_EUR_PER_KWH`), the week's mean outdoor temperature from Open-Meteo's history, the PV yield, and the solar spill (per day the smaller of grid import and feed-in, valued at the price difference). It also fits a baseline model on the baseline weeks (`model`) and gives every week the baseline's expected cost under that week's weather and the saving; see "Comparing control strategies" below. The energy comes from the inverter's daily logs, which the archive reads from the collector's store without writing to it. The dashboard's view "Control strategies" plots it with `plotly-graph-card`.

### Home Assistant

Runs as a container next to the archive, with its configuration in `<EM_DATA_DIR>/homeassistant`, outside the repository. The repository's `homeassistant/packages/` and `homeassistant/dashboards/` are mounted into it read-only.

1. Create the folder: `mkdir -p "<EM_DATA_DIR>/homeassistant"`
2. Start: `docker compose up -d homeassistant`, then open http://localhost:8123 and complete the onboarding.
3. Add to `<EM_DATA_DIR>/homeassistant/configuration.yaml`, below `default_config:`, and restart:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
4. Check: `docker compose exec homeassistant python -m homeassistant --script check_config -c /config --info recorder` shows `auto_purge: False`, with `packages/recorder.yaml` as its source.

The recorder keeps every measurement: its nightly purge is switched off.

Integrations:
- **forecast.solar:** location "home"; declination and modules power as in `.env`, with the power in W (7.92 kWp = 7920 W). Home Assistant counts the azimuth 0–360 from north, while the forecast.solar API and `.env` count from south. Enter `.env`'s azimuth + 180 (e.g. 55 → 235).
- **Open-Meteo:** zone "Home". Its weather entity is `weather.home_2`; `weather.home` is met.no from the onboarding.
- **Marketplace** (built in since 2026.11, formerly HACS): open it once and accept its warning. Custom integrations and cards are installed from there.
- **RCT Power** (Marketplace, v0.14.2): the inverter's IP address and port 8899. Polls every 30 s by default. Then hide `sensor.battery_at_rct_power_storage_battery_state_of_charge` (Settings › Entities › the sensor › settings › Visible: off). The integration gives the home battery's state of charge the device class `battery`, so the Maintenance dashboard flags it as a device battery running low whenever it is at 20 % or less. Hidden entities are left out there; the sensor keeps its history and statistics, and the project's dashboard names it explicitly, so it still shows there. Interim, until a proper fix (issue #7 in `uellue-bot/energymanager`).
- **Zigbee Home Automation (ZHA)**, for the room thermometer: the coordinator, a Home Assistant Connect ZBT-2 on USB, is passed into the container as `/dev/ttyACM0` (`EM_ZIGBEE_DEVICE` in `.env`). Add the integration with that serial port (EZSP radio, 460800 baud). Then "Add device" and put the thermometer into pairing mode as its manual says. Its temperature and humidity sensors are recorded like all others.
- **Daikin Onecta** (Marketplace, v5.0.4): an application on the Daikin developer portal with the redirect URI `https://my.home-assistant.io/redirect/oauth`; enter its client ID and secret when Home Assistant asks. Polls every 10 min from 07:00 to 22:00 and every 30 min otherwise, about 108 of the 200 calls per day.

Dashboard cards (Marketplace, category "Dashboard"; installing one also registers it as a dashboard resource):
- **apexcharts-card** (v2.2.3, MIT): the time-series charts.
- **plotly-graph-card** (v4.0.2, MIT, repository `dbuezas/lovelace-plotly-graph-card`): plots whose x-axis is not time, such as cost over outdoor temperature, with hover text per point.

To test how a Daikin cloud outage shows up without touching the unit, see `compose.mock-daikin-outage.yaml`.

### Alerts

Two layers. Home Assistant watches the sources and the host and sends a push to the phone (`homeassistant/packages/alerts.yaml`); an external service notices when Home Assistant or the whole host stops (a dead man's switch).

Alerts from Home Assistant, each repeated every 6 or 24 hours until resolved, with a message when it is:

| Alert | When |
|---|---|
| Inverter values missing | no value from `sensor.rct_power_storage_consumer_power` for 10 minutes |
| Heat pump values missing | no value from `sensor.altherma_climatecontrol_aussentemperatur` for 45 minutes (Onecta polls every 10 or 30 minutes) |
| Forecast archive unreachable | the archive's endpoint has not answered for 30 minutes |
| Disk nearly full | more than 90 % of the disk holding the configuration in use |
| HTTPS certificate expiring | less than 30 days left (only with "HTTPS on the home network") |

1. Install the Home Assistant app on the phone and log in; it registers a notify service `notify.mobile_app_<device>` (Developer tools → Actions lists it).
2. Add to `<EM_DATA_DIR>/homeassistant/configuration.yaml`, with that service, and restart:
   ```yaml
   notify:
     - platform: group
       name: energymanager
       services:
         - service: mobile_app_<device>
   ```
3. Check: Developer tools → Actions → `notify.energymanager` with a message arrives on the phone; Settings → Entities lists five `alert.energymanager_*`, all "Idle".

Dead man's switch, with healthchecks.io (free plan "Hobbyist", 20 checks; open source, could be self-hosted on another machine):

1. Create a check with period 5 minutes and grace time 10 minutes, and an email integration. Copy its ping URL.
2. Add to `<EM_DATA_DIR>/homeassistant/secrets.yaml` (the URL is the only secret; it stays on the host):
   ```yaml
   healthchecks_ping_url: https://hc-ping.com/<uuid>
   healthchecks_fail_url: https://hc-ping.com/<uuid>/fail
   ```
3. Add to `configuration.yaml` and restart:
   ```yaml
   rest_command:
     energymanager_ping:
       url: !secret healthchecks_ping_url
       method: post
     energymanager_ping_fail:
       url: !secret healthchecks_fail_url
       method: post

   automation energymanager:
     - alias: Energymanager heartbeat
       id: energymanager_heartbeat
       triggers:
         - trigger: time_pattern
           minutes: "/5"
       actions:
         - if:
             - condition: template
               value_template: >-
                 {{ states.binary_sensor
                    | selectattr('entity_id', 'search', '^binary_sensor\.energymanager_')
                    | selectattr('state', 'eq', 'on') | list | count > 0 }}
           then:
             - action: rest_command.energymanager_ping_fail
           else:
             - action: rest_command.energymanager_ping
   ```
   Home Assistant reports every 5 minutes. healthchecks.io emails when reports stop for 15 minutes (host or Home Assistant down), and when an alert from the table above is active, so problems also arrive by email.
4. Check: the check turns "up" in healthchecks.io within 5 minutes.

### HTTPS on the home network

Optional. Home Assistant serves HTTPS with a certificate from the site's own certificate authority, so browsers show no warning once a device trusts the authority, and passwords no longer cross the network unencrypted. Options and reasons: `design/research/remote-access-https.md`.

1. Create the authority and the server certificate, with every name and IPv4 address the browsers will use (here the PC's name on a FRITZ!Box network; add its LAN address too):
   ```sh
   tools/local_tls.sh "<EM_DATA_DIR>/tls" automation.fritz.box automation localhost 127.0.0.1
   ```
   The authority (`<EM_DATA_DIR>/tls/ca/`) may sign only server certificates, and only for these names, their subdomains and these IPv4 addresses; its key never leaves the host. Which browsers enforce these limits for an authority installed by hand is not verified, so treat the key like a password. `compose.yaml` mounts `<EM_DATA_DIR>/tls/server` into Home Assistant as `/ssl`; run `docker compose up -d homeassistant` after the first run.
2. Switch Home Assistant to HTTPS. Since 2026.11 it keeps these settings in its own storage and ignores `http:` in YAML. Change them through the WebSocket API (or the user interface): `http/config/configure` with the current `stable` settings from `http/config` plus `"ssl_certificate": "/ssl/server.crt", "ssl_key": "/ssl/server.key"`. Home Assistant restarts with the new settings and reverts to the old ones after 5 minutes unless confirmed.
3. Check: `curl --cacert "<EM_DATA_DIR>/tls/ca/ca.crt" https://automation.fritz.box:8123/` returns the page; then confirm with `http/config/promote`. Plain HTTP on port 8123 no longer answers.
4. On each device, install `<EM_DATA_DIR>/tls/ca/ca.crt` as a trusted certificate authority, after comparing its SHA-256 fingerprint with the one the script printed. Then open https://automation.fritz.box:8123.
   - Windows (Edge, Chrome): open the file, "Install Certificate…", "Current User", "Place all certificates in the following store": "Trusted Root Certification Authorities". To remove it: `certmgr.msc`, "Trusted Root Certification Authorities" → "Certificates", delete "energymanager home CA".
   - Firefox: Settings → Privacy & Security → Certificates → View Certificates → Authorities → Import, "Trust this CA to identify websites".
   - iPhone: open the file to install the profile, then switch it on under Settings → General → About → Certificate Trust Settings.
   - Android: Settings → Security → Encryption & credentials → Install a certificate → CA certificate, then pick the file from Downloads. The file picker may not list a file that arrived through a messenger; download it in the phone's browser from a web server that sends it as `application/x-x509-ca-cert` instead, for example for a few minutes with `python3 -m http.server 8080` in a folder holding only `ca.crt` (by IP address if the phone's Private DNS cannot resolve local names). The Home Assistant app accepts the authority (Android, 2026-11-22).
5. Tell Home Assistant its address: Settings → System → Network → "Home Assistant URL", switch off "automatic" and enter `https://automation.fritz.box:8123` (a name in the certificate) both for the local network and for the internet. From outside, Home Assistant is reached only through the VPN (`design/research/remote-access-https.md`), so the internet address is the same one; it has to resolve on the phone with the VPN on and mobile data. Without these addresses Home Assistant reports a repair "SSL is configured without an external or internal URL" and guesses its address where it builds links (app notifications, text-to-speech, sign-ins of integrations), and its log shows "Could not set up UPnP/SSDP server". The repair clears at the next restart.

The server certificate is valid for 397 days. Renew it before then by running the script again with the same names, then `docker compose restart homeassistant`. The authority stays, so the devices need nothing new.

### Collector

Records what the inverter and the heat pump hold beyond Home Assistant's entities, in an SQLite database outside the repository (`<EM_DATA_DIR>/collector/collector.sqlite`; why: `design/research/rct-onecta-data.md`):

- every minute, the inverter's battery and inverter state objects, raw (`power_mng.state`, `battery.bat_status`, `battery.status`, `battery.status2`, `prim_sm.state`), to find out how a battery calibration shows (E10);
- every minute as well, the maximum power point (MPP) tracker of PV input A, raw: the time of the last global MPP rescan (`dc_conv.last_rescan`), the voltage correction of that rescan (`dc_conv.dc_conv_struct[0].rescan_correction`) and the MPP voltage target (`dc_conv.dc_conv_struct[0].u_target`), so that a rescan can be told from shading (E14). A NaN answer cannot be stored and is left out as a gap, not recorded as a failure; these three objects do not count for the "state not read" alert;
- every minute as well, the battery's state of charge (`battery.soc`, a fraction), so that the solar headroom starts from the current value rather than the inverter's 5-minute log, which reaches the store only with the hourly catch-up; it does not count for the "state not read" alert either;
- the inverter's own logs (5-minute, daily, monthly and yearly series), first back to their oldest entry, then the newest entries every hour (E11);
- once a day after 03:00, yesterday's twelve 2-hour periods of the heat pump's electrical energy, for space heating and hot water, taken from the Daikin Onecta integration's diagnostics in Home Assistant, with no call to the Daikin cloud (E12).

**The one write to a device.** Reading the inverter's logs means writing a timestamp to a `logger.*` object, which the inverter answers with the entries logged before it. The code refuses any other write (requirements 2.3). Log timestamps follow the inverter's clock, which need not be UTC (on 2026-11-22 it ran on summer time, UTC+2); every query also stores that clock against the host's (table `clock`).

The inverter answers one client at a time and cuts answers when another client asks at once. The collector therefore reads one log query every 10 s, retries cut answers, and pauses the logs while the integration's household load in Home Assistant is not current.

1. Add to `.env`: the inverter's address `EM_RCT_HOST` (as in the RCT Power integration), and Home Assistant's API: `EM_HA_URL` and `HA_TOKEN` (a long-lived token: profile → Security). With "HTTPS on the home network": `EM_HA_URL=https://localhost:8123` and `EM_HA_CAFILE=/tls/ca.crt`.
2. Create the data folder for the container's user: `mkdir -p "<EM_DATA_DIR>/collector"`, then `docker compose run --rm --no-deps --user 0 --entrypoint chown collector 1000:1000 /data`.
3. Start: `docker compose up -d --build collector`
4. Check: `curl -s http://127.0.0.1:8766/status` shows the state values with their time, the last log read, the latest stored heat pump day, and how many log series are still being walked back. On the dashboard, "Battery state machine" and "Battery status" have values within 2 minutes. `homeassistant/packages/alerts.yaml` raises an alert when the state is not read for 10 minutes, the log for 3 hours, or yesterday's heat pump periods are missing at 06:00.

Failures are kept in table `failure` (part `state`, `log` or `energy`). The Daikin integration's diagnostics are not a stable interface; when an update changes them, nothing is stored for that day and the alert says so.

### Backup

Much of the collected data cannot be fetched again: the forecasts as they were issued, the heat pump's 2-hour periods once the cloud no longer has them, the inverter's 5-minute values once its own log has overwritten them. Back it up on demand from another machine, for example a laptop whose OneDrive folder is synced:

```sh
tools/backup_from_host.sh <user>@<host> "/mnt/c/Users/<you>/OneDrive/energymanager-backup"
```

Each run creates a folder named by the UTC time with one archive and its checksum. The script takes consistent snapshots of the collector's store, the forecast archive and Home Assistant's history while the stack runs (SQLite's own backup, not a file copy), adds the small data files in the data folder (`*.csv`, `*.tsv`, `deploy.log`, `unit/`, `weather-history/`), and checks the copy: checksum, unpacking, SQLite's integrity check of every store. Only a backup that passed all checks gets its final name; a failed run leaves a folder ending in `.partial`, or nothing. It changes nothing in the data folder and deletes no earlier backups. It needs ssh access to the host, room in the host user's home for about twice the stores' size, and reads the data folder from `.env` in the host's clone (`~/energymanager`, or `EM_BACKUP_CLONE`).

Left out on purpose, because they hold credentials and can be recreated: the certificate authority (`tls/`; run `tools/local_tls.sh` again and install the new authority on the devices), Home Assistant's configuration (`.storage/`, `secrets.yaml`: set up the integrations and the phone app again as described above) and `.env` (from `.env.example`, with a new Home Assistant token for the collector).

To restore, with the stack stopped: unpack the archive; it holds one folder `energymanager-backup-<time>/`. Copy that folder's contents into the data folder (so that, for example, `collector/collector.sqlite` lands in `<EM_DATA_DIR>/collector/`), and give the copied files the owner of the files they replace: uid 1000, the user the archive and the collector run as. Whether Home Assistant's history continues seamlessly after its configuration was set up again has not been tried; the entities would have to come back under the same names.

### Tests

```sh
python3 -I -m unittest discover -s tests
```

The collector's tests need `rctclient` and are skipped without it. To run them in the collector's image:

```sh
docker compose run --rm --no-deps -v "$PWD:/repo:ro" collector python3 -B -m unittest discover -s /repo/tests -p test_collector.py
```

## Comparing control strategies

The dashboard's view "Control strategies" answers one question: does a way of running the heat pump cost less than another? A way of running it is called a *control strategy*. The *baseline* is the strategy in use since January 2025: a fixed daily schedule for the heating curve and the hot-water tank (requirements S4). Later strategies come from the project's optimizer. The difficulty is that the weather never repeats. A cold, dull week costs more than a mild, sunny one, whatever the strategy. The view therefore compares each week with what the baseline would have cost *under that week's weather*.

The method is a first try: it may still change after it has been used on real comparisons. Requirements: `design/requirements.md`, S4, examples E20 to E22.

### What is counted

- **Net electricity cost per week**: grid import × grid price − feed-in × feed-in tariff, what the household actually pays for energy. The prices are settings (`EM_GRID_PRICE_EUR_PER_KWH` and `EM_FEED_IN_PRICE_EUR_PER_KWH` in `.env`), now 0.30 and 0.08 €/kWh. Fixed charges, such as the meter fee, are left out: no strategy changes them. The net cost can be negative in summer, when feed-in earns more than import costs.
- **Cost, not energy**, because cost is what the optimizer is to lower. A strategy may use *more* energy and still save. Example: heat the hot-water tank with its electric heater from cheap solar power to well above its usual 54 °C, and heat the house from the tank at night; the heat pump takes heat for the house from the tank first while the tank is above 55 °C. Counting kWh would call that a loss.
- **Weeks, not days**, because a good strategy moves consumption in time (for example, warming the house in a sunny afternoon so that it needs less heat at night), often across midnight. Over a week, that evens out. Months would even it out too, but give only about 23 points since January 2025, too few to fit and check a model, and a month mixes very different weather.
- **Solar spill per week**, shown in its own plot. For each day, take the smaller of the day's grid import and feed-in, and add these up over the week. If a day had both, the battery was full at some point and power went to the grid at 0.08 €/kWh, while other power was bought at 0.30 €/kWh, mostly at night. The battery easily covers the household's base load at night (100–200 W), so night-time import is mostly the heat pump's. A better strategy could in principle have run the heat pump while power was going to the grid, saving the difference of about 0.22 €/kWh. The spill is a diagnostic and is not part of the model. It matters most in February and March.

The energy figures come from the inverter's daily logs (household load, grid import, feed-in, PV yield) from January 2025; the outdoor temperature from Open-Meteo's history, hourly, averaged per day. Electric-vehicle charging is not recorded separately and adds noise: it is a household decision, not part of any strategy.

Whether the heat pump heated or cooled the house in a week comes from its 2-hour energy periods (collector, from 21 November 2026), which separate heating and cooling. For earlier weeks, the heat produced per month as read from the unit's display tells which months had no heating at all: put that table as `<EM_DATA_DIR>/unit/unit-panel-figures.csv`, with the columns `resolution` (`month`), `period_start` (e.g. `2026-06-01`) and `heating_produced_kwh`; the archive reads it, if present, without changing it. Weeks in which the heat pump cooled are left out of the fit, since cooling uses solar power that would otherwise be fed in. Cooling before 21 November 2026 was not recorded (briefly in 2026, from solar power only).

### How the expected cost is computed

This is a standard method of *measurement and verification*, the field that checks claimed energy savings. It is called an *adjusted baseline* in the IPMVP (International Performance Measurement and Verification Protocol); sources are in `design/research/weather-normalisation.md`.

1. Take the weeks that ran the baseline (all weeks so far).
2. Describe each week's weather by two numbers:
   - **Heating degree days (HDD)**: for each day, how many °C the daily mean outdoor temperature was *below* a base temperature, added up over the week. A day at 3 °C with a 15 °C base counts 12; a day at 16 °C counts 0. The idea: the house loses heat roughly in proportion to how much colder it is outside than inside, and up to the base temperature, people, appliances and the sun keep it warm without heating. The base temperature is the house's *heating limit* (German: *Heizgrenztemperatur*).
   - **PV yield**: the week's measured solar production in kWh. It stands for the sunshine. The site has no limit on feed-in, so the solar panels always produce what the sun allows, whatever the strategy does.
3. Fit grid import and feed-in per week, each by least squares as a straight-line combination of four terms: a constant, HDD, PV yield, and HDD × PV yield, for example import = a + b·HDD + c·PV + d·(HDD × PV). The product term is explained below.
4. Price the two fitted flows: expected cost = expected import × grid price − expected feed-in × feed-in tariff.
5. For any week, under any strategy: **saving = expected cost − actual cost**. Baseline weeks scatter around zero; a better strategy shows positive savings.

**Why the base temperature is fitted, not chosen.** It decides which days count as heating days. With 5 °C, all days between 5 and 15 °C would count as zero, although the house heats on them; the model would then miss that heating and add it to the scatter. The fit tries every base temperature from 8 to 20 °C in steps of 0.5 °C and keeps the one with the smallest error. This is the PRISM method (Fels 1986). Fixed conventions such as the German *Gradtagzahl G20/15* serve to compare different buildings and years; for one house, the fitted value is the usual choice. On this site's data it comes out at 15.5 °C, but any value from about 13 to 18 °C fits almost as well. Without the PV terms, the best value would be 12–13 °C, because the heating that sunny days save would then have to be expressed through the base temperature.

**Why the HDD × PV product.** Without it, one more kWh of solar power in a week would change the import by the same amount in every week, summer or winter. But what happens to that kWh depends on the season. In a warm week, the house needs little, the battery is full by noon and import is already near zero: the extra kWh goes to the grid. In a cold week, the heat pump and the house use everything the panels produce and still buy power: the extra kWh replaces bought power, and the sun through the windows also saves heating. With the product, the effect of one more kWh of PV is c + d·HDD instead of a constant c, so it can change with the cold; equally, a cold week costs less if it is also sunny. On this site's data, one more kWh of PV changes the import by about 0 kWh in a warm week and by −0.8 kWh in a cold week (100 degree days), and the feed-in by +1.0 and +0.5 kWh. The product also predicts weeks the model has not seen better: an error of 5.2 instead of 6.1 € per week overall, 6.6 instead of 7.9 € in the heating season. The published energy signatures with sun put the sun inside the heating term, so that it lowers heating only on days that need heating; summed over a week, that effect grows roughly with degree days × sunshine. The product is a weekly, straight-line version of that idea. What is new here is that it is applied to grid import and feed-in of a house with PV and a battery, where the share of solar power the house can use itself also depends on the cold. Its limits: cold weeks have little sun, so the term is least certain there; a very cold and very sunny week is extrapolation (see "Range" below); and the fitted numbers describe how the baseline behaved, not physical constants of the house, and are not bound by an energy balance.

**Why the energy flows are fitted, not the cost.** With fixed prices, both give exactly the same result: least squares is linear, and the cost is a fixed combination of import and feed-in. But fitted flows can be priced at *new* prices, so after a tariff change, baseline and strategy are priced alike without new baseline data. A fit of cost would keep the old prices in its coefficients. This is also what the IPMVP does: model energy, then apply prices.

**Why weeks without heating are in the fit.** They pin down the parts of the model that have nothing to do with heating: the household's base level and how sun turns into feed-in. In heating weeks, cold and dull usually come together, so the fit could hardly tell "expensive because cold" from "expensive because dark". Summer weeks break that tie. Fitted on heating weeks alone, the model predicted weeks it had not seen worse: an error of 7.1 instead of 5.2 € per week.

**Which parts are established.** The adjusted baseline, degree days with a fitted base temperature, solar radiation as a second variable, and pricing modelled energy are all published. Two parts are this project's own additions, with no source found: using the site's own PV yield instead of measured sunshine (irradiance), and the HDD × PV product.

### How good it is, and the whiskers

The *error per week* below is the root mean square of the weekly differences between actual and expected cost, in €. Two separate steps lead to the whiskers: a test, which produces an honest error for every baseline week, and a grouping, which decides whose errors a week's whiskers are made from.

**Step 1, the test: quarters of a year left out.** The error on the weeks the model was fitted on (*in sample*) is too optimistic for a week it has not seen, such as a week under a new strategy. So the model is refitted with one quarter of a year left out (December to February, March to May, June to August or September to November of one year), and that quarter's weeks are predicted by the model that has not seen them. This is repeated for every quarter, so that every baseline week gets one such *out-of-sample* error. A whole quarter rather than single weeks, because neighbouring weeks are alike (weather spells, habits): with single weeks left out, the weeks just before and after would still be in the fit and give the answer away. The quarters only serve this test; they play no part in the grouping.

**Step 2, the grouping: inside and outside the heating season.** Weeks with heating are much harder to predict than weeks without, so one error for all weeks would be too wide for summer and too narrow for winter. The weeks are therefore split into two groups, and the out-of-sample errors from step 1 are combined within each group: on this site about 6.6 € per week in the heating season and 2.1 € outside it. A baseline week belongs to the heating season if the heat pump heated in it. Where that is not known, and for every week of another strategy (which itself decides whether to heat), the week counts if its mean outdoor temperature is below the base temperature.

**The whiskers** of each week are ± two errors of its group, so about ±13 € in the heating season and ±4 € outside it. That is roughly the range in which the true saving lies around the value shown (about 95 % if the errors were independent and normally distributed).

Further figures:
- **R²** (0.97 on this site, for the model described here) looks better than the heating season is, because the summer weeks are easy to predict and spread the costs widely. Read the errors instead. (The research note quotes 0.94 for an earlier variant of the model.)
- **Lag-1 autocorrelation of the errors** (0.37 on this site): an error in one week tends to continue into the next, through weather spells or habits. The weeks are then less independent than they look, and a saving added up over several weeks is less certain than the whiskers of single weeks suggest.
- **Range**: the baseline weeks span a range of degree days and of PV yield. A week is flagged if either value lies below 90 % of the baseline's smallest value or above 110 % of its largest; the model would be extrapolating there.

In short: a strategy has to save clearly more than about 13 € in a single heating week to stand out on its own. Smaller savings show only as a pattern over many weeks.

### Known limits

- **Straight lines where reality has kinks.** Feed-in cannot be negative, but the fit expects slightly negative values in some winter weeks (about 1 € per week at most).
- **The base consumption is assumed the same all year.** More lighting and more time indoors in winter end up in the HDD term of step 3. For predicting the baseline that is harmless, since those habits recur every winter, but the HDD coefficient is no clean figure for the house's heat demand.
- **Days.** The inverter's daily logs follow its own clock, which still runs on summer time (UTC+2) since it was last set. In winter its day therefore ends an hour before local midnight (at 23:00); over a week this is negligible.
- **Flexible tariffs.** With prices that change by the hour, weekly totals are not enough: the baseline's import and feed-in would be needed hour by hour. That needs a *simulated* baseline (a model of the house and heat pump running the baseline's schedule under the actual weather), which is planned.
- **A better test design.** For an evaluation period, strategies may be switched week by week (above all in February and March), so that the weather affects both alike. The dashboard and the records must then always show which strategy was active.

## Solar headroom

The card "Solar headroom, next 48 h" on the overview answers: when can the washing machine, the dishwasher, the oven's self-cleaning or vehicle charging run without buying power from the grid? There is one green bar per quarter hour. Each shows the *solar headroom* of the hour that starts there: the extra energy, in kWh, that can be used in that hour without more grid import anywhere in the next 48 h. Energy in one hour is the same number as the mean power in kW, so a bar of 2 means about 2 kW for that hour.

To use it: pick a start where the bar is at least what the appliance uses in an hour (look it up on the appliance or measure it once). Bars overlap and draw on the same surplus, so the headrooms of two hours do not add up: for two appliances, or a longer run, take the lower of the bars an hour apart and treat it as shared. Requirements: `design/requirements.md`, S5, examples E23 to E26.

It counts the battery. On a sunny day the battery may be full by early afternoon, and the rest goes to the grid. Energy used in the late morning is then not lost: the battery charges a little less and still fills up from what would otherwise have been fed in. So the headroom starts before feed-in does (E23). On a winter evening, or a clear winter day whose sun never fills the battery, there is no headroom: whatever is used then is bought sooner or later (E24, E26).

### How it is computed

The forecast archive (the service described under "Forecast archive" above) computes it every 15 minutes and serves it at `/headroom`, from three parts:

1. **Solar power**: forecast.solar's hourly solar forecast for these panels, spread evenly over the quarter hours. Where forecast.solar has no value (it covers today and tomorrow), Open-Meteo's estimate is used, scaled to forecast.solar's level over the hours both have, since Open-Meteo's estimate leaves out the losses in panels, cabling and inverter.
2. **Household load**: a daily load curve times an expected daily energy. The curve is the share of each quarter hour in a day's load, averaged over the last 28 days, separately for weekdays and weekends, from the inverter's 5-minute records. The daily energy is fitted on the inverter's daily records since January 2025 in the same way as the baseline in "Comparing control strategies": a constant plus a term for heating degree days. One degree day is one day whose mean outdoor temperature is 1 °C below a base temperature, which the fit chooses; the day's mean temperature comes from Open-Meteo's forecast. On this site the fit gives about 9.6 kWh a day plus 1.7 kWh per degree day below 13.5 °C (2026-11-27).
3. **Battery**: simulated in quarter hours from its current state of charge, which the collector reads every minute. It charges from surplus and discharges for any shortfall, up to 5 kW, between 7 % and 97 % of 5.7 kWh. Over a full charge and discharge it loses 8.4 % of the energy, as derived from the inverter's lifetime counters. Replayed on 14 recorded days with the actual solar power and load, the simulated state of charge stayed within 1–3 percentage points of the recorded one, except on 21 November 2026, when the battery ran a calibration (a full charge it does now and then, which the simple rule does not follow).

The headroom of an hour is then found by trying: add extra consumption to that hour, simulate the 48 h again, and take the largest amount that neither raises the grid import nor leaves the battery emptier at the end of the 48 h (the night after needs that energy).

### How far to trust it

- **The solar forecast is the largest source of error.** Over the first week, the actual daily totals were 0.8 to 2.3 times forecast.solar's. A day that turns out sunnier than forecast has more headroom than shown; a duller one, less.
- **The load is an average.** It already contains the appliances the household usually runs, so on a day you do run them, part of their energy is in the expected load and the real headroom is slightly higher than shown. The heat pump runs on its schedules, not evenly; the curve shows that only on average.
- **Missing data.** If the collector's live state of charge is more than five minutes old, the forecast starts from the inverter's 5-minute log, which arrives about an hour late, and simulates that hour from the forecast. If that is more than two hours old too, or the newest solar forecast is more than six hours old, the card says what is missing and shows no headroom.
- **A correction of the solar forecast is recorded, not shown.** Once the panels have produced at least 1 kWh in a day, the rest of that day's solar forecast can be scaled by what they produced against what was forecast. On 2027-01-31 and 2027-04-30 the recorded headroom forecasts, with and without it, are compared with what happened (issue uellue-bot/energymanager#17); the card switches to the corrected one only if it turns out better.
- **Every headroom forecast is kept.** Once an hour the forecast archive stores its 192 quarter hours, with and without the correction, in the table `headroom_forecast` of its database (`<EM_DATA_DIR>/forecasts/forecasts.sqlite`), so they can be compared with what the inverter recorded.
