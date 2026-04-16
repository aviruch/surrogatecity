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
