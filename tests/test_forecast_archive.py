"""Tests for archive/forecast_archive.py (spec: forecast-archive, examples E5 and E6).

The responses are synthetic: real ones contain the caller's public IP address
and place name, so they must not be committed.
"""

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


class FakeServices:
    """A local HTTP server standing in for both services. It records each request."""

    def __init__(self):
        self.now = T0
        self.status = {"/solar": 200, "/weather": 200}
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fake.requests.append(self.path)
                body = solar_body(fake.now) if self.path == "/solar" else weather_body(fake.now)
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
        ]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ArchiveTest(unittest.TestCase):
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

    def test_a_day_of_fetches(self):
        self.run_hours(24)
        for service in (fa.FORECAST_SOLAR, fa.OPEN_METEO):
            self.assertEqual(self.count(service, "error IS NULL"), 24)

    def test_restart_loop_calls_once_per_hour(self):
        for minute in (2, 10, 20, 40, 59):
            now = T0 + timedelta(minutes=minute)
            fa.fetch_all(self.conn, self.fake.services, now)
        self.assertEqual(sorted(self.fake.requests), ["/solar", "/weather"])

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
        self.assertEqual(len(errors), 2)
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
