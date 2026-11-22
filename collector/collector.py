"""Collect what the inverter and the heat pump hold beyond Home Assistant's entities
(change collect-device-details; design/research/rct-onecta-data.md).

- Every minute: the inverter's battery and inverter state objects, raw (E10).
- Every 10 s, one query of the inverter's own logs, alternating between a walk
  back to the oldest entry it returns and, every hour for each series, a fill
  from the present back to the newest stored entry, so gaps of any length are
  filled (E11).
- Once a day after 03:00 local time: yesterday's twelve 2-hour periods of the
  heat pump's electrical energy, from the Daikin Onecta integration's
  diagnostics in Home Assistant (E12). No call to the Daikin cloud.

Values go to an append-only SQLite database. A read-only HTTP endpoint on
127.0.0.1 serves the latest values to Home Assistant. Settings come from
environment variables only (see .env.example).

The only write this program may send to a device is a log query: a timestamp
written to a `logger.*` object of the inverter (requirements 2.3).
`log_query_frame` enforces that; nothing else builds a write frame.
"""

import json
import math
import os
import socket
import sqlite3
import ssl
import threading
import time
import urllib.request
from datetime import date, datetime, time as dtime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from zoneinfo import ZoneInfo

from rctclient.exceptions import RctClientException
from rctclient.frame import ReceiveFrame, make_frame
from rctclient.registry import REGISTRY
from rctclient.types import Command, DataType, ObjectGroup
from rctclient.utils import decode_value, encode_value

STATE_OBJECTS = (
    "power_mng.state",
    "battery.bat_status",
    "battery.status",
    "battery.status2",
    "prim_sm.state",
)
LOG_SERIES = tuple(sorted(o.name for o in REGISTRY.all()
                          if o.group == ObjectGroup.LOGGER and o.response_data_type == DataType.TIMESERIES))
TIMEOUT_S = 5
RETRY_PAUSE_S = 2
LOG_INTERVAL_S = 10
EMPTY_CONFIRMATIONS = 2
HOUSEHOLD_LOAD = "sensor.rct_power_storage_consumer_power"

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    read_at TEXT NOT NULL,      -- UTC, ISO 8601
    object TEXT NOT NULL,       -- inverter object name, e.g. power_mng.state
    value REAL NOT NULL         -- raw value as decoded
);
CREATE INDEX IF NOT EXISTS state_object_time ON state (object, read_at);
CREATE TABLE IF NOT EXISTS log_entry (
    series TEXT NOT NULL,       -- logger object, e.g. logger.minutes_soc_log_ts
    ts INTEGER NOT NULL,        -- the entry's time by the inverter's clock (see table clock)
    value REAL NOT NULL,
    read_at TEXT NOT NULL,      -- UTC, ISO 8601
    UNIQUE (series, ts)
);
CREATE TABLE IF NOT EXISTS clock (
    read_at TEXT NOT NULL,      -- UTC, ISO 8601, this host's clock
    inverter_ts INTEGER NOT NULL -- the inverter's clock (flash_rtc.time_stamp) at that moment; log
                                 -- entries carry this clock, which need not be UTC (2026-11-22: UTC+2)
);
CREATE TABLE IF NOT EXISTS log_walk_floor (
    series TEXT NOT NULL,       -- the oldest entry time an answer of the backwards walk contained, so the
    ts INTEGER NOT NULL,        -- walk moves on even when no entry of that answer could be stored (NaN)
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS log_entry_read_at ON log_entry (read_at);
CREATE TABLE IF NOT EXISTS log_walk_done (
    series TEXT PRIMARY KEY,    -- the backwards walk of this series reached its oldest entry
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS energy_period (
    day TEXT NOT NULL,              -- local date the period belongs to
    period_start_local TEXT NOT NULL,
    period_start_utc TEXT NOT NULL,
    management_point TEXT NOT NULL, -- as Daikin names it, e.g. climateControl, domesticHotWaterTank
    mode TEXT NOT NULL,             -- heating or cooling
    kwh REAL NOT NULL,              -- as Daikin reports it (whole kWh)
    read_at TEXT NOT NULL,
    UNIQUE (day, period_start_local, management_point, mode)
);
CREATE TABLE IF NOT EXISTS failure (
    at TEXT NOT NULL,           -- UTC, ISO 8601
    part TEXT NOT NULL,         -- state, log or energy
    error TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS state_no_update BEFORE UPDATE ON state
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS state_no_delete BEFORE DELETE ON state
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS log_entry_no_update BEFORE UPDATE ON log_entry
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS log_entry_no_delete BEFORE DELETE ON log_entry
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS clock_no_update BEFORE UPDATE ON clock
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS clock_no_delete BEFORE DELETE ON clock
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS energy_period_no_update BEFORE UPDATE ON energy_period
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS energy_period_no_delete BEFORE DELETE ON energy_period
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS failure_no_update BEFORE UPDATE ON failure
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
CREATE TRIGGER IF NOT EXISTS failure_no_delete BEFORE DELETE ON failure
    BEGIN SELECT RAISE(ABORT, 'the collector database is append-only'); END;
"""


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")  # the endpoint reads while the loop writes
    conn.executescript(SCHEMA)
    return conn


class InverterError(Exception):
    """The inverter did not answer, or answered with a broken frame."""


class _Unreachable(Exception):
    """No connection to the inverter, also on the retry: the minute's round ends."""


def log_query_frame(name: str, before: int) -> bytes:
    """The one write frame this program builds: a log query to a `logger.*` object.

    Refuses every other object before a frame exists (design C6).
    """
    if name not in LOG_SERIES:
        raise PermissionError(f"refusing to write to {name}: only the logger.* time series may be queried")
    oinfo = REGISTRY.get_by_name(name)
    return make_frame(command=Command.WRITE, id=oinfo.object_id,
                      payload=encode_value(DataType.INT32, before))


class Inverter:
    """One short TCP connection to the inverter; use as a context manager."""

    def __init__(self, host: str, port: int, timeout: float = TIMEOUT_S):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None

    def __enter__(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise InverterError(f"connect: {e}") from e
        return self

    def __exit__(self, *exc):
        self.sock.close()

    def _exchange(self, request: bytes, object_id: int) -> bytes:
        """Send a request and return the payload of the response to `object_id`."""
        try:
            self.sock.sendall(request)
            deadline = time.monotonic() + self.timeout
            frame, buffer = ReceiveFrame(), b""
            while True:
                if not buffer:
                    if time.monotonic() > deadline:
                        raise InverterError("timeout")
                    buffer = self.sock.recv(1024)
                    if not buffer:
                        raise InverterError("connection closed")
                used = frame.consume(buffer)
                buffer = buffer[used:]
                if frame.complete():
                    if frame.id == object_id and frame.command in (Command.RESPONSE, Command.LONG_RESPONSE):
                        return frame.data
                    frame = ReceiveFrame()  # an answer to another client's request
        except (OSError, RctClientException) as e:
            raise InverterError(f"{type(e).__name__}: {e}") from e

    def query_log(self, name: str, before: int) -> list:
        """Entries of a log series logged before `before` (UNIX seconds), as (ts, value)."""
        request = log_query_frame(name, before)  # refuses anything but logger.*
        oinfo = REGISTRY.get_by_name(name)
        payload = self._exchange(request, oinfo.object_id)
        try:
            _, table = decode_value(DataType.TIMESERIES, payload)
        except Exception as e:
            raise InverterError(f"decode {name}: {e}") from e
        return sorted((int(t.timestamp()), float(v)) for t, v in table.items())

    def read(self, name: str):
        oinfo = REGISTRY.get_by_name(name)
        payload = self._exchange(make_frame(command=Command.READ, id=oinfo.object_id), oinfo.object_id)
        try:
            return decode_value(oinfo.response_data_type, payload)
        except Exception as e:  # a cut payload with a matching checksum (rctclient docs)
            raise InverterError(f"decode {name}: {e}") from e


def record_failure(conn: sqlite3.Connection, now: datetime, part: str, error: str) -> None:
    with conn:
        conn.execute("INSERT INTO failure (at, part, error) VALUES (?, ?, ?)", (iso(now), part, error))


def read_state(conn: sqlite3.Connection, inverter: Callable[[], Inverter], now: datetime,
               pause: Callable[[float], None] = time.sleep) -> dict:
    """Read the state objects once, over one connection where possible (design C4).

    A failed read is retried once, after a pause, over a new connection: a cut
    answer leaves the old one unusable. Returns what was stored.
    """
    stored, inv = {}, None
    try:
        for name in STATE_OBJECTS:
            for attempt in (1, 2):
                try:
                    if inv is None:
                        try:
                            inv = inverter().__enter__()
                        except InverterError as e:
                            if attempt == 1:
                                pause(RETRY_PAUSE_S)
                                continue
                            raise _Unreachable(str(e)) from e
                    stored[name] = float(inv.read(name))
                    break
                except InverterError as e:
                    if inv is not None:
                        inv.__exit__(None, None, None)
                        inv = None
                    if attempt == 2:
                        record_failure(conn, now, "state", f"{name}: {e}")
                    else:
                        pause(RETRY_PAUSE_S)
    except _Unreachable as e:
        record_failure(conn, now, "state", str(e))
    finally:
        if inv is not None:
            inv.__exit__(None, None, None)
    with conn:
        conn.executemany("INSERT INTO state (read_at, object, value) VALUES (?, ?, ?)",
                         [(iso(now), name, value) for name, value in stored.items()])
    return stored


def walk_pending(conn: sqlite3.Connection) -> list:
    done = {r[0] for r in conn.execute("SELECT series FROM log_walk_done")}
    return [s for s in LOG_SERIES if s not in done]


def _query(conn: sqlite3.Connection, inverter: Callable[[], Inverter], series: str, now: datetime,
           before_from_clock: Callable[[int], int], confirm_empty: bool,
           pause: Callable[[float], None]) -> tuple:
    """Read the inverter's clock (stored), then query `series` before the time `before_from_clock` gives.

    A cut answer can arrive empty with a valid checksum (rctclient docs), so with
    `confirm_empty`, "nothing older" counts only when two more queries agree.
    Returns (before, entries older than before).
    """
    try:
        with inverter() as inv:
            inverter_now = int(inv.read("flash_rtc.time_stamp"))
            with conn:
                conn.execute("INSERT INTO clock (read_at, inverter_ts) VALUES (?, ?)", (iso(now), inverter_now))
            before = before_from_clock(inverter_now)
            entries = inv.query_log(series, before)
            for _ in range(EMPTY_CONFIRMATIONS if confirm_empty else 0):
                if any(ts < before for ts, _v in entries):
                    break
                pause(RETRY_PAUSE_S)
                entries = inv.query_log(series, before)
    except InverterError as e:
        record_failure(conn, now, "log", f"{series}: {e}")
        raise
    return before, [(ts, v) for ts, v in entries if ts < before]


def _store(conn: sqlite3.Connection, series: str, entries: list, now: datetime) -> int:
    rows = [(series, ts, v, iso(now)) for ts, v in entries if math.isfinite(v)]
    before_count = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO log_entry (series, ts, value, read_at) VALUES (?, ?, ?, ?)", rows)
    return conn.total_changes - before_count


def walk_step(conn: sqlite3.Connection, inverter: Callable[[], Inverter], series: str, now: datetime,
              pause: Callable[[float], None] = time.sleep) -> int:
    """One query of the backwards walk (design C5); returns the number of new entries stored.

    Queries before the oldest time reached so far and marks the walk done when
    nothing older comes back. Timestamps follow the inverter's clock.
    """
    floor = conn.execute("SELECT min(m) FROM (SELECT min(ts) AS m FROM log_entry WHERE series = ? "
                         "UNION ALL SELECT min(ts) FROM log_walk_floor WHERE series = ?)",
                         (series, series)).fetchone()[0]
    before, older = _query(conn, inverter, series, now,
                           lambda clock: floor if floor is not None else clock + 60, True, pause)
    with conn:
        if not older:
            conn.execute("INSERT OR IGNORE INTO log_walk_done (series, at) VALUES (?, ?)", (series, iso(now)))
            return 0
        conn.execute("INSERT INTO log_walk_floor (series, ts, at) VALUES (?, ?, ?)",
                     (series, min(ts for ts, _v in older), iso(now)))
        return _store(conn, series, older, now)


def catch_up_step(conn: sqlite3.Connection, inverter: Callable[[], Inverter], series: str, now: datetime,
                  cursor: dict, pause: Callable[[float], None] = time.sleep) -> bool:
    """One query of the forward fill: from the inverter's present back to the newest stored entry.

    Fills gaps of any length (host or collector down, inverter unreachable).
    `cursor` keeps the position between calls; returns True when the series is
    caught up.
    """
    position = cursor.setdefault(series, {
        "target": conn.execute("SELECT max(ts) FROM log_entry WHERE series = ?", (series,)).fetchone()[0],
        "before": None})
    _before, older = _query(conn, inverter, series, now,
                            lambda clock: position["before"] or clock + 60, False, pause)
    with conn:
        _store(conn, series, older, now)
    oldest = min((ts for ts, _v in older), default=None)
    if oldest is None or position["target"] is None or oldest <= position["target"]:
        del cursor[series]
        return True
    position["before"] = oldest
    return False


class NotReady(Exception):
    """Yesterday's periods are not all published yet; try again later."""


class FormatChanged(Exception):
    """The diagnostics do not hold the values where they were found before (design C7)."""


def yesterday_periods(diagnostics: dict, today: date, tz: ZoneInfo) -> list:
    """(management_point, mode, [12 kWh values]) for the day before `today`, all or nothing.

    Daikin's `day` arrays hold 12 two-hour periods of yesterday, then 12 of
    today, counted from the last time Daikin delivered data; that time must lie
    in `today`, or the arrays refer to an older day.
    """
    try:
        devices = diagnostics["data"]["json_data"]
        result = []
        for device in devices:
            delivered = datetime.fromisoformat(device["timestamp"].replace("Z", "+00:00")).astimezone(tz).date()
            for point in device["management_points"]:
                if "consumption_data" not in point:
                    continue
                if delivered != today:
                    raise NotReady(f"Daikin last delivered on {delivered}")
                for mode, periods in point["consumption_data"]["value"]["electrical"].items():
                    if not isinstance(periods, dict):
                        continue  # e.g. "unit": "kWh"
                    day = periods["day"]
                    if len(day) != 24:
                        raise FormatChanged(f"day has {len(day)} values, expected 24")
                    if any(v is None for v in day[:12]):
                        raise NotReady(f"{point['management_point_type']} {mode}: not all periods published")
                    result.append((point["management_point_type"], mode, [float(v) for v in day[:12]]))
    except (NotReady, FormatChanged):
        raise
    except Exception as e:  # any other shape than the one observed (design C7)
        raise FormatChanged(f"{type(e).__name__}: {e}") from e
    if not result:
        raise FormatChanged("no consumption data found")
    return result


def store_periods(conn: sqlite3.Connection, periods: list, day: date, tz: ZoneInfo, now: datetime) -> int:
    rows = []
    for point, mode, values in periods:
        for i, kwh in enumerate(values):
            start = datetime.combine(day, dtime(2 * i), tzinfo=tz)
            rows.append((day.isoformat(), start.strftime("%Y-%m-%dT%H:%M"), iso(start), point, mode, kwh, iso(now)))
    with conn:
        before = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO energy_period (day, period_start_local, period_start_utc, "
                         "management_point, mode, kwh, read_at) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        return conn.total_changes - before


def energy_step(conn: sqlite3.Connection, fetch: Callable[[], dict], now: datetime, tz: ZoneInfo) -> bool:
    """Store yesterday's periods if not stored yet; True when they are stored (design C7)."""
    today = now.astimezone(tz).date()
    yesterday = today - timedelta(days=1)
    if conn.execute("SELECT 1 FROM energy_period WHERE day = ? LIMIT 1", (yesterday.isoformat(),)).fetchone():
        return True
    try:
        store_periods(conn, yesterday_periods(fetch(), today, tz), yesterday, tz, now)
        return True
    except NotReady:
        return False
    except Exception as e:  # format changed, Home Assistant unreachable or answering oddly
        record_failure(conn, now, "energy", f"{type(e).__name__}: {e}")
        return False


def status(conn: sqlite3.Connection) -> dict:
    """The latest value of each state object and the time of the last stored read."""
    latest = {}
    for name in STATE_OBJECTS:
        row = conn.execute("SELECT read_at, value FROM state WHERE object = ? "
                           "ORDER BY read_at DESC LIMIT 1", (name,)).fetchone()
        if row:
            latest[name] = {"read_at": row[0], "value": row[1]}
    # The state counts as read only when every object was: the oldest latest read.
    last = min((v["read_at"] for v in latest.values()), default=None) if len(latest) == len(STATE_OBJECTS) else None
    last_log = conn.execute("SELECT max(read_at) FROM log_entry").fetchone()[0]
    oldest = conn.execute("SELECT min(ts) FROM log_entry WHERE series LIKE 'logger.minutes_%'").fetchone()[0]
    latest_day = conn.execute("SELECT max(day) FROM energy_period").fetchone()[0]
    return {"state": latest,
            "last_success": {"state": last, "log": last_log, "energy_day": latest_day},
            "log": {"series": len(LOG_SERIES), "walk_pending": len(walk_pending(conn)),
                    "oldest_minutes_entry": oldest}}


def make_handler(db_path: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/status":
                self.send_error(404)
                return
            conn = connect(db_path)
            try:
                payload = json.dumps(status(conn)).encode()
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


class HomeAssistant:
    """Read-only access to Home Assistant's REST API with a long-lived token."""

    def __init__(self, url: str, token: str, cafile: str | None):
        self.url, self.token = url.rstrip("/"), token
        self.ctx = ssl.create_default_context(cafile=cafile) if url.startswith("https") else None

    def get(self, path: str):
        req = urllib.request.Request(self.url + path, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=20, context=self.ctx) as r:
            return json.load(r)

    def diagnostics(self, domain: str) -> dict:
        entries = self.get(f"/api/config/config_entries/entry?domain={domain}")
        if len(entries) != 1:
            raise ValueError(f"{len(entries)} config entries for {domain}, expected 1")
        return self.get(f"/api/diagnostics/config_entry/{entries[0]['entry_id']}")

    def inverter_values_fresh(self, now: datetime, max_age_s: float = 90) -> tuple:
        """(fresh, problem): whether the integration's household load was reported recently
        (spec: gentle on the inverter), and why not if Home Assistant could not be asked."""
        try:
            s = self.get("/api/states/" + HOUSEHOLD_LOAD)
            reported = datetime.fromisoformat(s.get("last_reported") or s["last_updated"])
            fresh = s["state"] not in ("unavailable", "unknown") and (now - reported).total_seconds() <= max_age_s
            return fresh, None
        except Exception as e:  # unreachable, wrong token or URL, TLS, odd answer
            return False, f"{type(e).__name__}: {e}"


def main():
    db_path = os.environ.get("EM_COLLECTOR_DB", "/data/collector.sqlite")
    bind = os.environ.get("EM_COLLECTOR_BIND", "127.0.0.1")
    port = int(os.environ.get("EM_COLLECTOR_PORT", "8766"))
    host = os.environ["EM_RCT_HOST"]
    rct_port = int(os.environ.get("EM_RCT_PORT", "8899"))
    ha = HomeAssistant(os.environ.get("EM_HA_URL", "http://localhost:8123"), os.environ["HA_TOKEN"],
                       os.environ.get("EM_HA_CAFILE") or None)
    conn = connect(db_path)
    server = ThreadingHTTPServer((bind, port), make_handler(db_path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"collector: {db_path}, endpoint http://{bind}:{port}/status", flush=True)
    tz = ZoneInfo(os.environ.get("TZ", "Europe/Berlin"))
    inverter = lambda: Inverter(host, rct_port)  # noqa: E731
    next_state = next_log = next_energy = next_catch_up_round = last_ha_failure = 0.0
    catch_up, cursor, turn = [], {}, 0
    while True:
        clock = time.time()
        now = datetime.now(timezone.utc)
        try:
            if clock >= next_state:
                next_state = clock - clock % 60 + 60
                stored = read_state(conn, inverter, now)
                if len(stored) < len(STATE_OBJECTS):
                    print(f"{iso(now)} state: {len(stored)} of {len(STATE_OBJECTS)} read", flush=True)
            elif clock >= next_energy:
                next_energy = clock + 900
                if now.astimezone(tz).hour >= 3:
                    energy_step(conn, lambda: ha.diagnostics("daikin_onecta"), now, tz)
            elif clock >= next_log:
                next_log = clock + LOG_INTERVAL_S
                if clock >= next_catch_up_round:  # every hour, every series that has entries
                    started = {r[0] for r in conn.execute("SELECT DISTINCT series FROM log_entry")}
                    catch_up, next_catch_up_round = [s for s in LOG_SERIES if s in started], clock + 3600
                pending = walk_pending(conn)
                use_catch_up = bool(catch_up) and (turn % 2 == 0 or not pending)
                if use_catch_up or pending:
                    fresh, problem = ha.inverter_values_fresh(now)
                    if problem and clock - last_ha_failure > 600:
                        record_failure(conn, now, "log", f"Home Assistant not asked: {problem}")
                        last_ha_failure = clock
                    if fresh:
                        turn += 1
                        try:
                            if use_catch_up:
                                if catch_up_step(conn, inverter, catch_up[0], now, cursor):
                                    catch_up.pop(0)
                            else:
                                walk_step(conn, inverter, pending[0], now)
                        except InverterError:
                            next_log = clock + 60
        except Exception as e:  # keep running; the failure is recorded and the alerts see it
            print(f"{iso(now)} {type(e).__name__}: {e}", flush=True)
            try:
                record_failure(conn, now, "collector", f"{type(e).__name__}: {e}")
            except Exception:
                pass
            time.sleep(30)
        time.sleep(max(0.5, min(next_state, next_log, next_energy) - time.time()))


if __name__ == "__main__":
    main()
