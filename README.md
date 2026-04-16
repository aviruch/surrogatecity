# Surrogate City Finder — Python (Flask) Port


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
