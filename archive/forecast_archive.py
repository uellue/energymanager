"""Keep every solar and weather forecast as issued (spec: forecast-archive).

Once per hour, fetches the forecast.solar estimate and the Open-Meteo weather
forecast for the site and appends each raw response, with its fetch time and the
issue time the service states, to an SQLite database. Failed fetches are kept as
well. A read-only HTTP endpoint on 127.0.0.1 serves the hourly series that the
dashboard compares with measured production (example E5).

Settings come from environment variables only (see .env.example). Standard
library only.
"""

import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit

FORECAST_SOLAR = "forecast.solar"
OPEN_METEO = "open-meteo"
TIMEOUT_S = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetch (
    id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    fetched_at TEXT NOT NULL,   -- UTC, ISO 8601
    issued_at TEXT,             -- UTC, ISO 8601, as stated by the service; NULL if it states none
    http_status INTEGER,        -- NULL if no HTTP response arrived
    body BLOB,                  -- the response body, unchanged
    error TEXT                  -- NULL on success
);
CREATE INDEX IF NOT EXISTS fetch_service_time ON fetch (service, fetched_at);
CREATE TRIGGER IF NOT EXISTS fetch_no_update BEFORE UPDATE ON fetch
    BEGIN SELECT RAISE(ABORT, 'the forecast archive is append-only'); END;
CREATE TRIGGER IF NOT EXISTS fetch_no_delete BEFORE DELETE ON fetch
    BEGIN SELECT RAISE(ABORT, 'the forecast archive is append-only'); END;
"""


@dataclass(frozen=True)
class Service:
    name: str
    url: str
    issued_at: Callable[[bytes], str | None]


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_time(text: str) -> datetime:
    t = datetime.fromisoformat(text)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def forecast_solar_issued_at(body: bytes) -> str | None:
    """forecast.solar states the time it computed the response in message.info.time_utc."""
    return iso(parse_time(json.loads(body)["message"]["info"]["time_utc"]))


def no_issue_time(body: bytes) -> None:
    """Open-Meteo states no issue time."""
    return None


def services_from_env(env=os.environ) -> list[Service]:
    lat, lon = env["EM_LATITUDE"], env["EM_LONGITUDE"]
    dec, az, kwp = env["EM_DECLINATION"], env["EM_AZIMUTH"], env["EM_KWP"]
    open_meteo_query = urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,cloud_cover,global_tilted_irradiance",
        "tilt": dec, "azimuth": az, "forecast_days": 3, "timezone": "UTC",
    })
    return [
        Service(FORECAST_SOLAR,
                f"https://api.forecast.solar/estimate/{lat}/{lon}/{dec}/{az}/{kwp}?time=utc",
                forecast_solar_issued_at),
        Service(OPEN_METEO, f"https://api.open-meteo.com/v1/forecast?{open_meteo_query}",
                no_issue_time),
    ]


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def attempted_this_hour(conn, service: str, now: datetime) -> bool:
    hour = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    row = conn.execute(
        "SELECT 1 FROM fetch WHERE service = ? AND fetched_at >= ? AND fetched_at < ?",
        (service, iso(hour), iso(hour + timedelta(hours=1))),
    ).fetchone()
    return row is not None


def fetch_once(conn, service: Service, now: datetime) -> str:
    """Fetch one service unless it was already tried this hour. Returns what happened."""
    if attempted_this_hour(conn, service.name, now):
        return "skipped"
    status, body, issued_at, error = None, None, None, None
    request = urllib.request.Request(service.url, headers={"User-Agent": "energymanager"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, body, error = e.code, e.read(), f"HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        error = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
    if error is None:
        try:
            issued_at = service.issued_at(body)
        except (ValueError, KeyError, TypeError) as e:
            error = f"unreadable response: {type(e).__name__}"
    conn.execute(
        "INSERT INTO fetch (service, fetched_at, issued_at, http_status, body, error)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (service.name, iso(now), issued_at, status, body, error),
    )
    return error or "ok"


def fetch_all(conn, services, now: datetime) -> dict[str, str]:
    return {s.name: fetch_once(conn, s, now) for s in services}


def latest_before(conn, service: str, t: datetime) -> dict | None:
    """The latest successful forecast of a service fetched at or before t, or None."""
    row = conn.execute(
        "SELECT fetched_at, issued_at, body FROM fetch"
        " WHERE service = ? AND error IS NULL AND fetched_at <= ?"
        " ORDER BY fetched_at DESC LIMIT 1",
        (service, iso(t)),
    ).fetchone()
    if row is None:
        return None
    return {"fetched_at": row[0], "issued_at": row[1], "body": row[2]}


def forecast_solar_hourly_wh(body: bytes) -> dict[datetime, float]:
    """Energy per hour, keyed by the hour's start (UTC).

    watt_hours_period holds the energy of the period ending at each timestamp; a
    period is counted in the hour its end falls into, (start, start + 1 h].
    """
    hourly: dict[datetime, float] = {}
    for stamp, wh in json.loads(body)["result"]["watt_hours_period"].items():
        end = parse_time(stamp)
        start = (end - timedelta(microseconds=1)).replace(minute=0, second=0, microsecond=0)
        hourly[start] = hourly.get(start, 0.0) + wh
    return hourly


def open_meteo_hourly_wh(body: bytes, kwp: float) -> dict[datetime, float]:
    """Weather-based production estimate per hour, keyed by the hour's start (UTC).

    Open-Meteo's irradiance at time T is the mean over the preceding hour. The
    estimate is the plane's peak power at 1000 W/m²: GTI × kWp, in Wh per hour,
    with no loss factor, so it is an upper estimate (design D6).
    """
    hourly = json.loads(body)["hourly"]
    return {
        parse_time(stamp) - timedelta(hours=1): gti * kwp
        for stamp, gti in zip(hourly["time"], hourly["global_tilted_irradiance"])
        if gti is not None
    }


def e5_series(conn, now: datetime, days: int, kwp: float) -> list[dict]:
    """Per hour of the last `days` days: the latest forecasts issued before the hour began."""
    end = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    series = []
    cache: dict[tuple, dict] = {}
    for h in range(days * 24, 0, -1):
        start = end - timedelta(hours=h)
        entry = {"start": iso(start)}
        for service, key, parse in (
            (FORECAST_SOLAR, "solar_forecast", forecast_solar_hourly_wh),
            (OPEN_METEO, "weather_estimate", lambda b: open_meteo_hourly_wh(b, kwp)),
        ):
            issue = latest_before(conn, service, start)
            value = None
            if issue is not None:
                cache_key = (service, issue["fetched_at"])
                if cache_key not in cache:
                    cache[cache_key] = parse(issue["body"])
                value = cache[cache_key].get(start)
            entry[key + "_wh"] = value
            entry[key + "_fetched_at"] = issue["fetched_at"] if issue else None
        series.append(entry)
    return series


def make_handler(db_path: str, kwp: float, clock=lambda: datetime.now(timezone.utc)):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path != "/e5":
                self.send_error(404)
                return
            try:
                days = int(parse_qs(url.query).get("days", ["7"])[0])
            except ValueError:
                self.send_error(400, "days must be an integer")
                return
            days = max(1, min(days, 31))
            conn = connect(db_path)
            try:
                payload = json.dumps({"hours": e5_series(conn, clock(), days, kwp)}).encode()
            finally:
                conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    return Handler


def seconds_until_next_run(now: datetime, offset_min: int = 2) -> float:
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return (next_hour + timedelta(minutes=offset_min) - now).total_seconds()


def main():
    db_path = os.environ.get("EM_ARCHIVE_DB", "/data/forecasts.sqlite")
    bind = os.environ.get("EM_ARCHIVE_BIND", "127.0.0.1")
    port = int(os.environ.get("EM_ARCHIVE_PORT", "8765"))
    kwp = float(os.environ["EM_KWP"])
    services = services_from_env()
    conn = connect(db_path)
    server = ThreadingHTTPServer((bind, port), make_handler(db_path, kwp))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"forecast archive: {db_path}, endpoint http://{bind}:{port}/e5", flush=True)
    while True:
        now = datetime.now(timezone.utc)
        for name, outcome in fetch_all(conn, services, now).items():
            print(f"{iso(now)} {name}: {outcome}", flush=True)
        time.sleep(seconds_until_next_run(datetime.now(timezone.utc)))


if __name__ == "__main__":
    main()
