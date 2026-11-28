"""Tests for archive/forecast_archive.py (specs: forecast-archive, satellite-radiation-archive;
examples E5, E6 and E13).

The responses are synthetic: real ones contain the caller's public IP address
and place name, so they must not be committed.
"""

import json
import math
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archive"))
import forecast_archive as fa  # noqa: E402

T0 = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def solar_body(now: datetime) -> bytes:
    """A forecast.solar-like response computed at `now`: 500 Wh in each hour of the next two days."""
    hours = [now.replace(minute=0, second=0) + timedelta(hours=h) for h in range(1, 49)]
    return json.dumps({
        "result": {"watt_hours_period": {fa.iso(t): 500 for t in hours}},
        "message": {"info": {"time_utc": fa.iso(now)}},
    }).encode()


def weather_body(now: datetime) -> bytes:
    """An Open-Meteo-like response: GTI 100 W/m² in each hour of three days."""
    day = now.replace(hour=0, minute=0, second=0)
    times = [(day + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(72)]
    return json.dumps({"hourly": {"time": times, "global_tilted_irradiance": [100.0] * 72}}).encode()


def satellite_body(now: datetime, offset: float = 0.0, missing=(), today: bool = False) -> bytes:
    """A satellite-API-like response in the shape recorded on 2026-11-23 (neutral coordinates,
    synthetic values): the 24 hours of the day before `now`, labelled 00:00 to 23:00.

    Each quantity is the label's index plus `offset` (the hour of day for the
    first day, 24 more for the second), with a quantity-specific step, so that
    every value is distinct; labels in `missing` have null values.
    With `today`, the response also holds the 24 hours of `now`'s day, as with
    past_days=1 and forecast_days=1; the labels from the hour of `now` on are
    null, since the satellite has not observed them yet.
    """
    day = now.replace(hour=0, minute=0, second=0) - timedelta(days=1)
    labels = [day + timedelta(hours=h) for h in range(48 if today else 24)]
    times = [t.strftime("%Y-%m-%dT%H:%M") for t in labels]
    observed = now.replace(minute=0, second=0, microsecond=0)
    hourly = {"time": times}
    for k, name in enumerate(fa.SATELLITE_VARIABLES):
        hourly[name] = [None if t in missing or label >= observed else 1000.0 * k + h + offset
                        for h, (t, label) in enumerate(zip(times, labels))]
    return json.dumps({
        "latitude": 52.52, "longitude": 13.41, "generationtime_ms": 0.1, "utc_offset_seconds": 0,
        "timezone": "GMT", "timezone_abbreviation": "GMT", "elevation": 38.0,
        "hourly_units": {"time": "iso8601", **{name: "W/m²" for name in fa.SATELLITE_VARIABLES}},
        "hourly": hourly,
    }).encode()


class FakeServices:
    """A local HTTP server standing in for the three services. It records each request."""

    def __init__(self):
        self.now = T0
        self.status = {"/solar": 200, "/weather": 200, "/satellite": 200}
        self.satellite_offset = 0.0
        self.satellite_today = False
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fake.requests.append(self.path)
                body = {"/solar": lambda: solar_body(fake.now),
                        "/weather": lambda: weather_body(fake.now),
                        "/satellite": lambda: satellite_body(fake.now, fake.satellite_offset,
                                                             today=fake.satellite_today)}[self.path]()
                self.send_response(fake.status[self.path])
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{self.server.server_port}"
        self.services = [
            fa.Service(fa.FORECAST_SOLAR, base + "/solar", fa.forecast_solar_issued_at),
            fa.Service(fa.OPEN_METEO, base + "/weather", fa.no_issue_time),
            fa.Service(fa.SATELLITE, base + "/satellite", fa.no_issue_time),
        ]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ArchiveCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name, "forecasts.sqlite"))
        self.conn = fa.connect(self.db)
        self.fake = FakeServices()

    def tearDown(self):
        self.fake.close()
        self.conn.close()
        self.tmp.cleanup()

    def run_hours(self, hours, minute=2):
        for h in range(hours):
            self.fake.now = T0 + timedelta(hours=h, minutes=minute)
            fa.fetch_all(self.conn, self.fake.services, self.fake.now)

    def count(self, service, where="1"):
        return self.conn.execute(
            f"SELECT count(*) FROM fetch WHERE service = ? AND {where}", (service,)).fetchone()[0]


class ArchiveTest(ArchiveCase):
    def test_a_day_of_fetches(self):
        self.run_hours(24)
        for service in (fa.FORECAST_SOLAR, fa.OPEN_METEO):
            self.assertEqual(self.count(service, "error IS NULL"), 24)

    def test_restart_loop_calls_once_per_hour(self):
        for minute in (2, 10, 20, 40, 59):
            now = T0 + timedelta(minutes=minute)
            fa.fetch_all(self.conn, self.fake.services, now)
        self.assertEqual(sorted(self.fake.requests), ["/satellite", "/solar", "/weather"])

    def test_service_down_is_recorded(self):
        self.fake.status["/solar"] = 503
        self.run_hours(1)
        row = self.conn.execute(
            "SELECT http_status, error FROM fetch WHERE service = ?", (fa.FORECAST_SOLAR,)).fetchone()
        self.assertEqual(row, (503, "HTTP 503"))
        self.assertIsNone(fa.latest_before(self.conn, fa.FORECAST_SOLAR, T0 + timedelta(hours=1)))
        self.assertEqual(self.count(fa.OPEN_METEO, "error IS NULL"), 1)

    def test_unreachable_service_is_recorded(self):
        self.fake.close()
        fa.fetch_all(self.conn, self.fake.services, T0)
        errors = [r[0] for r in self.conn.execute("SELECT error FROM fetch")]
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(e.startswith("URLError") for e in errors), errors)
        self.fake = FakeServices()

    def test_kept_unchanged_with_issue_time(self):
        self.run_hours(1)
        issue = fa.latest_before(self.conn, fa.FORECAST_SOLAR, T0 + timedelta(hours=1))
        self.assertEqual(issue["body"], solar_body(T0 + timedelta(minutes=2)))
        self.assertEqual(issue["issued_at"], "2026-11-02T00:02:00+00:00")
        weather = fa.latest_before(self.conn, fa.OPEN_METEO, T0 + timedelta(hours=1))
        self.assertIsNone(weather["issued_at"])

    def test_archive_is_append_only(self):
        self.run_hours(1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM fetch")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE fetch SET body = NULL")

    def test_e6_lead_times_over_a_week(self):
        """E6: for an hour of the week, the forecasts issued 1, 6 and 24 h before it."""
        self.run_hours(7 * 24)
        hour = T0 + timedelta(days=5, hours=12)
        for lead in (1, 6, 24):
            for service in (fa.FORECAST_SOLAR, fa.OPEN_METEO):
                issue = fa.latest_before(self.conn, service, hour - timedelta(hours=lead))
                expected = hour - timedelta(hours=lead) - timedelta(minutes=58)
                self.assertEqual(issue["fetched_at"], fa.iso(expected), (service, lead))

    def test_e5_series(self):
        self.run_hours(3 * 24)
        now = T0 + timedelta(days=3)
        series = fa.e5_series(self.conn, now, days=2, kwp=7.92)
        self.assertEqual(len(series), 48)
        first = series[0]
        self.assertEqual(first["start"], fa.iso(T0 + timedelta(days=1)))
        self.assertEqual(first["solar_forecast_wh"], 500)
        self.assertAlmostEqual(first["weather_estimate_wh"], 792.0)
        self.assertEqual(first["solar_forecast_fetched_at"], fa.iso(T0 + timedelta(hours=23, minutes=2)))

    def test_endpoint(self):
        self.run_hours(2)
        handler = fa.make_handler(self.db, 7.92, clock=lambda: T0 + timedelta(hours=3))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/e5?days=1"
            with urllib.request.urlopen(url) as response:
                hours = json.load(response)["hours"]
            self.assertEqual(len(hours), 24)
            self.assertEqual(hours[-1]["start"], fa.iso(T0 + timedelta(hours=2)))
            self.assertEqual(hours[-1]["solar_forecast_wh"], 500)
        finally:
            server.shutdown()
            server.server_close()


class SatelliteTest(ArchiveCase):
    """E13: Open-Meteo's satellite irradiance of the past day, fetched hourly and kept as fetched
    (spec: satellite-radiation-archive)."""

    def test_a_day_of_fetches(self):
        """E13: 24 responses a day; together they give all four quantities for every hour of a day."""
        self.run_hours(48)
        self.assertEqual(self.count(fa.SATELLITE, "error IS NULL"), 48)
        day = T0 - timedelta(days=1)
        for h in range(24):
            hour = fa.satellite_hour(self.conn, day + timedelta(hours=h))
            self.assertIsNotNone(hour, h)
            self.assertEqual(set(hour) - {"start", "fetched_at"}, set(fa.SATELLITE_VARIABLES))
            self.assertTrue(all(hour[name] is not None for name in fa.SATELLITE_VARIABLES), h)

    def test_a_day_of_fetches_with_todays_null_tail(self):
        """E13, in the shape forecast_days=1 returns: yesterday and today, today null from the current
        hour on. Hourly fetches over two days give all four quantities for every hour of the first
        day; an hour not yet observed reads as None, not as a value of an older day."""
        self.fake.satellite_today = True
        self.run_hours(48)  # 2026-11-02 00:02 to 2026-11-03 23:02
        for h in range(24):
            hour = fa.satellite_hour(self.conn, T0 + timedelta(hours=h))
            self.assertTrue(all(hour[name] is not None for name in fa.SATELLITE_VARIABLES), h)
            self.assertEqual(hour["shortwave_radiation"], h + 1, h)  # 23:00-24:00 is today's 00:00 label
        # Observed during the day: 2026-11-03 21:00-22:00 is labelled 22:00, today's entry in the last
        # fetch at 23:02 (index 46), not yesterday's 22:00 (index 22).
        hour = fa.satellite_hour(self.conn, T0 + timedelta(days=1, hours=21))
        self.assertEqual((hour["fetched_at"], hour["shortwave_radiation"]),
                         (fa.iso(T0 + timedelta(days=1, hours=23, minutes=2)), 46.0))
        # Not yet observed: 22:00-23:00 is labelled 23:00, null in every response that holds it.
        hour = fa.satellite_hour(self.conn, T0 + timedelta(days=1, hours=22))
        self.assertEqual([hour[name] for name in fa.SATELLITE_VARIABLES], [None] * 4)

    def test_hour_null_in_every_response(self):
        """An hour that every response holds as null reads as None, from the newest response."""
        body = satellite_body(T0, missing={"2026-11-01T13:00"})
        for fetched_at in (T0, T0 + timedelta(hours=1)):
            self.conn.execute("INSERT INTO fetch (service, fetched_at, http_status, body) VALUES (?, ?, 200, ?)",
                              (fa.SATELLITE, fa.iso(fetched_at), body))
        hour = fa.satellite_hour(self.conn, datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(hour["fetched_at"], fa.iso(T0 + timedelta(hours=1)))
        self.assertEqual([hour[name] for name in fa.SATELLITE_VARIABLES], [None] * 4)

    def test_kept_unchanged_without_issue_time(self):
        """E13: the response is kept byte for byte; the service states no issue time."""
        self.run_hours(1)
        kept = fa.latest_before(self.conn, fa.SATELLITE, T0 + timedelta(hours=1))
        self.assertEqual(kept["body"], satellite_body(T0 + timedelta(minutes=2)))
        self.assertIsNone(kept["issued_at"])

    def test_satellite_down_forecasts_kept(self):
        """E13: a failed satellite fetch is recorded; the forecasts of that hour are kept as usual."""
        self.fake.status["/satellite"] = 503
        self.run_hours(1)
        row = self.conn.execute(
            "SELECT http_status, error FROM fetch WHERE service = ?", (fa.SATELLITE,)).fetchone()
        self.assertEqual(row, (503, "HTTP 503"))
        for service in (fa.FORECAST_SOLAR, fa.OPEN_METEO):
            self.assertEqual(self.count(service, "error IS NULL"), 1)
        self.assertIsNone(fa.satellite_hour(self.conn, T0 - timedelta(hours=12)))

    def test_next_hour_after_failure(self):
        """E13: after a failed fetch, the next hour tries again."""
        self.fake.status["/satellite"] = 503
        self.run_hours(1)
        self.fake.status["/satellite"] = 200
        self.fake.now = T0 + timedelta(hours=1, minutes=2)
        self.assertEqual(fa.fetch_all(self.conn, self.fake.services, self.fake.now)[fa.SATELLITE], "ok")

    def test_later_response_revises_an_hour(self):
        """E13: a later response with a different value is the one read; both stay kept."""
        self.run_hours(1)
        self.fake.satellite_offset = 0.5
        self.fake.now = T0 + timedelta(hours=1, minutes=2)
        fa.fetch_all(self.conn, self.fake.services, self.fake.now)
        hour = fa.satellite_hour(self.conn, T0 - timedelta(hours=12))  # 12:00-13:00, labelled 13:00
        self.assertEqual(hour, {
            "start": fa.iso(T0 - timedelta(hours=12)),
            "fetched_at": fa.iso(T0 + timedelta(hours=1, minutes=2)),
            "shortwave_radiation": 13.5, "direct_normal_irradiance": 1013.5,
            "diffuse_radiation": 2013.5, "global_tilted_irradiance": 3013.5,
        })
        earlier = fa.latest_before(self.conn, fa.SATELLITE, T0 + timedelta(hours=1))
        self.assertEqual(json.loads(earlier["body"])["hourly"]["shortwave_radiation"][13], 13.0)

    def test_missing_value_and_uncovered_hour(self):
        """A null from the service reads as None; an hour no response covers reads as None."""
        body = satellite_body(T0, missing={"2026-11-01T13:00"})
        self.conn.execute("INSERT INTO fetch (service, fetched_at, http_status, body) VALUES (?, ?, 200, ?)",
                          (fa.SATELLITE, fa.iso(T0), body))
        hour = fa.satellite_hour(self.conn, datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
        self.assertEqual([hour[name] for name in fa.SATELLITE_VARIABLES], [None] * 4)
        self.assertIsNone(fa.satellite_hour(self.conn, T0 + timedelta(hours=1)))

    def test_newer_response_not_yet_observed_falls_back_to_older(self):
        """E13: a newer response holding only nulls for an hour (fetched before the satellite had it)
        does not hide an older response's values for that hour."""
        older = satellite_body(T0)
        newer = satellite_body(T0, offset=0.5, missing={"2026-11-01T13:00"})
        for fetched_at, body in ((T0, older), (T0 + timedelta(minutes=30), newer)):
            self.conn.execute("INSERT INTO fetch (service, fetched_at, http_status, body) VALUES (?, ?, 200, ?)",
                              (fa.SATELLITE, fa.iso(fetched_at), body))
        hour = fa.satellite_hour(self.conn, datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
        self.assertEqual((hour["fetched_at"], hour["shortwave_radiation"]), (fa.iso(T0), 13.0))
        hour = fa.satellite_hour(self.conn, datetime(2026, 11, 1, 11, tzinfo=timezone.utc))
        self.assertEqual((hour["fetched_at"], hour["shortwave_radiation"]), (fa.iso(T0 + timedelta(minutes=30)), 12.5))

    def test_last_hour_of_a_day_comes_with_the_next_day(self):
        """The hour 23:00-24:00 is labelled 00:00 of the next day, so a response of the previous day
        does not cover it; a naive time is read as UTC."""
        self.run_hours(24)  # fetches on 2026-11-02, each holding the labels of 2026-11-01
        self.assertIsNone(fa.satellite_hour(self.conn, datetime(2026, 11, 1, 23, tzinfo=timezone.utc)))
        hour = fa.satellite_hour(self.conn, datetime(2026, 11, 1, 22))
        self.assertEqual((hour["start"], hour["shortwave_radiation"]), ("2026-11-01T22:00:00+00:00", 23.0))

    def test_url_from_env(self):
        """The query names the four quantities, the roof plane from .env, the satellite product alone
        (no forecast filling of hours not yet observed), yesterday and today, UTC (E13)."""
        env = {"EM_LATITUDE": "52.52", "EM_LONGITUDE": "13.41", "EM_DECLINATION": "30",
               "EM_AZIMUTH": "-10", "EM_KWP": "5"}
        service = {s.name: s for s in fa.services_from_env(env)}[fa.SATELLITE]
        url = urlsplit(service.url)
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://satellite-api.open-meteo.com/v1/archive")
        self.assertEqual(parse_qs(url.query), {
            "latitude": ["52.52"], "longitude": ["13.41"],
            "hourly": [",".join(fa.SATELLITE_VARIABLES)], "tilt": ["30"], "azimuth": ["-10"],
            "past_days": ["1"], "forecast_days": ["1"], "timezone": ["UTC"],
            "models": ["dwd_sis_europe_africa_v4"]})
        self.assertIs(service.issued_at, fa.no_issue_time)


def history_body(start: datetime, hours: int, value=lambda t: 5.0) -> bytes:
    """An archive-API-like response (neutral coordinates, synthetic values): hourly temperature_2m
    from `start` (UTC) for `hours` hours."""
    times = [start + timedelta(hours=h) for h in range(hours)]
    return json.dumps({
        "latitude": 52.52, "longitude": 13.41, "utc_offset_seconds": 0, "timezone": "GMT",
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                   "temperature_2m": [value(t) for t in times]},
    }).encode()


def collector_store(path: str, days: dict) -> sqlite3.Connection:
    """A collector-like store with the inverter's daily logs:
    {date: (load, import, feed-in, PV input A, PV input B) in Wh}."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE log_entry (series TEXT NOT NULL, ts INTEGER NOT NULL, value REAL NOT NULL,"
                 " read_at TEXT NOT NULL, UNIQUE (series, ts))")
    for day, values in days.items():
        ts = int(datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        for series, sign, value in zip(fa.DAILY_SERIES, (1, 1, -1, 1, 1), values):
            conn.execute("INSERT INTO log_entry VALUES (?, ?, ?, '')", (series, ts, sign * value))
    conn.commit()
    return conn


BERLIN = fa.ZoneInfo("Europe/Berlin")


ENV = {"EM_LATITUDE": "52.52", "EM_LONGITUDE": "13.41", "EM_DECLINATION": "30",
       "EM_AZIMUTH": "-10", "EM_KWP": "5"}


class NamedModelTest(ArchiveCase):
    """Spec model-forecast-archive: the forecasts of named models, current and past runs (S3, E18)."""

    def service(self, name):
        return {s.name: s for s in fa.services_from_env(ENV)}[name]

    def test_current_forecasts_url(self):
        """Scenario "A day of fetches": hourly, three named models, roof plane, 15-minute steps too."""
        service = self.service(fa.MODELS)
        self.assertFalse(service.daily)
        url = urlsplit(service.url)
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", "https://api.open-meteo.com/v1/forecast")
        self.assertEqual(parse_qs(url.query), {
            "latitude": ["52.52"], "longitude": ["13.41"], "models": ["dwd_icon_d2,dwd_icon_eu,ecmwf_ifs"],
            "hourly": ["global_tilted_irradiance"], "minutely_15": ["global_tilted_irradiance"],
            "tilt": ["30"], "azimuth": ["-10"], "forecast_days": ["4"], "timezone": ["UTC"]})

    def test_first_past_runs_fetch_from_august(self):
        """Scenario "First fetch after deployment": from 2026-08-27 to yesterday, three leads."""
        service = self.service(fa.PREVIOUS_RUNS)
        self.assertTrue(service.daily)
        url = urlsplit(service.url(self.conn, T0))
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}",
                         "https://previous-runs-api.open-meteo.com/v1/forecast")
        self.assertEqual(parse_qs(url.query), {
            "latitude": ["52.52"], "longitude": ["13.41"], "models": ["dwd_icon_d2,dwd_icon_eu,ecmwf_ifs"],
            "hourly": ["global_tilted_irradiance,global_tilted_irradiance_previous_day1,"
                       "global_tilted_irradiance_previous_day2"],
            "tilt": ["30"], "azimuth": ["-10"], "start_date": ["2026-08-27"], "end_date": ["2026-11-01"],
            "timezone": ["UTC"]})

    def test_past_runs_fill_missed_days(self):
        """Scenario "Fetches missed for some days": three failed days after a success are covered."""
        service = self.service(fa.PREVIOUS_RUNS)
        query = lambda: parse_qs(urlsplit(service.url(self.conn, T0)).query)  # noqa: E731
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.PREVIOUS_RUNS, "2026-10-29T00:02:00+00:00", b"{}"))
        for d in (30, 31):
            self.conn.execute("INSERT INTO fetch (service, fetched_at, error) VALUES (?, ?, 'HTTP 500')",
                              (fa.PREVIOUS_RUNS, fa.iso(datetime(2026, 10, d, 0, 2, tzinfo=timezone.utc))))
        self.conn.execute("INSERT INTO fetch (service, fetched_at, error) VALUES (?, ?, 'HTTP 500')",
                          (fa.PREVIOUS_RUNS, "2026-11-01T00:02:00+00:00"))
        self.assertEqual((query()["start_date"], query()["end_date"]), (["2026-10-26"], ["2026-11-01"]))
        # Another source's success does not count for this one.
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, "2026-11-01T00:02:00+00:00", b"{}"))
        self.assertEqual(query()["start_date"], ["2026-10-26"])

    def test_refused_request_leaves_the_others(self):
        """Scenario "Open-Meteo refuses one request": a failure entry, the other sources kept."""
        base = f"http://127.0.0.1:{self.fake.server.server_port}"
        self.fake.status["/satellite"] = 429  # stands in for the named-model source
        self.fake.services.append(fa.Service(fa.MODELS, base + "/satellite", fa.no_issue_time))
        self.fake.services = [s for s in self.fake.services if s.name != fa.SATELLITE]
        self.run_hours(1)
        self.assertEqual(self.conn.execute("SELECT http_status, error FROM fetch WHERE service = ?",
                                           (fa.MODELS,)).fetchone(), (429, "HTTP 429"))
        self.assertEqual(self.count(fa.FORECAST_SOLAR, "error IS NULL"), 1)
        self.assertEqual(self.count(fa.OPEN_METEO, "error IS NULL"), 1)


class HistoryTest(ArchiveCase):
    """E20: Open-Meteo's historical temperature, fetched once a day and kept as fetched."""

    def test_url_first_from_baseline_start_then_two_weeks(self):
        env = {"EM_LATITUDE": "52.52", "EM_LONGITUDE": "13.41", "EM_DECLINATION": "30",
               "EM_AZIMUTH": "-10", "EM_KWP": "5"}
        service = {s.name: s for s in fa.services_from_env(env)}[fa.HISTORY]
        self.assertTrue(service.daily)
        query = lambda: parse_qs(urlsplit(service.url(self.conn, T0)).query)  # noqa: E731
        self.assertEqual(query(), {
            "latitude": ["52.52"], "longitude": ["13.41"], "start_date": ["2025-01-01"],
            "end_date": ["2026-11-01"], "hourly": ["temperature_2m"], "timezone": ["UTC"]})
        self.conn.execute("INSERT INTO fetch (service, fetched_at, error) VALUES (?, ?, 'HTTP 500')",
                          (fa.HISTORY, fa.iso(T0)))
        self.assertEqual(query()["start_date"], ["2025-01-01"])  # a failed fetch does not count
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, fa.iso(T0 - timedelta(days=1)), history_body(T0, 1)))
        self.assertEqual(query()["start_date"], ["2026-10-18"])  # 14 days before the last success

    def test_days_missed_while_fetches_failed_are_filled(self):
        env = {"EM_LATITUDE": "52.52", "EM_LONGITUDE": "13.41", "EM_DECLINATION": "30",
               "EM_AZIMUTH": "-10", "EM_KWP": "5"}
        service = {s.name: s for s in fa.services_from_env(env)}[fa.HISTORY]
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, "2026-10-01T00:02:00+00:00", history_body(T0, 1)))
        for d in range(1, 32):  # a month of failures
            self.conn.execute("INSERT INTO fetch (service, fetched_at, error) VALUES (?, ?, 'HTTP 500')",
                              (fa.HISTORY, fa.iso(datetime(2026, 10, d, 0, 2, tzinfo=timezone.utc))))
        query = parse_qs(urlsplit(service.url(self.conn, T0)).query)
        self.assertEqual((query["start_date"], query["end_date"]), (["2026-09-17"], ["2026-11-01"]))

    def test_once_per_day(self):
        base = f"http://127.0.0.1:{self.fake.server.server_port}"
        service = fa.Service(fa.HISTORY, lambda conn, now: base + "/solar", fa.no_issue_time, daily=True)
        outcomes = [fa.fetch_once(self.conn, service, T0 + timedelta(hours=h, minutes=2)) for h in range(30)]
        self.assertEqual(outcomes.count("ok"), 2)  # 2026-11-02 00:02 and 2026-11-03 00:02
        self.assertEqual(outcomes[24], "ok")

    def test_later_response_revises_and_null_keeps(self):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        for fetched, value in ((T0, lambda t: 1.0), (T0 + timedelta(days=1), lambda t: None if t.hour else 2.0)):
            self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                              (fa.HISTORY, fa.iso(fetched), history_body(start, 24, value)))
        temps = fa.history_temperatures(self.conn)
        self.assertEqual(temps[start], 2.0)
        self.assertEqual(temps[start + timedelta(hours=5)], 1.0)

    def test_local_day_mean_on_the_dst_day(self):
        """2026-10-25 has 25 hours in Berlin; one missing hour gives no mean."""
        start = datetime(2026, 10, 24, tzinfo=timezone.utc)
        temps = fa.history_temperatures(self.conn)
        temps.update({start + timedelta(hours=h): float(h) for h in range(72)})
        day = date(2026, 10, 25)
        first = datetime(2026, 10, 24, 22, tzinfo=timezone.utc)  # local midnight, UTC+2
        expected = sum(float((first - start) / timedelta(hours=1) + h) for h in range(25)) / 25
        self.assertAlmostEqual(fa.day_mean_temperature(temps, day, BERLIN), expected)
        del temps[first + timedelta(hours=3)]
        self.assertIsNone(fa.day_mean_temperature(temps, day, BERLIN))


class ControlStrategyTest(ArchiveCase):
    """E20, E21: weekly electricity cost over outdoor temperature and the weekly solar spill."""

    MONDAY = date(2025, 3, 3)

    def setUp(self):
        super().setUp()
        start = datetime(2025, 3, 1, tzinfo=timezone.utc)
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, fa.iso(T0), history_body(start, 24 * 20, lambda t: 4.0)))
        self.collector_db = str(Path(self.tmp.name, "collector.sqlite"))
        # Mon-Sun: 20 kWh load, 10 kWh import, 3 kWh feed-in, 12 + 1 kWh PV each day; one more
        # day the next week.
        days = {self.MONDAY + timedelta(days=d): (20000, 10000, 3000, 12000, 1000) for d in range(8)}
        self.collector = collector_store(self.collector_db, days)

    def tearDown(self):
        self.collector.close()
        super().tearDown()

    def test_a_complete_week(self):
        weeks = fa.control_strategy_weeks(self.conn, self.collector, 0.30, 0.08, BERLIN)
        self.assertEqual(len(weeks), 1)  # the week with only its Monday is left out
        week = weeks[0]
        self.assertEqual((week["week"], week["start"], week["temperature_c"]), ("2025-W10", "2025-03-03", 4.0))
        # Net cost 7 × (10 kWh × 0.30 − 3 kWh × 0.08) = 19.32 €; spill 7 × 3 kWh at 0.22 €/kWh.
        self.assertEqual((week["cost_eur"], week["spill_kwh"], week["spill_eur"]), (19.32, 21.0, 4.62))
        self.assertEqual((week["load_kwh"], week["import_kwh"], week["feed_kwh"], week["pv_kwh"]),
                         (140.0, 70.0, 21.0, 91.0))
        self.assertEqual(week["daily_mean_c"], [4.0] * 7)
        self.assertEqual((week["strategy"], week["result"]), ("baseline", "actual"))

    def test_heating_from_the_collectors_periods(self):
        """Without the periods' table nothing is known; with it, a week with heating on one day
        counts as heated."""
        self.assertEqual(fa.control_strategy_weeks(self.conn, self.collector, 0.30, 0.08, BERLIN)[0]["heated"],
                         None)
        self.collector.execute("CREATE TABLE energy_period (day TEXT, period_start_local TEXT, period_start_utc"
                               " TEXT, management_point TEXT, mode TEXT, kwh REAL, read_at TEXT)")
        for d in range(7):
            day = (self.MONDAY + timedelta(days=d)).isoformat()
            for mode, kwh in (("heating", 3.0 if d == 2 else 0.0), ("cooling", 0.0)):
                self.collector.execute("INSERT INTO energy_period VALUES (?, '', '', 'climateControl', ?, ?, '')",
                                       (day, mode, kwh))
        self.collector.commit()
        week = fa.control_strategy_weeks(self.conn, self.collector, 0.30, 0.08, BERLIN)[0]
        self.assertEqual((week["heated"], week["cooled"]), (True, False))

    def test_null_or_unreadable_history_removes_nothing(self):
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, fa.iso(T0 + timedelta(days=1)),
                           history_body(datetime(2025, 3, 3, tzinfo=timezone.utc), 1, lambda t: None)))
        self.conn.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                          (fa.HISTORY, fa.iso(T0 + timedelta(days=2)), b"not json"))
        self.assertEqual(len(fa.control_strategy_weeks(self.conn, self.collector, 0.30, 0.08, BERLIN)), 1)

    def test_a_missing_daily_value_drops_the_week(self):
        monday = int(datetime(2025, 3, 3, 23, 59, 59, tzinfo=timezone.utc).timestamp())
        self.collector.execute("DELETE FROM log_entry WHERE series = 'logger.day_egrid_feed_log_ts'"
                               " AND ts = ?", (monday,))
        self.collector.commit()
        self.assertEqual(fa.control_strategy_weeks(self.conn, self.collector, 0.30, 0.08, BERLIN), [])

    def test_a_day_without_temperature_drops_the_week(self):
        archive = fa.connect(str(Path(self.tmp.name, "gap.sqlite")))
        start = datetime(2025, 3, 1, tzinfo=timezone.utc)
        gap = datetime(2025, 3, 5, 12, tzinfo=timezone.utc)
        archive.execute("INSERT INTO fetch (service, fetched_at, body) VALUES (?, ?, ?)",
                        (fa.HISTORY, fa.iso(T0), history_body(start, 24 * 20,
                                                              lambda t: None if t == gap else 4.0)))
        try:
            self.assertEqual(fa.control_strategy_weeks(archive, self.collector, 0.30, 0.08, BERLIN), [])
        finally:
            archive.close()

    def test_endpoint(self):
        handler = fa.make_handler(self.db, 7.92, collector_db=self.collector_db, prices=(0.30, 0.08), tz=BERLIN)
        missing = fa.make_handler(self.db, 7.92, collector_db=str(Path(self.tmp.name, "none.sqlite")))
        no_log = str(Path(self.tmp.name, "no-log.sqlite"))
        sqlite3.connect(no_log).execute("CREATE TABLE other (x)").connection.close()
        unreadable = fa.make_handler(self.db, 7.92, collector_db=no_log)
        for h in (handler, missing, unreadable):
            server = ThreadingHTTPServer(("127.0.0.1", 0), h)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_port}/control-strategies"
            try:
                if h is handler:
                    with urllib.request.urlopen(url) as response:
                        data = json.load(response)
                    self.assertEqual(data["prices"], {"grid_eur_per_kwh": 0.30, "feed_in_eur_per_kwh": 0.08})
                    self.assertIsNone(data["model"])  # one week is too few to fit
                    self.assertNotIn("daily_mean_c", data["weeks"][0])
                    self.assertEqual([w["week"] for w in data["weeks"]], ["2025-W10"])
                else:
                    with self.assertRaises(urllib.error.HTTPError) as e:
                        urllib.request.urlopen(url)
                    self.assertEqual(e.exception.code, 503)
            finally:
                server.shutdown()
                server.server_close()


def synthetic_week(start: date, temps: list[float], pv: float, base: float = 14.0,
                   strategy: str = "baseline", import_cut: float = 0.0) -> dict:
    """A week as control_strategy_weeks returns it, with import and feed-in made exactly by
    known coefficients: import = 5 + 2·HDD − 0.1·PV + 0.5·HDD·PV/100 − import_cut,
    feed-in = 1 + 0.2·HDD + 0.8·PV − 0.3·HDD·PV/100."""
    hdd = sum(max(0.0, base - t) for t in temps)
    imp = 5 + 2 * hdd - 0.1 * pv + 0.5 * hdd * pv / 100 - import_cut
    feed = 1 + 0.2 * hdd + 0.8 * pv - 0.3 * hdd * pv / 100
    return {"week": start.isoformat(), "start": start.isoformat(), "daily_mean_c": temps,
            "temperature_c": sum(temps) / 7, "pv_kwh": pv, "import_kwh": imp, "feed_kwh": feed,
            "cost_eur": imp * 0.30 - feed * 0.08, "strategy": strategy, "result": "actual"}


def synthetic_baseline(weeks: int = 104) -> list[dict]:
    """Two years of weeks with temperatures and PV yields that vary independently enough to fit."""
    result = []
    for k in range(weeks):
        start = date(2025, 1, 6) + timedelta(weeks=k)
        mean = 9 - 9 * math.cos(2 * math.pi * k / 52)
        temps = [mean + ((3 * k + d) % 5) - 2 for d in range(7)]
        pv = 160 - 120 * math.cos(2 * math.pi * k / 52) + 30 * ((5 * k) % 3 - 1)  # 10 to 310 kWh
        result.append(synthetic_week(start, temps, pv))
    return result


class HeatPumpModeTest(unittest.TestCase):
    """Whether the heat pump heated or cooled in a week, from the 2-hour periods or the unit's
    monthly figures."""

    def test_monthly_figures_from_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "unit-panel-figures.csv")
            path.write_text(
                "resolution,period_start,period_end,heating_produced_kwh,heating_consumed_kwh,note\n"
                "month,2026-06-01,2026-07-01,0,0,\n"
                "month,2026-10-01,2026-11-01,328,72,\n"
                "day,2026-11-16,2026-11-17,40,10,\n"
                "month,2026-12-01,2027-01-01,,,unreadable\n", encoding="utf-8")
            self.assertEqual(fa.unit_months(str(path)), {(2026, 6): 0.0, (2026, 10): 328.0})
            self.assertEqual(fa.unit_months(str(Path(tmp, "missing.csv"))), {})
            # As a spreadsheet saves it (byte-order mark), with a short last row.
            path.write_bytes(b"\xef\xbb\xbfresolution,period_start,heating_produced_kwh\r\n"
                             b"month,2026-06-01,0\r\nmonth\r\n")
            self.assertEqual(fa.unit_months(str(path)), {(2026, 6): 0.0})
            path.write_bytes(b"resolution,period_start\n\xff\xfe not text\n")  # unreadable: no months
            self.assertEqual(fa.unit_months(str(path)), {})

    def test_periods_first_then_months(self):
        june = [date(2026, 6, 8) + timedelta(days=d) for d in range(7)]
        months = {(2026, 6): 0.0, (2026, 10): 328.0}
        self.assertEqual(fa.heat_pump_modes(june, {}, months), (False, None))
        october = [date(2026, 10, 5) + timedelta(days=d) for d in range(7)]
        self.assertEqual(fa.heat_pump_modes(october, {}, months), (None, None))
        periods = {d: {"heating": 0.0, "cooling": 0.0} for d in june}
        periods[june[3]]["cooling"] = 2.0
        self.assertEqual(fa.heat_pump_modes(june, periods, months), (False, True))  # off: from the month
        self.assertEqual(fa.heat_pump_modes(june, periods, {}), (None, True))  # whole kWh prove no "off"
        periods[june[0]]["heating"] = 1.0
        self.assertEqual(fa.heat_pump_modes(june, periods, months), (True, True))
        across = [date(2026, 9, 28) + timedelta(days=d) for d in range(7)]  # September and October
        self.assertEqual(fa.heat_pump_modes(across, {}, {(2026, 9): 0.0, (2026, 10): 328.0}), (None, None))


class BaselineModelTest(unittest.TestCase):
    """E22: the adjusted baseline, fitted on the baseline weeks."""

    def test_recovers_base_temperature_and_coefficients(self):
        weeks = synthetic_baseline()
        model = fa.baseline_model(weeks, 0.30, 0.08)
        self.assertEqual(model["base_temperature_c"], 14.0)
        self.assertEqual(model["import_coefficients"], [5.0, 2.0, -0.1, 0.5])
        self.assertEqual(model["feed_coefficients"], [1.0, 0.2, 0.8, -0.3])
        self.assertEqual((model["r2_cost"], model["rms_cost_eur"], model["rms_out_of_sample_eur"]),
                         (1.0, 0.0, 0.0))
        self.assertEqual(model["baseline_weeks"], 104)
        self.assertTrue(all(abs(w["saving_eur"]) < 0.01 and w["in_range"] for w in weeks))

    def test_a_strategy_week_is_compared_with_the_baseline_under_its_weather(self):
        """A week of another strategy that imports 20 kWh less saves 20 × 0.30 = 6 € and does not
        enter the fit."""
        weeks = synthetic_baseline()
        weeks.append(synthetic_week(date(2027, 1, 4), [2.0] * 7, 60.0, strategy="optimizer", import_cut=20))
        model = fa.baseline_model(weeks, 0.30, 0.08)
        self.assertEqual(model["baseline_weeks"], 104)
        self.assertEqual(weeks[-1]["saving_eur"], 6.0)
        self.assertEqual(weeks[-1]["hdd"], 84.0)

    def test_weather_outside_the_baselines_range_is_flagged(self):
        weeks = synthetic_baseline()
        weeks.append(synthetic_week(date(2027, 1, 4), [-20.0] * 7, 60.0, strategy="optimizer"))
        weeks.append(synthetic_week(date(2027, 1, 11), [2.0] * 7, 1.0, strategy="optimizer"))  # PV low
        weeks.append(synthetic_week(date(2027, 1, 18), [2.0] * 7, 60.0, strategy="optimizer"))
        fa.baseline_model(weeks, 0.30, 0.08)
        self.assertEqual([w["in_range"] for w in weeks[-3:]], [False, False, True])

    def test_noise_shows_in_and_out_of_sample(self):
        """With noise on the import, the error out of sample is larger than in sample, and the
        autocorrelation pairs only consecutive weeks."""
        weeks = synthetic_baseline()
        for k, w in enumerate(weeks):
            noise = 8.0 * (((7 * k) % 11) / 10 - 0.5)  # deterministic, between −4 and +4 kWh
            w["import_kwh"] += noise
            w["cost_eur"] += noise * 0.30
        model = fa.baseline_model(weeks, 0.30, 0.08)
        self.assertGreater(model["rms_cost_eur"], 0.1)
        self.assertGreater(model["rms_out_of_sample_eur"], model["rms_cost_eur"])
        self.assertLess(model["r2_cost"], 1.0)
        self.assertIsNotNone(model["lag1_autocorrelation"])
        # Errors inside and outside the heating season (weeks colder than the 14 °C base); each
        # week's band is two out-of-sample errors of its period.
        periods = model["periods"]
        self.assertEqual(list(periods), ["heating", "outside"])
        self.assertEqual(periods["heating"]["weeks"], sum(w["temperature_c"] < 14.0 for w in weeks))
        self.assertEqual(periods["heating"]["weeks"] + periods["outside"]["weeks"], 104)
        january, july = weeks[2], weeks[27]  # 2025-01-20, 2025-07-14
        for week, name in ((january, "heating"), (july, "outside")):
            self.assertEqual(week["heating_period"], name == "heating")
            self.assertAlmostEqual(week["band_eur"], 2 * periods[name]["rms_out_of_sample_eur"],
                                   delta=0.02)  # both rounded to cents
        every_other = weeks[::2]  # no two consecutive weeks left: no pair, no autocorrelation
        self.assertIsNone(fa.baseline_model(every_other, 0.30, 0.08)["lag1_autocorrelation"])

    def test_degenerate_baseline_raises_nothing_unhandled(self):
        """Equal cost every week: no R², but no error either."""
        weeks = [synthetic_week(date(2025, 1, 6) + timedelta(weeks=k), [20.0] * 7, 100.0 + k)
                 for k in range(30)]
        for w in weeks:
            w["import_kwh"], w["feed_kwh"], w["cost_eur"] = 10.0, 0.0, 3.0
        model = fa.baseline_model(weeks, 0.30, 0.08)
        self.assertIsNone(model)  # all degree days 0: the degree-day term cannot be fitted

    def test_known_heating_decides_the_period_and_cooling_weeks_stay_out(self):
        """A baseline week known to be unheated is outside the heating season even when colder
        than the base temperature; a week of another strategy is judged by temperature alone,
        since the strategy decides whether to heat; a week with cooling is not fitted."""
        weeks = synthetic_baseline()
        cold_unheated = weeks[10]  # 2025-03-17, mean temperature below the 14 °C base
        self.assertLess(cold_unheated["temperature_c"], 14.0)
        cold_unheated["heated"] = False
        strategy = synthetic_week(date(2027, 1, 4), [5.0] * 7, 60.0, strategy="optimizer")
        strategy["heated"] = False
        cooled = synthetic_week(date(2027, 7, 5), [22.0] * 7, 250.0)
        cooled["cooled"], cooled["import_kwh"] = True, 999.0  # would spoil the fit if used
        model = fa.baseline_model(weeks + [strategy, cooled], 0.30, 0.08)
        self.assertFalse(cold_unheated["heating_period"])
        self.assertTrue(strategy["heating_period"])
        self.assertEqual((model["baseline_weeks"], model["cooling_weeks_left_out"]), (104, 1))
        self.assertEqual(model["weeks_known_unheated"], 1)
        self.assertEqual(model["import_coefficients"], [5.0, 2.0, -0.1, 0.5])

    def test_too_few_baseline_weeks(self):
        self.assertIsNone(fa.baseline_model(synthetic_baseline(fa.MIN_BASELINE_WEEKS - 1), 0.30, 0.08))

    def test_december_belongs_to_the_next_years_winter_quarter(self):
        self.assertEqual(fa.quarter({"start": "2025-12-01"}), (2026, 0))
        self.assertEqual(fa.quarter({"start": "2026-02-23"}), (2026, 0))
        self.assertEqual(fa.quarter({"start": "2026-03-02"}), (2026, 1))

    def test_an_unknown_baseline_week_above_the_base_is_outside(self):
        weeks = synthetic_baseline()
        warm = next(w for w in weeks if w["temperature_c"] >= 14.0)
        warm["heated"] = None
        fa.baseline_model(weeks, 0.30, 0.08)
        self.assertFalse(warm["heating_period"])

    def test_least_squares_refuses_dependent_regressors(self):
        with self.assertRaises(ZeroDivisionError):
            fa.least_squares([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]], [1.0, 2.0, 3.0])


class Helpers(unittest.TestCase):
    def test_forecast_solar_partial_periods_go_to_the_hour_they_end_in(self):
        body = json.dumps({"result": {"watt_hours_period": {
            "2026-11-21T07:00:05+00:00": 0, "2026-11-21T08:00:00+00:00": 120,
            "2026-11-21T15:40:24+00:00": 30}}}).encode()
        hourly = fa.forecast_solar_hourly_wh(body)
        start = datetime(2026, 11, 21, tzinfo=timezone.utc)
        self.assertEqual(hourly[start.replace(hour=7)], 120)
        self.assertEqual(hourly[start.replace(hour=15)], 30)

    def test_next_run(self):
        now = datetime(2026, 11, 21, 9, 30, tzinfo=timezone.utc)
        self.assertEqual(fa.seconds_until_next_run(now), 32 * 60)


if __name__ == "__main__":
    unittest.main()
