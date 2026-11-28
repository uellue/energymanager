"""Compare Open-Meteo's past forecasts of named models with the measured PV production.

Runs inside the forecast archive's container on the automation PC, where both stores are
mounted; opens them read-only and prints aggregates only:

    scp tools/compare_pv_forecasts.py automation:/tmp/
    ssh automation 'docker cp /tmp/compare_pv_forecasts.py energymanager-archive-1:/tmp/ &&
        docker exec energymanager-archive-1 python3 /tmp/compare_pv_forecasts.py [stats|align]'

`stats` (default): per model and lead time, daily energy forecast ÷ measured, mean absolute
error, correlation; the same per hour; "tomorrow like today" as a baseline.
`align`: per month, the production-weighted mean hour of day, measured and forecast; a clock
error shows as a constant difference.

Forecast PV = global tilted irradiance (W/m², roof plane) × EM_KWP / 1000, without losses.
Open-Meteo labels each hourly value by the end of its hour. The inverter's clock follows
local time (it jumped an hour back on 2026-10-25), so records from before the latest clock
change are shifted by the change of the UTC offset in TZ (default Europe/Berlin).
"""
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, "/app")
import headroom as hr  # noqa: E402

MODELS = ("dwd_icon_d2", "dwd_icon_eu", "ecmwf_ifs")
LEADS = (("latest run", ""), ("1 day ahead", "_previous_day1"), ("2 days ahead", "_previous_day2"))
SINCE = datetime(2026, 8, 26, tzinfo=timezone.utc)


def stats(pairs):
    """(n, sum(forecast) / sum(measured), mean absolute error, correlation) of (forecast, measured)."""
    f = [p[0] for p in pairs]
    m = [p[1] for p in pairs]
    n = len(pairs)
    mf, mm = sum(f) / n, sum(m) / n
    cov = sum((a - mf) * (b - mm) for a, b in pairs)
    r = cov / math.sqrt(sum((a - mf) ** 2 for a in f) * sum((b - mm) ** 2 for b in m))
    return n, sum(f) / sum(m), sum(abs(a - b) for a, b in pairs) / n, r


def utc_hour(d, hh):
    return datetime(d.year, d.month, d.day, hh, tzinfo=timezone.utc)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "stats"
    kwp = float(os.environ["EM_KWP"])
    tz = ZoneInfo(os.environ.get("TZ", "Europe/Berlin"))
    fc = sqlite3.connect("file:/data/forecasts.sqlite?mode=ro", uri=True)
    col = sqlite3.connect("file:/collector/collector.sqlite?mode=ro", uri=True)

    row = fc.execute("SELECT body FROM fetch WHERE service = 'open-meteo-previous-runs'"
                     " AND error IS NULL ORDER BY fetched_at DESC LIMIT 1").fetchone()
    h = json.loads(row[0])["hourly"]
    labels = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]

    offset = hr.clock_offset_s(col)
    now_utcoffset = datetime.now(tz).utcoffset()
    # Measured Wh per hour [start, start + 1 h), from the 5-minute mean powers of both inputs.
    hourly_meas, count = defaultdict(float), defaultdict(int)
    for key in ("pv_a", "pv_b"):
        for t, w in hr.records(col, hr.LOG_SERIES[key], SINCE, offset):
            t -= t.astimezone(tz).utcoffset() - now_utcoffset
            start = (t - timedelta(minutes=5)).replace(minute=0, second=0)
            hourly_meas[start] += w / 12
            if key == "pv_a":
                count[start] += 1
    complete = {s for s, n in count.items() if n == 12}

    if mode == "align":
        gti = dict(zip(labels, h["global_tilted_irradiance_ecmwf_ifs"]))
        by_month = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        for start in complete:
            g = gti.get(start + timedelta(hours=1))
            if g is None:
                continue
            mid = start.hour + 0.5
            m = by_month[start.strftime("%Y-%m")]
            m[0] += hourly_meas[start] * mid
            m[1] += hourly_meas[start]
            m[2] += g * mid
            m[3] += g
        for k in sorted(by_month):
            m = by_month[k]
            print(f"{k} measured {m[0] / m[1]:.2f} h UTC, forecast (ECMWF, latest run) {m[2] / m[3]:.2f} h UTC")
        return

    full_days = sorted({s.date() for s in complete
                        if all(utc_hour(s.date(), hh) in complete for hh in range(24))})
    print(f"clock offset {offset} s; full days with measurements: {len(full_days)} "
          f"({full_days[0]} to {full_days[-1]})")
    meas_day = {d: sum(hourly_meas[utc_hour(d, hh)] for hh in range(24)) / 1000 for d in full_days}

    print("\nDaily energy, kWh. ratio = sum(forecast) / sum(measured); MAE = mean absolute error;"
          " r = correlation; last column: MAE after dividing the forecast by its ratio.")
    print(f"{'model':14} {'lead':13} {'days':>4} {'ratio':>6} {'MAE':>6} {'r':>5} {'scaled':>6}")
    for model in MODELS:
        for lead_name, suffix in LEADS:
            series = dict(zip(labels, h.get(f"global_tilted_irradiance{suffix}_{model}", [])))
            pairs, per_month = [], defaultdict(list)
            for d in full_days:
                vals = [series.get(utc_hour(d, hh) + timedelta(hours=1)) for hh in range(24)]
                if any(v is None for v in vals):
                    continue
                p = (sum(vals) * kwp / 1000, meas_day[d])
                pairs.append(p)
                per_month[d.strftime("%Y-%m")].append(p)
            if len(pairs) < 10:
                print(f"{model:14} {lead_name:13} {len(pairs):>4}  (too few)")
                continue
            n, ratio, mae, r = stats(pairs)
            scaled = sum(abs(a / ratio - b) for a, b in pairs) / n
            months = ", ".join(f"{k[5:]} {stats(v)[1]:.2f}" for k, v in sorted(per_month.items()))
            print(f"{model:14} {lead_name:13} {n:>4} {ratio:6.2f} {mae:6.2f} {r:5.2f} {scaled:6.2f}"
                  f"   ratio by month: {months}")

    by_month = defaultdict(list)
    for d, v in meas_day.items():
        by_month[d.strftime("%Y-%m")].append(v)
    print("\nMeasured, mean kWh/day: "
          + ", ".join(f"{k} {sum(v) / len(v):.1f}" for k, v in sorted(by_month.items())))

    print("\nHourly, 1 day ahead, hours with measured or forecast > 50 Wh: MAE in Wh")
    for model in MODELS:
        series = dict(zip(labels, h.get(f"global_tilted_irradiance_previous_day1_{model}", [])))
        pairs = []
        for start in complete:
            g = series.get(start + timedelta(hours=1))
            if g is None:
                continue
            f, m = g * kwp, hourly_meas[start]
            if f > 50 or m > 50:
                pairs.append((f, m))
        n, ratio, mae, r = stats(pairs)
        print(f"{model:14} hours {n:>5}  ratio {ratio:.2f}  MAE {mae:5.0f}  r {r:.2f}")

    pairs = [(meas_day[d - timedelta(days=1)], meas_day[d])
             for d in full_days if d - timedelta(days=1) in meas_day]
    n, ratio, mae, r = stats(pairs)
    print(f"\nBaseline 'tomorrow like today' (measured): days {n}, MAE {mae:.2f} kWh/day, r {r:.2f}")


if __name__ == "__main__":
    main()
