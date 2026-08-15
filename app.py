"""
Surrogate City Finder — open-data edition.

Rebuilt per the BS2015 paper "Surrogate City Finder - Weather Data Tool"
(Garg et al., IIIT Hyderabad) with all Google and Wikipedia dependencies
removed:

  * Geocoding / autocomplete ..... OpenStreetMap Nominatim (client side)
  * Map ........................... Leaflet + OpenStreetMap tiles (client side)
  * Elevation ..................... Open-Meteo Elevation API
  * Climate of the input location . Open-Meteo ERA5 archive (monthly normals)
  * Candidate surrogate cities .... Bundled index of 17,640 EnergyPlus/EPW
                                    weather-file locations (US-DOE +
                                    climate.onebuilding.org), monthly normals
                                    fetched from Open-Meteo on demand and
                                    cached in a local SQLite database.

Endpoints
---------
  GET  /                     main page (location search + filters)
  GET  /page2.html           results page (map + chart + table)
  GET  /api/climate          ?lat=..&lon=..  -> monthly normals + elevation
  GET  /api/elevation        ?lat=..&lon=..  -> elevation only
  POST /test  (legacy path)  latitude/longitude/altitude/latrange/altrange/
                             radius -> JSON array of candidate stations with
                             mjan..mdec / njan..ndec monthly temps
  also mounted: /finder/surrogate/test.php (legacy compatibility)

First query in a new region fetches climate normals for the candidate
stations from Open-Meteo (free, no API key) and caches them permanently in
data/climate_cache.sqlite; subsequent queries are instant.

Run:  pip install -r requirements.txt && python app.py
Then open http://localhost:8081/
"""

import csv
import math
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIONS_CSV = os.path.join(DATA_DIR, "stations.csv")

# Demo mode: SCF_DEMO=1 uses a separate cache seeded with sample data so the
# app can be exercised without internet access. Real deployments never set it.
DEMO_MODE = os.environ.get("SCF_DEMO") == "1"
CACHE_DB = os.path.join(DATA_DIR, "demo_cache.sqlite" if DEMO_MODE else "climate_cache.sqlite")

# Years used to compute monthly climate normals from ERA5 daily data.
NORMALS_START = "2015-01-01"
NORMALS_END = "2024-12-31"

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
ELEVATION_API = "https://api.open-meteo.com/v1/elevation"

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]

app = Flask(__name__, static_folder="static", template_folder="templates")

_db_lock = threading.Lock()


# ---------------------------------------------------------------------------
# SQLite cache
# ---------------------------------------------------------------------------

def _db():
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS climate (
               key TEXT PRIMARY KEY,       -- 'lat:lon' rounded to 3 decimals
               elevation REAL,
               tmax TEXT,                  -- 12 comma-separated monthly values
               tmin TEXT,
               fetched_at INTEGER
           )"""
    )
    return conn


def _key(lat, lon):
    return f"{round(float(lat), 3)}:{round(float(lon), 3)}"


def cache_get_many(coords):
    """coords: list of (lat, lon). Returns {key: (elevation, [tmax], [tmin])}."""
    keys = [_key(la, lo) for la, lo in coords]
    out = {}
    with _db_lock:
        conn = _db()
        try:
            for i in range(0, len(keys), 500):
                chunk = keys[i:i + 500]
                q = ",".join("?" * len(chunk))
                for k, elev, tmax, tmin in conn.execute(
                        f"SELECT key, elevation, tmax, tmin FROM climate WHERE key IN ({q})", chunk):
                    out[k] = (elev,
                              [float(x) for x in tmax.split(",")],
                              [float(x) for x in tmin.split(",")])
        finally:
            conn.close()
    return out


def cache_put(lat, lon, elevation, tmax, tmin):
    with _db_lock:
        conn = _db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO climate (key, elevation, tmax, tmin, fetched_at) VALUES (?,?,?,?,?)",
                (_key(lat, lon), elevation,
                 ",".join(f"{v:.2f}" for v in tmax),
                 ",".join(f"{v:.2f}" for v in tmin),
                 int(time.time())))
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Station index (bundled CSV)
# ---------------------------------------------------------------------------

_stations = None


def stations():
    global _stations
    if _stations is None:
        rows = []
        with open(STATIONS_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({
                        "wmo": r["wmo"],
                        "name": r["name"],
                        "country": r["country"],
                        "lat": float(r["latitude"]),
                        "lon": float(r["longitude"]),
                        "source": r["source"],
                        "epw_url": r["epw_url"],
                    })
                except ValueError:
                    continue
        _stations = rows
    return _stations


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Open-Meteo fetchers
# ---------------------------------------------------------------------------

def fetch_normals(lat, lon):
    """Monthly mean-daily-max / mean-daily-min for one point from ERA5.

    Returns (elevation, [12 tmax], [12 tmin]) or None on failure.
    """
    cached = cache_get_many([(lat, lon)])
    k = _key(lat, lon)
    if k in cached:
        return cached[k]
    if DEMO_MODE:
        return None
    try:
        resp = requests.get(ARCHIVE_API, params={
            "latitude": round(float(lat), 4),
            "longitude": round(float(lon), 4),
            "start_date": NORMALS_START,
            "end_date": NORMALS_END,
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
        }, timeout=60)
        resp.raise_for_status()
        j = resp.json()
        daily = j["daily"]
        elevation = j.get("elevation")
        sums_max = [0.0] * 12
        sums_min = [0.0] * 12
        counts = [0] * 12
        for date, tmax, tmin in zip(daily["time"],
                                    daily["temperature_2m_max"],
                                    daily["temperature_2m_min"]):
            if tmax is None or tmin is None:
                continue
            m = int(date[5:7]) - 1
            sums_max[m] += tmax
            sums_min[m] += tmin
            counts[m] += 1
        if not all(counts):
            return None
        tmax12 = [sums_max[i] / counts[i] for i in range(12)]
        tmin12 = [sums_min[i] / counts[i] for i in range(12)]
        cache_put(lat, lon, elevation, tmax12, tmin12)
        return (elevation, tmax12, tmin12)
    except Exception:
        return None


def fetch_elevations(coords):
    """Batch elevation lookup. coords: list of (lat, lon) -> {key: elevation}."""
    out = {}
    if DEMO_MODE:
        return out
    for i in range(0, len(coords), 100):
        chunk = coords[i:i + 100]
        try:
            resp = requests.get(ELEVATION_API, params={
                "latitude": ",".join(str(round(la, 4)) for la, lo in chunk),
                "longitude": ",".join(str(round(lo, 4)) for la, lo in chunk),
            }, timeout=30)
            resp.raise_for_status()
            elevs = resp.json().get("elevation", [])
            for (la, lo), e in zip(chunk, elevs):
                out[_key(la, lo)] = e
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/mainpage.html")
def mainpage():
    return render_template("mainpage.html")


@app.route("/page2.html")
def page2():
    return render_template("page2.html")


@app.route("/<path:filename>")
def root_static(filename):
    return send_from_directory("static", filename)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/climate")
def api_climate():
    try:
        lat = float(request.values["lat"])
        lon = float(request.values["lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "lat and lon are required"}), 400
    normals = fetch_normals(lat, lon)
    if normals is None:
        return jsonify({"error": "climate data unavailable for this location"}), 502
    elevation, tmax, tmin = normals
    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "elevation": elevation,
        "tmax": [round(v, 1) for v in tmax],
        "tmin": [round(v, 1) for v in tmin],
        "avg_high": round(sum(tmax) / 12, 1),
        "avg_low": round(sum(tmin) / 12, 1),
    })


@app.route("/api/elevation")
def api_elevation():
    try:
        lat = float(request.values["lat"])
        lon = float(request.values["lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "lat and lon are required"}), 400
    cached = cache_get_many([(lat, lon)])
    k = _key(lat, lon)
    if k in cached:
        return jsonify({"elevation": cached[k][0]})
    elevs = fetch_elevations([(lat, lon)])
    if k not in elevs:
        return jsonify({"error": "elevation unavailable"}), 502
    return jsonify({"elevation": elevs[k]})


@app.route("/test", methods=["POST", "GET"])
@app.route("/finder/surrogate/test.php", methods=["POST", "GET"])
def surrogate_candidates():
    """Return candidate surrogate stations near the input location.

    Parameters (legacy names preserved):
        latitude, longitude, altitude  — the input location
        latrange   — max |Δlatitude| in degrees
        altrange   — max |Δaltitude| in metres
        radius     — max distance in km (optional; legacy clients filtered
                     distance client-side, so this defaults generously)
    """
    try:
        lat = float(request.values["latitude"])
        lon = float(request.values["longitude"])
    except (KeyError, ValueError):
        return jsonify([])
    try:
        alt = float(request.values.get("altitude", ""))
    except ValueError:
        alt = None
    latrange = _float_or(request.values.get("latrange"), 10.0)
    altrange = _float_or(request.values.get("altrange"), 100.0)
    radius = _float_or(request.values.get("radius"), 2000.0)

    # 1. Cheap geometric prefilter: latitude band + distance radius.
    cands = []
    for s in stations():
        if abs(s["lat"] - lat) > latrange:
            continue
        d = haversine_km(lat, lon, s["lat"], s["lon"])
        if d <= radius:
            cands.append((d, s))
    cands.sort(key=lambda t: t[0])
    # Safety cap: closest 400 stations is far more than the UI needs.
    cands = cands[:400]

    # 2. Elevation filter (batch-fetch missing elevations, cached with climate).
    coords = [(s["lat"], s["lon"]) for _, s in cands]
    cached = cache_get_many(coords)
    missing = [(la, lo) for la, lo in coords if _key(la, lo) not in cached]
    elevs = fetch_elevations(missing) if missing else {}

    def station_elev(s):
        k = _key(s["lat"], s["lon"])
        if k in cached:
            return cached[k][0]
        return elevs.get(k)

    if alt is not None:
        cands = [(d, s) for d, s in cands
                 if station_elev(s) is None or abs(station_elev(s) - alt) <= altrange]

    # 3. Climate normals for the survivors (cache first, then Open-Meteo).
    results = []
    to_fetch = []
    for d, s in cands:
        k = _key(s["lat"], s["lon"])
        if k in cached:
            results.append((d, s, cached[k]))
        else:
            to_fetch.append((d, s))

    if to_fetch and not DEMO_MODE:
        def _worker(item):
            d, s = item
            n = fetch_normals(s["lat"], s["lon"])
            return (d, s, n)
        with ThreadPoolExecutor(max_workers=6) as ex:
            for d, s, n in ex.map(_worker, to_fetch):
                if n is not None:
                    results.append((d, s, n))

    results.sort(key=lambda t: t[0])
    out = []
    for d, s, (elevation, tmax, tmin) in results:
        row = {
            "cityname": s["name"],
            "countryname": s["country"],
            "latitude": str(s["lat"]),
            "longitude": str(s["lon"]),
            "elevation": None if elevation is None else round(elevation, 1),
            "distance_km": round(d, 1),
            "source": s["source"],
            "epw_url": s["epw_url"],
        }
        for i, m in enumerate(MONTHS):
            row["m" + m] = f"{tmax[i]:.1f}"   # monthly mean daily max
            row["n" + m] = f"{tmin[i]:.1f}"   # monthly mean daily min
        out.append(row)
    return jsonify(out)


def _float_or(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    if DEMO_MODE:
        print("*** SCF_DEMO=1 — running from the offline demo cache; "
              "results are sample data, not real climate normals. ***")
    app.run(host="0.0.0.0", port=8081, debug=True)
