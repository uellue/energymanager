"""Keep every solar and weather forecast as issued (spec: forecast-archive).

Once per hour, fetches the forecast.solar estimate, the Open-Meteo weather
forecast and Open-Meteo's satellite irradiance of the past day and today so far for the site
(spec: satellite-radiation-archive) and appends each raw response, with its
fetch time and the issue time the service states, to an SQLite database. Once
per day it also fetches Open-Meteo's historical hourly temperature (first from
January 2025, then from two weeks before the last successful fetch, since
Open-Meteo still revises its most recent days). For comparing PV forecast
sources it also fetches, every hour, Open-Meteo's irradiance forecast on the roof
plane from three named weather models, and once per day the same models' past
forecasts (from 2026-08-27 on; spec: model-forecast-archive). Failed
fetches are kept as well. A read-only HTTP endpoint on 127.0.0.1 serves the
hourly series that the dashboard compares with measured production (example E5)
and, as a first try, the weekly electricity cost over outdoor temperature
(examples E20, E21), from the collector's store of the inverter's daily logs.

Settings come from environment variables only (see .env.example). Standard
library only.
"""

import csv
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

FORECAST_SOLAR = "forecast.solar"
OPEN_METEO = "open-meteo"
SATELLITE = "open-meteo-satellite"
HISTORY = "open-meteo-history"
HISTORY_START = date(2025, 1, 1)  # the baseline's start (requirements S4)
HISTORY_REVISE_DAYS = 14  # Open-Meteo still revises the most recent days of its history
SATELLITE_MODEL = "dwd_sis_europe_africa_v4"  # DWD's product from EUMETSAT MTG, Europe
SATELLITE_VARIABLES = ("shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation",
                       "global_tilted_irradiance")
# Named weather models, so that each response says which model it came from (requirements S3).
MODELS = "open-meteo-models"
PREVIOUS_RUNS = "open-meteo-previous-runs"
NAMED_MODELS = ("dwd_icon_d2", "dwd_icon_eu", "ecmwf_ifs")
PREVIOUS_RUNS_START = date(2026, 8, 27)  # the inverter's 5-minute records start
PREVIOUS_RUNS_OVERLAP_DAYS = 3  # past runs do not change; the overlap covers missed days
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
    url: str | Callable[[sqlite3.Connection, datetime], str]  # a function: the URL depends on what is kept
    issued_at: Callable[[bytes], str | None]
    daily: bool = False  # fetched once per UTC day instead of once per hour


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
        # 4 days: the solar headroom's 48 h from late evening reach into the fourth UTC day.
        "tilt": dec, "azimuth": az, "forecast_days": 4, "timezone": "UTC",
    })
    satellite_query = urlencode({
        "latitude": lat, "longitude": lon, "hourly": ",".join(SATELLITE_VARIABLES),
        "tilt": dec, "azimuth": az, "past_days": 1, "forecast_days": 1, "timezone": "UTC",
        # The satellite product alone: the default "seamless" model fills hours not yet
        # observed with forecast values. With this one they stay null (checked 2026-11-23).
        "models": SATELLITE_MODEL,
    })
    def history_url(conn: sqlite3.Connection, now: datetime) -> str:
        """Hourly temperature up to yesterday (UTC), over daily_range."""
        start, end = daily_range(conn, HISTORY, now, HISTORY_START, HISTORY_REVISE_DAYS)
        query = urlencode({"latitude": lat, "longitude": lon, "start_date": start.isoformat(),
                           "end_date": end.isoformat(), "hourly": "temperature_2m", "timezone": "UTC"})
        return f"https://archive-api.open-meteo.com/v1/archive?{query}"

    models_query = urlencode({
        "latitude": lat, "longitude": lon, "models": ",".join(NAMED_MODELS),
        "hourly": "global_tilted_irradiance", "minutely_15": "global_tilted_irradiance",
        "tilt": dec, "azimuth": az, "forecast_days": 4, "timezone": "UTC",
    })

    def previous_runs_url(conn: sqlite3.Connection, now: datetime) -> str:
        """Past forecasts of the named models up to yesterday (UTC), over daily_range: per hour, the
        latest run's value and those of the runs one and two days earlier."""
        start, end = daily_range(conn, PREVIOUS_RUNS, now, PREVIOUS_RUNS_START, PREVIOUS_RUNS_OVERLAP_DAYS)
        query = urlencode({
            "latitude": lat, "longitude": lon, "models": ",".join(NAMED_MODELS),
            "hourly": ",".join(f"global_tilted_irradiance{lead}"
                               for lead in ("", "_previous_day1", "_previous_day2")),
            "tilt": dec, "azimuth": az, "start_date": start.isoformat(), "end_date": end.isoformat(),
            "timezone": "UTC",
        })
        return f"https://previous-runs-api.open-meteo.com/v1/forecast?{query}"

    return [
        Service(FORECAST_SOLAR,
                f"https://api.forecast.solar/estimate/{lat}/{lon}/{dec}/{az}/{kwp}?time=utc",
                forecast_solar_issued_at),
        Service(OPEN_METEO, f"https://api.open-meteo.com/v1/forecast?{open_meteo_query}",
                no_issue_time),
        Service(SATELLITE, f"https://satellite-api.open-meteo.com/v1/archive?{satellite_query}",
                no_issue_time),
        Service(HISTORY, history_url, no_issue_time, daily=True),
        Service(MODELS, f"https://api.open-meteo.com/v1/forecast?{models_query}", no_issue_time),
        Service(PREVIOUS_RUNS, previous_runs_url, no_issue_time, daily=True),
    ]


def daily_range(conn, service: str, now: datetime, first: date, overlap_days: int) -> tuple[date, date]:
    """The days a daily fetch covers, up to yesterday (UTC): from `first` until one fetch of the
    service has succeeded; then from `overlap_days` before the last successful fetch, so that days
    missed while fetches failed are filled as well."""
    end = now.astimezone(timezone.utc).date() - timedelta(days=1)
    (last,) = conn.execute("SELECT max(fetched_at) FROM fetch WHERE service = ? AND error IS NULL",
                           (service,)).fetchone()
    start = first
    if last is not None:
        start = max(first, parse_time(last).date() - timedelta(days=overlap_days))
    return start, end


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def attempted_this_hour(conn, service: str, now: datetime, daily: bool = False) -> bool:
    """Whether the service was tried in the current hour, or the current UTC day if `daily`."""
    start = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if daily:
        start = start.replace(hour=0)
    row = conn.execute(
        "SELECT 1 FROM fetch WHERE service = ? AND fetched_at >= ? AND fetched_at < ?",
        (service, iso(start), iso(start + (timedelta(days=1) if daily else timedelta(hours=1)))),
    ).fetchone()
    return row is not None


def fetch_once(conn, service: Service, now: datetime) -> str:
    """Fetch one service unless it was already tried this hour (or day). Returns what happened."""
    if attempted_this_hour(conn, service.name, now, service.daily):
        return "skipped"
    status, body, issued_at, error = None, None, None, None
    url = service.url(conn, now) if callable(service.url) else service.url
    request = urllib.request.Request(url, headers={"User-Agent": "energymanager"})
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


def satellite_hour(conn, start: datetime) -> dict | None:
    """Satellite irradiance (W/m²) of the hour beginning at `start`, from the latest response covering it.

    Open-Meteo labels each hourly value with the end of the hour it is the mean
    of, so the hour [start, start + 1 h) is the entry labelled start + 1 h.
    Returns the four quantities (None where the service had no value) and the
    response's fetch time, or None when no kept response covers the hour.
    """
    if start.tzinfo is None:  # naive times are UTC here, as in parse_time
        start = start.replace(tzinfo=timezone.utc)
    start = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    label = (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    rows = conn.execute(
        "SELECT fetched_at, body FROM fetch WHERE service = ? AND error IS NULL AND fetched_at > ?"
        " ORDER BY fetched_at DESC",
        (SATELLITE, iso(start)),
    )
    empty = None
    for fetched_at, body in rows:
        try:
            hourly = json.loads(body)["hourly"]
            i = hourly["time"].index(label)
            values = {name: hourly[name][i] for name in SATELLITE_VARIABLES}
        except (ValueError, KeyError, TypeError, IndexError):
            continue  # does not cover the hour, or not a readable response
        hour = {"start": iso(start), "fetched_at": fetched_at, **values}
        if any(v is not None for v in values.values()):
            return hour
        # All null: fetched before the hour was observed. An older response may have it.
        empty = empty or hour
    return empty


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


def history_temperatures(conn) -> dict[datetime, float]:
    """Open-Meteo's historical temperature (°C) at each UTC hour from the kept responses.

    A later response overrides an earlier one, since Open-Meteo revises its most
    recent days; a null value overrides nothing.
    """
    temps: dict[datetime, float] = {}
    rows = conn.execute("SELECT body FROM fetch WHERE service = ? AND error IS NULL ORDER BY fetched_at",
                        (HISTORY,))
    for (body,) in rows:
        try:
            hourly = json.loads(body)["hourly"]
            pairs = list(zip(hourly["time"], hourly["temperature_2m"]))
        except (ValueError, KeyError, TypeError):
            continue
        for stamp, value in pairs:
            if value is not None:
                temps[parse_time(stamp)] = value
    return temps


# The inverter's daily logs, as the collector keeps them (Wh; feed-in negative). PV yield is
# the sum of the two inputs A and B.
DAILY_SERIES = {"logger.day_eload_log_ts": "load", "logger.day_egrid_load_log_ts": "import",
                "logger.day_egrid_feed_log_ts": "feed", "logger.day_ea_log_ts": "pv_a",
                "logger.day_eb_log_ts": "pv_b"}


def inverter_days(collector_conn, start: date) -> dict[date, dict[str, float]]:
    """Household load, grid import and feed-in per day in kWh, from `start` on.

    The inverter stamps each daily entry 23:59:59 of its day by its own clock,
    which the collector keeps unchanged; the stamp's date is the day. That clock
    runs at UTC+2 (design/research/rct-onecta-data.md), so in winter its day ends
    one hour before local midnight; the temperature uses the local day, a
    difference that weekly means make negligible.
    """
    since = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    rows = collector_conn.execute(
        f"SELECT series, ts, value FROM log_entry WHERE series IN ({','.join('?' * len(DAILY_SERIES))})"
        " AND ts >= ? ORDER BY ts", (*DAILY_SERIES, since))  # the later entry of a date wins
    days: dict[date, dict[str, float]] = {}
    for series, ts, value in rows:
        day = datetime.fromtimestamp(ts, timezone.utc).date()
        days.setdefault(day, {})[DAILY_SERIES[series]] = abs(value) / 1000
    return days


def day_mean_temperature(temps: dict[datetime, float], day: date, tz: ZoneInfo) -> float | None:
    """Mean of the hourly temperatures of a local day, or None if an hour is missing."""
    start = datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(timezone.utc)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz).astimezone(timezone.utc)
    hours = [temps.get(start + timedelta(hours=h)) for h in range(int((end - start) / timedelta(hours=1)))]
    return None if None in hours else sum(hours) / len(hours)


def unit_months(path: str | None) -> dict[tuple[int, int], float]:
    """Heat produced for space heating per month (kWh), as read from the heat pump's own display
    into a CSV file kept outside the repository (columns resolution, period_start, ...,
    heating_produced_kwh). Empty if there is no such file or it cannot be read; rows that
    cannot be read are skipped. A byte-order mark, as spreadsheet programs write it, is fine."""
    if not path or not os.path.exists(path):
        return {}
    months = {}
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    if row["resolution"] == "month":
                        start = date.fromisoformat(row["period_start"][:10])
                        months[(start.year, start.month)] = float(row["heating_produced_kwh"])
                except (KeyError, ValueError, TypeError):  # a short or unreadable row
                    continue
    except (OSError, UnicodeDecodeError, csv.Error):
        return {}
    return months


def unit_days(collector_conn) -> dict[date, dict[str, float]]:
    """Space heating and cooling energy (kWh) per local day, from the heat pump's 2-hour
    periods that the collector keeps (management point climateControl)."""
    days: dict[date, dict[str, float]] = {}
    rows = collector_conn.execute(
        "SELECT day, mode, sum(kwh) FROM energy_period WHERE management_point = 'climateControl'"
        " GROUP BY day, mode")
    for day, mode, kwh in rows:
        days.setdefault(date.fromisoformat(day), {})[mode] = kwh
    return days


def heat_pump_modes(days: list[date], periods: dict, months: dict) -> tuple[bool | None, bool | None]:
    """Whether the heat pump heated, and whether it cooled, in these days; None if unknown.

    Heating is known to be on if the 2-hour periods show heating energy on any of the days,
    and known to be off if every day falls in a month with no heating at all on the unit's
    display. The periods alone do not prove it off: Daikin reports them in whole kWh, so
    light heating may show as 0. Cooling comes from the periods where all days have them.
    """
    heated = cooled = None
    if all(d in periods for d in days):
        if any(periods[d].get("heating", 0) > 0 for d in days):
            heated = True
        cooled = any(periods[d].get("cooling", 0) > 0 for d in days)
    if heated is None and all(months.get((d.year, d.month)) == 0 for d in days):
        heated = False
    return heated, cooled


def control_strategy_weeks(conn, collector_conn, grid_price: float, feed_in_price: float,
                           tz: ZoneInfo, months: dict | None = None) -> list[dict]:
    """A first try (examples E20 to E22): per ISO week from HISTORY_START, the household's
    net electricity cost over the week's mean outdoor temperature, and its solar spill.

    Net cost: grid import × grid_price − feed-in × feed_in_price, what the household pays.
    Spill per day: the smaller of import and feed-in, which a better shift of consumption
    could in principle have saved at grid_price − feed_in_price. Only weeks whose seven
    days all have the daily values and every hour's temperature. All weeks so far ran the
    baseline. `heated` and `cooled` say whether the heat pump heated or cooled the house that
    week (None: unknown; see heat_pump_modes). `daily_mean_c` (the seven daily mean
    temperatures) is for baseline_model.
    """
    try:
        periods = unit_days(collector_conn)
    except sqlite3.OperationalError:  # a collector store without the periods' table
        periods = {}
    temps = history_temperatures(conn)
    weeks: dict[tuple[int, int], list] = {}
    for day, e in sorted(inverter_days(collector_conn, HISTORY_START).items()):
        temperature = day_mean_temperature(temps, day, tz)
        if len(e) == len(DAILY_SERIES) and temperature is not None:
            weeks.setdefault(day.isocalendar()[:2], []).append((day, e, temperature))
    result = []
    for (year, week), days in sorted(weeks.items()):
        if len(days) != 7:
            continue
        total = {key: sum(e[key] for _, e, _ in days) for key in DAILY_SERIES.values()}
        spill = sum(min(e["import"], e["feed"]) for _, e, _ in days)
        heated, cooled = heat_pump_modes([d for d, _, _ in days], periods, months or {})
        result.append({
            "week": f"{year}-W{week:02d}", "start": days[0][0].isoformat(),
            "temperature_c": round(sum(t for _, _, t in days) / 7, 2),
            "daily_mean_c": [t for _, _, t in days],
            "cost_eur": round(total["import"] * grid_price - total["feed"] * feed_in_price, 2),
            "spill_kwh": round(spill, 1), "spill_eur": round(spill * (grid_price - feed_in_price), 2),
            "load_kwh": round(total["load"], 1), "import_kwh": round(total["import"], 1),
            "feed_kwh": round(total["feed"], 1), "pv_kwh": round(total["pv_a"] + total["pv_b"], 1),
            "heated": heated, "cooled": cooled,
            "strategy": "baseline", "result": "actual",
        })
    return result


# Base temperatures scanned when fitting the baseline model, 8 to 20 °C in steps of 0.5 K.
BASE_TEMPERATURES = tuple(b / 2 for b in range(16, 41))
MIN_BASELINE_WEEKS = 20


def least_squares(rows: list[list[float]], ys: list[float]) -> list[float]:
    """Ordinary least squares through the normal equations (a few regressors only)."""
    n = len(rows[0])
    a = [[sum(r[i] * r[j] for r in rows) for j in range(n)] + [sum(r[i] * y for r, y in zip(rows, ys))]
         for i in range(n)]
    tolerance = 1e-10 * max(abs(a[k][k]) for k in range(n))  # relative to the entries' size
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(a[k][i]))
        a[i], a[p] = a[p], a[i]
        if abs(a[i][i]) <= tolerance:
            raise ZeroDivisionError("the regressors are (nearly) linearly dependent")
        for k in range(i + 1, n):
            f = a[k][i] / a[i][i]
            a[k] = [x - f * z for x, z in zip(a[k], a[i])]
    c = [0.0] * n
    for i in reversed(range(n)):
        c[i] = (a[i][n] - sum(a[i][j] * c[j] for j in range(i + 1, n))) / a[i][i]
    return c


def regressors(week: dict, base: float) -> list[float]:
    """1, heating degree days below `base`, PV yield (kWh) and their product (scaled by 1/100)."""
    hdd = sum(max(0.0, base - t) for t in week["daily_mean_c"])
    return [1.0, hdd, week["pv_kwh"], hdd * week["pv_kwh"] / 100]


def quarter(week: dict) -> tuple[int, int]:
    """The quarter of a year the week's Monday falls in, December to February, March to May,
    June to August, September to November: (year of the January of its winter, 0-3)."""
    d = date.fromisoformat(week["start"])
    return (d.year + (d.month == 12), (d.month % 12) // 3)


def baseline_model(weeks: list[dict], grid_price: float, feed_in_price: float) -> dict | None:
    """A first try (example E22): the adjusted baseline of measurement and verification
    (design/research/weather-normalisation.md), fitted on the baseline weeks.

    Grid import and feed-in per week are each fitted against heating degree days below a
    base temperature, PV yield and their product; the base temperature is the one of
    BASE_TEMPERATURES with the smallest squared error of the priced result. Every week then
    gets the baseline's expected import, feed-in and net cost under that week's weather, and
    the saving = expected − actual cost. Checks: the error with each quarter of a year left out of the
    fit in turn (out of sample), overall and separately inside and outside the heating season,
    since weeks without heating are far easier to predict; the lag-1 autocorrelation of the
    residuals; and whether a week's degree days and PV yield lie within 90-110 % of the
    baseline's range. Each week's `band_eur` is two out-of-sample errors of its period.

    A baseline week is in the heating season if the heat pump heated in it (`heated`); where
    that is unknown, and for every week of another strategy, which itself decides whether to
    heat, if it was colder than the fitted base temperature, the house's heating limit. (The
    lowest mean temperature of the weeks known to be unheated was tried as the limit and
    rejected: one cold week in a month without heating put it at 11.4 °C, below weeks that
    were heated.) Weeks in which the heat pump cooled are
    left out of the fit, since cooling uses solar power that would otherwise be fed in.
    Adds the figures to the weeks in place; returns the model, or None with too few
    baseline weeks.
    """
    base_weeks = [w for w in weeks if w["strategy"] == "baseline" and w["result"] == "actual"
                  and not w.get("cooled")]
    if len(base_weeks) < MIN_BASELINE_WEEKS:
        return None
    costs = [w["cost_eur"] for w in base_weeks]

    def fit(ws, base):
        rows = [regressors(w, base) for w in ws]
        return (least_squares(rows, [w["import_kwh"] for w in ws]),
                least_squares(rows, [w["feed_kwh"] for w in ws]))

    def predict(coeffs, w, base):
        x = regressors(w, base)
        imp, feed = (sum(c * v for c, v in zip(cs, x)) for cs in coeffs)
        return imp, feed, imp * grid_price - feed * feed_in_price

    best = None
    for base in BASE_TEMPERATURES:
        try:
            coeffs = fit(base_weeks, base)
        except ZeroDivisionError:
            continue
        sse = sum((predict(coeffs, w, base)[2] - c) ** 2 for w, c in zip(base_weeks, costs))
        if best is None or sse < best[0]:
            best = (sse, base, coeffs)
    if best is None:
        return None
    sse, base, coeffs = best
    residuals = [c - predict(coeffs, w, base)[2] for w, c in zip(base_weeks, costs)]
    mean = sum(costs) / len(costs)
    out: dict[str, float] = {}  # each week's error, predicted with its whole quarter left out of the fit
    for s in sorted({quarter(w) for w in base_weeks}):
        rest = [w for w in base_weeks if quarter(w) != s]
        try:
            held = fit(rest, base)
        except ZeroDivisionError:  # a quarter the rest cannot predict: no out-of-sample error at all
            out = {}
            break
        out.update({w["start"]: w["cost_eur"] - predict(held, w, base)[2] for w in base_weeks if quarter(w) == s})

    def rms(errors):
        return (sum(e * e for e in errors) / len(errors)) ** 0.5 if errors else None

    rms_out = rms(list(out.values()))

    def period(w):
        """The heating season (Heizperiode): the baseline heated that week, or would have."""
        if w["strategy"] == "baseline" and w["result"] == "actual" and w.get("heated") is not None:
            return "heating" if w["heated"] else "outside"
        return "heating" if w["temperature_c"] < base else "outside"

    periods = {}
    for name in ("heating", "outside"):
        inside = [r for w, r in zip(base_weeks, residuals) if period(w) == name]
        held_out = [out[w["start"]] for w in base_weeks if period(w) == name and w["start"] in out]
        periods[name] = {"weeks": len(inside), "rms_eur": rms(inside), "rms_out_of_sample_eur": rms(held_out)}
    # Lag-1 autocorrelation over pairs of consecutive weeks only (weeks may be missing).
    starts = [date.fromisoformat(w["start"]) for w in base_weeks]
    pairs = [(residuals[k], residuals[k + 1]) for k in range(len(residuals) - 1)
             if starts[k + 1] - starts[k] == timedelta(weeks=1)]
    squares = sum(e * e for e in residuals)
    rho = sum(a * b for a, b in pairs) / squares if pairs and squares > 0 else None
    spread = sum((c - mean) ** 2 for c in costs)
    ranges = {}
    for i, name in ((1, "hdd"), (2, "pv_kwh")):
        values = [regressors(w, base)[i] for w in base_weeks]
        ranges[name] = (min(values), max(values))
    for w in weeks:
        x = regressors(w, base)
        imp, feed, cost = predict(coeffs, w, base)
        error = periods[period(w)]["rms_out_of_sample_eur"]
        w.update({
            "heating_period": period(w) == "heating",
            "hdd": round(x[1], 1), "expected_import_kwh": round(imp, 1),
            "expected_feed_kwh": round(feed, 1), "expected_cost_eur": round(cost, 2),
            "saving_eur": round(cost - w["cost_eur"], 2),
            "band_eur": round(2 * error, 2) if error is not None else None,
            "in_range": all(0.9 * lo <= x[i] <= 1.1 * hi
                            for i, (lo, hi) in zip((1, 2), ranges.values())),
        })

    def rounded(v):
        return round(v, 2) if v is not None else None

    return {
        "base_temperature_c": base, "baseline_weeks": len(base_weeks),
        "weeks_known_heated": sum(1 for w in base_weeks if w.get("heated") is True),
        "weeks_known_unheated": sum(1 for w in base_weeks if w.get("heated") is False),
        "cooling_weeks_left_out": sum(1 for w in weeks if w["strategy"] == "baseline"
                                      and w["result"] == "actual" and w.get("cooled")),
        "r2_cost": round(1 - sse / spread, 3) if spread > 0 else None,
        "rms_cost_eur": round((sse / len(costs)) ** 0.5, 2),
        "rms_out_of_sample_eur": rounded(rms_out),
        "periods": {name: {"weeks": s["weeks"], "rms_eur": rounded(s["rms_eur"]),
                           "rms_out_of_sample_eur": rounded(s["rms_out_of_sample_eur"])}
                    for name, s in periods.items()},
        "lag1_autocorrelation": round(rho, 2) if rho is not None else None,
        "import_coefficients": [round(c, 4) for c in coeffs[0]],
        "feed_coefficients": [round(c, 4) for c in coeffs[1]],
        "range_hdd": [round(v, 1) for v in ranges["hdd"]],
        "range_pv_kwh": [round(v, 1) for v in ranges["pv_kwh"]],
    }


def headroom_payload(db_path: str, collector_db: str | None, now: datetime, kwp: float, tz: ZoneInfo,
                     record: bool = False) -> dict:
    """The headroom forecast, or {"missing": reason, "steps": []}; with `record`, the forecast
    is also stored, once per hour (example E25)."""
    # Imported here, not at the top, since headroom imports this module. `python3 -I` leaves this
    # file's folder off the path; it is root-owned in the image.
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import headroom
    if not collector_db or not os.path.exists(collector_db):
        return {"missing": "the collector's store is not available", "steps": []}
    conn = connect(db_path)
    try:
        collector_conn = sqlite3.connect(f"file:{collector_db}?mode=ro", uri=True)
        try:
            result = headroom.forecast(conn, collector_conn, now, kwp, tz)
        finally:
            collector_conn.close()
        if record:
            headroom.record(conn, result)
        return result
    except headroom.Missing as e:
        return {"missing": str(e), "steps": []}
    except sqlite3.Error as e:  # e.g. the collector's store is locked or has no log yet
        return {"missing": f"the collector's store cannot be read: {e}", "steps": []}
    except (KeyError, TypeError, ValueError, IndexError) as e:  # a stored response of another shape
        return {"missing": f"an input could not be read: {type(e).__name__}: {e}", "steps": []}
    finally:
        conn.close()


def make_handler(db_path: str, kwp: float, clock=lambda: datetime.now(timezone.utc),
                 collector_db: str | None = None, prices: tuple[float, float] = (0.30, 0.08),
                 tz: ZoneInfo = ZoneInfo("Europe/Berlin"), unit_figures: str | None = None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/control-strategies":
                self.control_strategies()
                return
            if url.path == "/headroom":
                self.headroom()
                return
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
            self.send_json(payload)

        def control_strategies(self):
            if not collector_db or not os.path.exists(collector_db):
                self.send_error(503, "the collector's store is not available")
                return
            conn = connect(db_path)
            try:
                collector_conn = sqlite3.connect(f"file:{collector_db}?mode=ro", uri=True)
                try:
                    weeks = control_strategy_weeks(conn, collector_conn, *prices, tz,
                                                   months=unit_months(unit_figures))
                finally:
                    collector_conn.close()
            except sqlite3.Error as e:  # e.g. the collector's store has no log yet, or is locked
                self.send_error(503, f"the collector's store cannot be read: {e}")
                return
            finally:
                conn.close()
            try:
                model = baseline_model(weeks, *prices)
            except (ZeroDivisionError, ValueError):  # degenerate data: the weeks without a model
                model = None
            for w in weeks:
                del w["daily_mean_c"]
            self.send_json(json.dumps({
                "prices": {"grid_eur_per_kwh": prices[0], "feed_in_eur_per_kwh": prices[1]},
                "model": model, "weeks": weeks}).encode())

        def headroom(self):
            """The solar headroom for the next 48 h (spec: solar-headroom). A missing or stale
            input gives its reason and no steps (example E2)."""
            payload = headroom_payload(db_path, collector_db, clock(), kwp, tz)
            self.send_json(json.dumps(payload).encode())

        def send_json(self, payload: bytes):
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
    collector_db = os.environ.get("EM_COLLECTOR_DB", "/collector/collector.sqlite")
    prices = (float(os.environ.get("EM_GRID_PRICE_EUR_PER_KWH", "0.30")),
              float(os.environ.get("EM_FEED_IN_PRICE_EUR_PER_KWH", "0.08")))
    tz = ZoneInfo(os.environ.get("TZ", "Europe/Berlin"))
    unit_figures = os.environ.get("EM_UNIT_FIGURES", "/unit/unit-panel-figures.csv")
    services = services_from_env()
    conn = connect(db_path)
    server = ThreadingHTTPServer((bind, port), make_handler(db_path, kwp, collector_db=collector_db,
                                                            prices=prices, tz=tz,
                                                            unit_figures=unit_figures))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"forecast archive: {db_path}, endpoints http://{bind}:{port}/e5, /control-strategies"
          " and /headroom", flush=True)
    while True:
        now = datetime.now(timezone.utc)
        for name, outcome in fetch_all(conn, services, now).items():
            print(f"{iso(now)} {name}: {outcome}", flush=True)
        try:  # the record of the headroom forecast (E25) must never stop the fetches
            result = headroom_payload(db_path, collector_db, datetime.now(timezone.utc), kwp, tz, record=True)
            if result.get("missing"):
                print(f"{iso(now)} headroom: not recorded, {result['missing']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{iso(now)} headroom: failed, {type(e).__name__}: {e}", flush=True)
        time.sleep(seconds_until_next_run(datetime.now(timezone.utc)))


if __name__ == "__main__":
    main()
