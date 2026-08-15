"""Seed data/demo_cache.sqlite with SYNTHETIC climate data for offline demos.

Run:  python scripts/seed_demo.py
Then: SCF_DEMO=1 python app.py     (Windows: set SCF_DEMO=1 && python app.py)

The demo cache lets the app be exercised without internet access. The numbers
are plausible but SYNTHETIC (except Hyderabad and Sholapur, which use real
published normals so the paper's reference pair can be reproduced). Never use
demo mode for real work — run without SCF_DEMO so real Open-Meteo data is
fetched and cached in data/climate_cache.sqlite.
"""
import csv
import hashlib
import math
import os
import sqlite3
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

DB = os.path.join(BASE, "data", "demo_cache.sqlite")
STATIONS = os.path.join(BASE, "data", "stations.csv")

# Demo region: around Hyderabad, India (the paper's test case)
CENTER = (17.385, 78.4867)
LAT_BAND = 12.0
RADIUS_KM = 800.0

REAL = {
    # name-substring: (elevation, tmax[12], tmin[12])
    "Hyderabad": (542.0,
        [28.6, 31.8, 35.2, 37.6, 38.8, 34.4, 30.5, 29.6, 30.1, 30.4, 28.8, 27.8],
        [14.7, 17.0, 20.3, 24.1, 26.0, 23.9, 22.5, 22.0, 21.7, 20.0, 16.4, 14.1]),
    "Sholapur": (479.0,
        [30.9, 33.7, 37.1, 39.4, 40.1, 34.8, 30.6, 29.9, 30.6, 31.5, 30.4, 29.7],
        [15.4, 17.4, 20.8, 24.2, 25.4, 23.3, 21.9, 21.3, 21.1, 20.1, 17.0, 15.0]),
}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + \
        math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def synth(lat, lon, name):
    """Synthetic-but-plausible monthly normals for a tropical Indian station."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    elev = 200 + (h % 500)                       # 200-700 m
    base = 32.5 - 0.25 * (lat - 17.0) - 0.004 * (elev - 450)
    tmax, tmin = [], []
    for m in range(12):
        # pre-monsoon peak in May, monsoon dip Jul-Sep, cool winter
        season = 4.5 * math.sin((m - 1.5) * math.pi / 6.0)
        monsoon = -4.0 * math.exp(-((m - 6.5) ** 2) / 3.0)
        jitter = ((h >> (m + 3)) % 100) / 100.0 - 0.5
        hi = base + season + monsoon + jitter
        lo = hi - (13.0 - 4.5 * math.exp(-((m - 6.5) ** 2) / 4.0)) + jitter / 2
        tmax.append(round(hi, 1))
        tmin.append(round(lo, 1))
    return float(elev), tmax, tmin


def key(lat, lon):
    return f"{round(float(lat), 3)}:{round(float(lon), 3)}"


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE climate (
        key TEXT PRIMARY KEY, elevation REAL, tmax TEXT, tmin TEXT, fetched_at INTEGER)""")

    def put(lat, lon, elev, tmax, tmin):
        conn.execute("INSERT OR REPLACE INTO climate VALUES (?,?,?,?,?)",
                     (key(lat, lon), elev,
                      ",".join(f"{v:.2f}" for v in tmax),
                      ",".join(f"{v:.2f}" for v in tmin),
                      int(time.time())))

    n = 0
    with open(STATIONS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lat, lon = float(r["latitude"]), float(r["longitude"])
            if abs(lat - CENTER[0]) > LAT_BAND:
                continue
            if haversine_km(CENTER[0], CENTER[1], lat, lon) > RADIUS_KM:
                continue
            for sub, vals in REAL.items():
                if sub.lower() in r["name"].lower():
                    put(lat, lon, *vals)
                    break
            else:
                put(lat, lon, *synth(lat, lon, r["name"]))
            n += 1

    # the input location itself (Hyderabad city centre)
    put(CENTER[0], CENTER[1], *REAL["Hyderabad"])
    conn.commit()
    conn.close()
    print(f"Seeded {n} stations + input location into {DB}")
    print("Run:  SCF_DEMO=1 python app.py   and search for Hyderabad")


if __name__ == "__main__":
    main()
