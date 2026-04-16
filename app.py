"""
Surrogate City Finder — Flask port of the original PHP project.

T

The Wikipedia-scraping logic uses the SAME string-index / substring approach
as the original PHP (mb_strpos / mb_substr / mb_split), translated directly
to Python. This means it has the SAME fragility as the original: if Wikipedia
changes its infobox HTML even slightly, these endpoints will return empty or
garbled data. That is by design — the user asked for a literal port.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:8081/mainpage.html
"""

import json
import re
import requests
from flask import Flask, request, jsonify, send_from_directory, render_template

app = Flask(__name__, static_folder="static", template_folder="templates")



def mb_strpos(haystack, needle, offset=0):
    """PHP mb_strpos — returns first index of needle in haystack, or -1."""
    try:
        return haystack.index(needle, offset)
    except ValueError:
        return -1


def mb_substr(s, start, length):
    """PHP mb_substr($s, $start, $length)."""
    return s[start:start + length]


def mb_split(pattern, s):
    """PHP mb_split — regex split. PHP's mb_split uses POSIX regex, but for
    the literal strings the original code splits on ('</td>', '>', '<'),
    re.split with re.escape gives identical results."""
    return re.split(pattern, s)


def file_get_contents(url):
    """PHP file_get_contents — download the URL body as text. We set a
    User-Agent because Wikipedia rejects the default requests UA for some
    paths."""
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (SurrogateCityFinder)"})
    r.encoding = "utf-8"
    return r.text


# ----------------------------------------------------------------------------
# Static page routes — serve the original HTML templates directly.
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("mainpage.html")


@app.route("/mainpage.html")
def mainpage():
    return render_template("mainpage.html")


@app.route("/page2.html")
def page2():
    return render_template("page2.html")


@app.route("/Autocomplete.html")
def autocomplete():
    return render_template("Autocomplete.html")


@app.route("/tablesorter.html")
def tablesorter():
    return render_template("tablesorter.html")


@app.route("/style-demo.html")
def style_demo():
    return render_template("style-demo.html")


# Serve JS/CSS/images from the project root (mirrors the original layout
# where jquery-latest.js etc. lived next to the PHP files).
@app.route("/<path:filename>")
def root_static(filename):
    return send_from_directory("static", filename)


# ----------------------------------------------------------------------------
# back.php  ->  /back
# Scrapes Wikipedia for a city and returns its monthly high+low temperatures
# as a JSON array. Converts F -> C using *0.27777 (bug-for-bug port — the
# correct factor is 0.5556, but the original PHP uses 0.27777 here).
# ----------------------------------------------------------------------------

@app.route("/back", methods=["POST", "GET"])
def back():
    cityname = request.values.get("cityname", "")
    stack = []
    data = file_get_contents("http://en.wikipedia.org/wiki/" + cityname)
    finalend = len(data)

    start = mb_strpos(data, '<span class="plainlinks nourlexpansion">')
    if start != -1:
        semi = mb_substr(data, start, finalend - start)
        en = mb_strpos(semi, "><span")
        completedata = mb_substr(data, start, en)
        start2 = mb_strpos(completedata, "href=")
        semi = mb_substr(completedata, start2 + 5, len(completedata) - start2 - 5)
        completedata = mb_substr(semi, 1, len(semi) - 2)
        # array_push($stack, $completedata) is commented out in the PHP — keep it that way.

    # --- Average high ---
    finalend = len(data)
    start = mb_strpos(data, "Average high")
    test = mb_strpos(data, "Average high \u00b0F")  # °F
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass  # leave as-is
                else:
                    try:
                        semi = str((float(semi) - 32) * 0.27777)
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    # --- Average low ---
    finalend = len(data)
    start = mb_strpos(data, "Average low")
    test = mb_strpos(data, "Average low \u00b0F")
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass
                else:
                    try:
                        semi = str((float(semi) - 32) * 0.27777)
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    return json.dumps(stack)




@app.route("/ll", methods=["POST", "GET"])
def ll():
    stack = []
    data = file_get_contents("http://en.wikipedia.org/wiki/Jaipur")
    finalend = len(data)

    start = mb_strpos(data, '<span class="plainlinks nourlexpansion">')
    if start != -1:
        semi = mb_substr(data, start, finalend - start)
        en = mb_strpos(semi, "><span")
        completedata = mb_substr(data, start, en)
        start2 = mb_strpos(completedata, "href=")
        semi = mb_substr(completedata, start2 + 5, len(completedata) - start2 - 5)
        completedata = mb_substr(semi, 1, len(semi) - 2)

    # --- Average high ---
    finalend = len(data)
    start = mb_strpos(data, "Average high")
    test = mb_strpos(data, "Average high</abbr> \u00b0F")
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass
                else:
                    try:
                        semi = str(round((float(semi) - 32) * 0.55555, 2))
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    # --- Average low ---
    finalend = len(data)
    start = mb_strpos(data, "Average low")
    test = mb_strpos(data, "Average low</abbr> \u00b0F")
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass
                else:
                    try:
                        semi = str(round((float(semi) - 32) * 0.5555, 2))
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    return json.dumps(stack)




@app.route("/submit", methods=["POST", "GET"])
def submit():
    url = request.values.get("cityname", "")
    html = file_get_contents(url)
    return html




@app.route("/submit1", methods=["POST", "GET"])
def submit1():
    cityname = request.values.get("cityname", "")
    stack = []
    data = file_get_contents("http://en.wikipedia.org/wiki/" + cityname)
    finalend = len(data)

    start = mb_strpos(data, '<span class="plainlinks nourlexpansion">')
    if start != -1:
        semi = mb_substr(data, start, finalend - start)
        en = mb_strpos(semi, "><span")
        completedata = mb_substr(data, start, en)
        start2 = mb_strpos(completedata, "href=")
        semi = mb_substr(completedata, start2 + 5, len(completedata) - start2 - 5)
        completedata = mb_substr(semi, 1, len(semi) - 2)

    # --- Average high ---
    finalend = len(data)
    start = mb_strpos(data, "Average high")
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        formatvalue = mb_substr(semi1, 0, start2)
        test = mb_strpos(formatvalue, "\u00b0C)")  # if °C) is present in the header, values are already in C
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass
                else:
                    try:
                        semi = str(round((float(semi) - 32) * 0.55555, 2))
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    # --- Average low ---
    finalend = len(data)
    start = mb_strpos(data, "Average low")
    if start != -1:
        semi1 = mb_substr(data, start, finalend - start)
        start2 = mb_strpos(semi1, "</th>")
        end2 = mb_strpos(semi1, "</tr>")
        semi2 = mb_substr(semi1, start2 + 5, end2 - start2 - 5)
        formatvalue = mb_substr(semi1, 0, start2)
        test = mb_strpos(formatvalue, "\u00b0C)")
        parts = mb_split("</td>", semi2)
        i = 0
        while i < len(parts):
            ss = parts[i]
            # temp replace — the PHP also tries to normalize "?" to "-"; keep that.
            ss = ss.replace("?", "-")
            semi = mb_split(">", ss)
            if len(semi) > 1:
                semi = semi[1]
                semi = mb_split("<", semi)
                semi = semi[0]
                if test == -1:
                    pass
                else:
                    try:
                        semi = str(round((float(semi) - 32) * 0.5555, 2))
                    except ValueError:
                        pass
                stack.append(semi)
            i += 1
            if i == 13:
                break

    return json.dumps(stack)




@app.route("/finder/surrogate/test.php", methods=["POST", "GET"])
@app.route("/test", methods=["POST", "GET"])
def test_stub():
    # Read the inputs so callers that debug the endpoint can see them.
    _ = {
        "latitude":  request.values.get("latitude"),
        "longitude": request.values.get("longitude"),
        "altitude":  request.values.get("altitude"),
        "latrange":  request.values.get("latrange"),
        "altrange":  request.values.get("altrange"),
    }
    return jsonify([])


# Also mount the other PHP-compatible paths so the frontend's hardcoded URLs
# (which end in .php) keep working without having to edit the templates.
app.add_url_rule("/back.php",    view_func=back,     methods=["POST", "GET"])
app.add_url_rule("/ll.php",      view_func=ll,       methods=["POST", "GET"])
app.add_url_rule("/submit.php",  view_func=submit,   methods=["POST", "GET"])
app.add_url_rule("/submit1.php", view_func=submit1,  methods=["POST", "GET"])


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=8080, debug=True)
