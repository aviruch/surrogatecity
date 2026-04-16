# Surrogate City Finder — Python (Flask) Port

A literal port of the original PHP project to Python. The frontend (HTML + jQuery +
Google Maps) is unchanged; only the four PHP backend files were rewritten as Flask
routes.

## Project layout

```
cityfinder/
├── app.py               # All backend logic (replaces back.php, ll.php, submit.php, submit1.php)
├── requirements.txt
├── templates/           # Served by Flask
│   ├── mainpage.html    # Landing page — city autocomplete
│   ├── page2.html       # Results page — map + chart + table
│   ├── Autocomplete.html
│   ├── tablesorter.html
│   └── style-demo.html
└── static/              # Served at /
    ├── a.js             # jQuery 1.11.1
    ├── jquery-latest.js
    ├── jquery.tablesorter.js
    └── im.png
```

## Setup

```bash
cd cityfinder
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8081/ in a browser.

## Endpoint mapping

| Original PHP                                       | Flask route                    |
|----------------------------------------------------|--------------------------------|
| `back.php`                                         | `/back` (also `/back.php`)     |
| `ll.php`                                           | `/ll` (also `/ll.php`)         |
| `submit.php`                                       | `/submit` (also `/submit.php`) |
| `submit1.php`                                      | `/submit1` (also `/submit1.php`) |
| `test.php` *(was missing from upload — see below)* | `/test` (also `/finder/surrogate/test.php`) |

Both the clean paths (`/submit1`) and the legacy `.php` paths are mounted, so any
hardcoded URL in the frontend keeps working.

## Important: the missing `test.php`

The original `page2.html` calls a fifth PHP file at
`http://localhost:8081/finder/surrogate/test.php` that was **not included** in
the upload. That endpoint takes `latitude / longitude / altitude / latrange /
altrange` and returns a JSON array of candidate cities with monthly temperature
data — clearly backed by a database of cities and climate records.

Without that database, the "find surrogate cities" feature cannot return real
results. `app.py` includes a stub that returns `[]` so the page still loads
cleanly. To make the full feature work, replace the `test_stub()` function in
`app.py` with a real query against your city-climate data source. The expected
response shape is a JSON array of objects like:

```json
[
  {
    "cityname": "Jaipur",
    "countryname": "India",
    "latitude": "26.9",
    "longitude": "75.8",
    "mjan": "22.8", "mfeb": "26.1", "mmar": "31.4", ...,
    "njan": "8.3",  "nfeb": "11.1", "nmar": "16.3", ...
  },
  ...
]
```

Fields `mjan..mdec` are monthly average highs and `njan..ndec` are monthly
average lows (both in °C).

## Fixes applied during porting

Two bugs in the original frontend were fixed because they prevented the app from
working at all:

1. **Query string separator**: the original `window.open(...)` in `mainpage.html`
   and `page2.html` built URLs using `?` as a separator between every parameter
   (`?city=...?state=...?country=...`) instead of `&`. Browsers treat everything
   after the first `?` as a single parameter value, so only `text` was parseable
   — `city`, `state`, `country`, `lat`, `lng`, etc. were silently lost. Changed
   to `&` and wrapped values in `encodeURIComponent()`.

2. **Hardcoded hostnames**: `localhost:8081/cityfinder2/*.php` URLs were changed
   to relative paths (`/back`, `/submit1`, etc.) so the app works regardless of
   where it's deployed.

Everything else (including the Wikipedia scraping logic's fragility — see below)
is a literal port.

## Known fragility (inherited from the PHP)

The Wikipedia-scraping endpoints (`/back`, `/ll`, `/submit1`) parse Wikipedia's
infobox HTML by searching for literal strings like `"Average high"`, `"</th>"`,
`"</tr>"`, and `'<span class="plainlinks nourlexpansion">'`. Wikipedia's
infobox HTML has evolved since the original PHP was written, so:

- Some cities will return an empty array or partial data.
- The Celsius/Fahrenheit detection (which keys off `"Average high °F"` or the
  `"°C)"` marker) depends on exact formatting that may no longer match.
- `ll.php` is **hardcoded to Jaipur** — it ignores whatever city you send it.
  That's a bug in the original, preserved here.

If you want a reliable version, the right fix is to use Wikipedia's REST API
(`https://en.wikipedia.org/api/rest_v1/page/html/{title}`) or a weather API
(Open-Meteo has free historical climate data), but you asked for a literal
port, so the brittle string parsing is intact.

## Google Maps API key

The frontend uses a Google Maps Places API key hardcoded in the HTML. Your
original key was still embedded — if it no longer works, replace the `key=`
parameter in the `<script src="https://maps.googleapis.com/maps/api/js?...">`
tags in `mainpage.html`, `Autocomplete.html`, and `page2.html` with a current
key.
