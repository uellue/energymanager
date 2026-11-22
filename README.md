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

### Tests

```sh
python3 -I -m unittest discover -s tests
```
