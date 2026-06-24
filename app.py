import json
import urllib.parse
import urllib.request
import urllib.error
import logging
from urllib.parse import urlparse
from flask import Flask, request, render_template_string, Response, abort

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https://*.pinimg.com; style-src 'self' 'unsafe-inline';"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


def search(q, b=""):
    if len(q) > 100:
        logging.warning("Input validation failed: payload size limit exceeded.")
        return [], ""

    opts = {"query": q, "scope": "pins", "bookmarks": [b] if b else []}
    src = f"/search/pins/?q={urllib.parse.quote(q)}"
    url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url={urllib.parse.quote(src)}&data={urllib.parse.quote(json.dumps({'options': opts}))}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))["resource_response"]
            return [
                i["images"]["orig"]["url"]
                for i in res.get("data", {}).get("results", [])
                if "images" in i
            ], res.get("bookmark", "")

    except urllib.error.URLError as e:
        logging.error(f"Network error during external request: {e}")
        return [], ""
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response: {e}")
        return [], ""
    except Exception as e:
        logging.error(f"Unexpected error in search: {e}")
        return [], ""


T = """<head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{background:#000;color:#fff;font-family:sans-serif;text-align:center;margin:0}
.g{column-count:4;gap:1em;padding:0 1em} @media(max-width:800px){.g{column-count:2}}
</style></head><body>
<h2 style="margin:1em 0 0"><a href="/" style="color:#fff;text-decoration:none">kipoboard</a></h2>
<form style="padding:1em"><input name="q" value="{{q}}" autofocus><input type="submit" value="Search"></form>
<div class="g">
{% for i in imgs %}<a href="/proxy?u={{i|urlencode}}"><img src="/proxy?u={{i|urlencode}}" style="width:100%;margin-bottom:1em" loading="lazy"></a>{% endfor %}
</div>{% if n %}<a href="/?q={{q|urlencode}}&b={{n|urlencode}}" style="color:#fff;display:block;padding:2em">Next</a>{% endif %}</body>"""


@app.route("/")
def home():
    q = request.args.get("q", "")[:100]
    b = request.args.get("b", "")
    imgs, n = search(q, b) if q else ([], "")
    return render_template_string(T, q=q, imgs=imgs, n=n)


@app.route("/proxy")
def proxy():
    u = request.args.get("u", "")

    parsed_url = urlparse(u)
    if parsed_url.scheme != "https" or not parsed_url.netloc.endswith("i.pinimg.com"):
        logging.warning(f"SSRF attempt blocked for URL: {u}")
        abort(403)

    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:

            content_type = r.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                logging.warning(f"Blocked non-image content type: {content_type}")
                abort(415)

            max_size = 10 * 1024 * 1024
            content_length = r.headers.get("Content-Length")
            if content_length and int(content_length) > max_size:
                logging.warning(f"Payload too large: {content_length} bytes")
                abort(413)

            data = r.read(max_size + 1)
            if len(data) > max_size:
                logging.warning("Stream exceeded max size during read.")
                abort(413)

            return Response(data, content_type=content_type)

    except urllib.error.URLError as e:
        logging.error(f"Proxy fetch failed for {u}: {e}")
        abort(502)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
