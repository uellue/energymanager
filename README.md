# energymanager

Collects data from a home with a heat pump, solar power and a battery, and will plan the heat pump's operation to use more of the home's own solar power. The pilot is a Daikin Altherma with an RCT inverter and battery, connected through Home Assistant.

Status: early prototype. It is developed as a living lab: built, run and corrected in one real household, with real devices and real data, by a person working with coding agents. Expect gaps and changes. The design documents are in `design/`; the specifications are in `openspec/`.

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

### Private-data check

Every commit, including its message, is checked for private data of the site: private IP addresses, coordinates and tokens. Activate the check once per clone:

```sh
git config core.hooksPath .githooks
```

A commit with a finding is refused, with the file, the line and the kind of finding. Move the value to a file that git ignores, such as `.env`. If a finding is not private (for example a version number that looks like coordinates), commit anyway with `git commit --no-verify`.

To check files directly: `python3 -I tools/check_private_data.py --files <file>...`

### Forecast archive

Keeps every solar forecast (forecast.solar) and weather forecast (Open-Meteo) as it was issued, once per hour, in an SQLite database outside the repository. Needs Docker Engine with Compose.

1. Copy `.env.example` to `.env` and fill it in: the data folder and the roof plane. `.env` holds the site's location and is ignored by git.
2. Create the data folder: `mkdir -p "<EM_DATA_DIR>/forecasts"`
3. Start: `docker compose up -d --build archive`
4. Check: `docker compose logs archive` shows one line per service and hour, e.g. `forecast.solar: ok`. A restart within the same hour logs `skipped` and makes no call.

The database is `<EM_DATA_DIR>/forecasts/forecasts.sqlite`, table `fetch`: one row per attempt, with the service, the fetch time and the issue time (UTC), the HTTP status, the response body unchanged, and the error if the fetch failed. Rows are never changed or deleted. The response bodies contain the caller's public IP address and place name, so they belong in no repository.

The endpoint `http://127.0.0.1:8765/e5?days=7` returns, per hour of the last days, the latest solar forecast and the weather-based production estimate fetched before that hour began. The estimate is the irradiance on the roof plane × kWp, with no losses, so it is an upper estimate. The endpoint is reachable from this machine only.

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
- **RCT Power** (Marketplace, v0.14.2): the inverter's IP address and port 8899. Polls every 30 s by default.
- **Daikin Onecta** (Marketplace, v5.0.4): an application on the Daikin developer portal with the redirect URI `https://my.home-assistant.io/redirect/oauth`; enter its client ID and secret when Home Assistant asks. Polls every 10 min from 07:00 to 22:00 and every 30 min otherwise, about 108 of the 200 calls per day.

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

The server certificate is valid for 397 days. Renew it before then by running the script again with the same names, then `docker compose restart homeassistant`. The authority stays, so the devices need nothing new.

### Tests

```sh
python3 -I -m unittest discover -s tests
```
