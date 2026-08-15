# Surrogate City Finder — open-data edition

Web tool from the BS2015 paper *"Surrogate City Finder — Weather Data Tool"*
(Garg, Nikhil, Rallapalli, Bhatia, Subhash, Kasireddy — IIIT Hyderabad),
rebuilt without any Google or Wikipedia dependencies. For a given location,
it shortlists the best-matched EnergyPlus weather-file locations based on
latitude, altitude, monthly temperature range and distance, ranks them by
RMS temperature error, and shows them on a map with a comparison chart.

## What replaced what

| Before (2015)                         | Now                                          |
|---------------------------------------|----------------------------------------------|
| Google Maps + Places autocomplete     | Leaflet + OpenStreetMap tiles, Nominatim geocoding |
| Google Charts                         | Chart.js                                     |
| Google Elevation API                  | Open-Meteo Elevation API                     |
| Wikipedia infobox scraping (brittle)  | Open-Meteo ERA5 monthly normals (2015–2024)  |
| Missing `test.php` city database      | Bundled index of **17,640 EPW weather-file locations** (US-DOE + climate.onebuilding.org) with on-demand climate normals |
| PHP backend                           | Flask (`app.py`)                             |

No API keys are required anywhere. Nominatim and Open-Meteo are free,
open services (please respect their fair-use policies).

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8081/ — search a location, adjust the filter ranges
(latitude ±°, altitude ±m, avg high/low ±°C, radius km), submit.

**The first search in a new region takes up to a minute**: the backend
fetches 10-year ERA5 daily data from Open-Meteo for each candidate station
and reduces it to monthly mean-daily-max/min normals. Results are cached
permanently in `data/climate_cache.sqlite`, so every later search in that
region is instant.

## How it works

1. `templates/mainpage.html` — Nominatim autocomplete picks the location
   (lat/lon), filters are passed to the results page by query string
   (same parameter names as the original tool).
2. `GET /api/climate?lat&lon` — monthly normals + elevation of the input
   location (Open-Meteo ERA5, cached).
3. `POST /test` — candidate stations from `data/stations.csv` filtered by
   latitude band, distance radius and altitude range; monthly normals
   attached from cache or fetched. (Also mounted at the legacy path
   `/finder/surrogate/test.php`.)
4. `templates/page2.html` — applies the paper's monthly temperature filter
   (every month's avg high/low within the chosen deviation), computes
   RMS Max / RMS Min / RMS Total exactly as in the paper, and renders the
   Leaflet map, Chart.js comparison chart and sortable results table.
   Every result row links to the actual EPW weather file download.

## Project layout

```
├── app.py                  # Flask backend (all endpoints)
├── requirements.txt
├── data/
│   ├── stations.csv        # bundled EPW station index (17,640 locations)
│   └── climate_cache.sqlite# created at runtime (Open-Meteo normals)
├── scripts/
│   └── seed_demo.py        # synthetic offline demo data (testing only)
├── templates/
│   ├── mainpage.html       # landing page — search + filters
│   └── page2.html          # results — map + chart + table
└── static/
    └── style.css
```

`templates/Autocomplete.html`, `tablesorter.html`, `style-demo.html` and
`static/a.js`, `jquery*.js` belonged to the old Google-Maps version and are
no longer used — they can be deleted.

## Offline demo mode (testing only)

```bash
python scripts/seed_demo.py
SCF_DEMO=1 python app.py        # Windows: set SCF_DEMO=1 && python app.py
```

Seeds a separate `data/demo_cache.sqlite` with synthetic data around
Hyderabad (Hyderabad and Sholapur use real published normals, reproducing
the paper's Table 2 reference pair) so the whole UI can be exercised with
no internet. Never use demo mode for real work.

## Data sources & credits

- Station index extracted from the [Ladybug Tools EPW map](https://github.com/ladybug-tools/epwmap)
  (US-DOE EnergyPlus weather data + [climate.onebuilding.org](https://climate.onebuilding.org)).
- Climate normals & elevation: [Open-Meteo](https://open-meteo.com/) (ERA5 reanalysis).
- Geocoding: [Nominatim / OpenStreetMap](https://nominatim.org/).
