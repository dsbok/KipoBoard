import json, urllib.parse, urllib.request
from flask import Flask, request, render_template_string, Response

app = Flask(__name__)


def search(q, b=""):
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
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=10
        ) as r:
            res = json.loads(r.read())["resource_response"]
            return [
                i["images"]["orig"]["url"]
                for i in res.get("data", {}).get("results", [])
                if "images" in i
            ], res.get("bookmark", "")
    except:
        return [], ""


T = """<head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{background:#000;color:#fff;font-family:sans-serif;text-align:center;margin:0}
.g{column-count:4;gap:1em;padding:0 1em} @media(max-width:800px){.g{column-count:2}}
</style></head><body>
<h2 style="margin:1em 0 0"><a href="/" style="color:#fff;text-decoration:none">KipoBoard</a></h2>
<form style="padding:1em"><input name="q" value="{{q}}" autofocus><input type="submit" value="Search"></form>
<div class="g">
{% for i in imgs %}<a href="/proxy?u={{i|urlencode}}"><img src="/proxy?u={{i|urlencode}}" style="width:100%;margin-bottom:1em" loading="lazy"></a>{% endfor %}
</div>{% if n %}<a href="/?q={{q|urlencode}}&b={{n|urlencode}}" style="color:#fff;display:block;padding:2em">Next →</a>{% endif %}</body>"""


@app.route("/")
def home():
    q, b = request.args.get("q", ""), request.args.get("b", "")
    imgs, n = search(q, b) if q else ([], "")
    return render_template_string(T, q=q, imgs=imgs, n=n)


@app.route("/proxy")
def proxy():
    u = request.args.get("u", "")
    if not u.startswith("https://i.pinimg.com/"):
        return "Forbidden", 403
    return Response(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        ).read(),
        content_type="image/jpeg",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
