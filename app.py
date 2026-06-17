import json
import urllib.parse
import urllib.request
import sys


def search_pinterest(q, b="", c=""):
    opts = {"query": q, "scope": "pins"}
    if b:
        opts["bookmarks"] = [b]
    src = f"/search/pins/?q={urllib.parse.quote(q)}"
    url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url={urllib.parse.quote(src)}&data={urllib.parse.quote(json.dumps({'options': opts}))}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "X-Pinterest-AppState": "active",
            "X-Pinterest-PWS-Handler": "www/search/[scope].js",
        },
    )
    if c:
        req.add_header("X-CSRFToken", c)
        req.add_header("Cookie", f"csrftoken={c}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            res = data.get("resource_response", {})
            imgs = [
                i.get("images", {}).get("orig", {}).get("url")
                for i in res.get("data", {}).get("results", [])
                if i.get("images")
            ]
            nb = (
                res.get("bookmark")
                or data.get("resource", {})
                .get("options", {})
                .get("bookmarks", [None])[0]
            )
            nc = next(
                (
                    v.split("=")[1].split(";")[0]
                    for k, v in r.getheaders()
                    if k.lower() == "set-cookie" and "csrftoken" in v
                ),
                c,
            )
            return {"images": imgs, "bookmark": nb, "csrftoken": nc}
    except Exception as e:
        if "test" in sys.argv:
            print(f"Error: {e}")
        return {"images": [], "bookmark": "", "csrftoken": c}


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "test":
    res = search_pinterest("nature")
    print(f"Found {len(res['images'])} images")
    sys.exit(0 if len(res["images"]) > 0 else 1)

from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

HTML_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>KipoBoard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #000; color: #fff; scroll-behavior: smooth; }
        form { margin: 1.5rem 0; text-align: center; }
        input[type="text"] { width: 300px; max-width: 80vw; padding: 4px; }
        .grid { column-count: 4; column-gap: 1rem; padding: 1rem 0; }
        @media (max-width: 800px) { .grid { column-count: 2; } }
        .item { display: inline-block; width: 100%; margin-bottom: 1rem; border-radius: 4px; overflow: hidden; }
        .item img { width: 100%; display: block; background: #111; }
        .nav { text-align: center; padding: 2rem 0; }
        .nav a { color: #fff; text-decoration: none; padding: 10px 20px; border: 1px solid #fff; border-radius: 4px; }
        #btt { position: fixed; bottom: 20px; right: 20px; padding: 10px; background: #333; color: #fff; border: none; border-radius: 50%; cursor: pointer; }
    </style>
</head>
<body>
    <h2 style="text-align:center;"><a href="/" style="color:#fff; text-decoration:none;">KipoBoard</a></h2>
    <form><input type="text" name="q" value="{{ Q }}" required placeholder="Search..." autofocus> <input type="submit" value="Search"></form>
    <div id="grid" class="grid">{{ HTML|safe }}</div>
    {% if Next %}
    <div class="nav"><a href="{{ Next }}">Next Page →</a></div>
    {% endif %}
    <p style="text-align:center; opacity:0.5;">{{ Msg }}</p>
    <button id="btt" onclick="window.scrollTo(0,0)">↑</button>
</body>
</html>"""


@app.route("/")
def home():
    q = request.args.get("q", "")
    b = request.args.get("b", "")
    c = request.args.get("c", "")
    res = search_pinterest(q, b, c) if q else {"images": [], "bookmark": "", "csrftoken": ""}
    html = "".join(
        f'<a class="item" href="/proxy?u={urllib.parse.quote(img)}" target="_blank"><img src="/proxy?u={urllib.parse.quote(img)}" loading="lazy"></a>'
        for img in res["images"]
    )
    next_url = f"/?q={urllib.parse.quote(q)}&b={urllib.parse.quote(res['bookmark'])}&c={urllib.parse.quote(res['csrftoken'])}" if res["bookmark"] else ""
    return render_template_string(
        HTML_TMPL,
        Q=q,
        HTML=html,
        Next=next_url,
        Msg="No results" if q and not res["images"] else "",
    )


@app.route("/proxy")
def proxy():
    u = request.args.get("u", "")
    if not u.startswith("https://i.pinimg.com/"):
        return "Forbidden", 403
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            headers = {"Cache-Control": "public, max-age=86400"}
            if request.args.get("dl") == "1":
                headers["Content-Disposition"] = (
                    f'attachment; filename="{u.split("/")[-1]}"'
                )
            return Response(
                r.read(), content_type=r.headers.get("Content-Type"), headers=headers
            )
    except:
        return "Error", 502


if __name__ == "__main__":
    app.run(port=5005)
