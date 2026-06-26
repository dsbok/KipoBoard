import json
import urllib.parse
import urllib.request
import html
from http.server import HTTPServer, BaseHTTPRequestHandler

def search(q, b=""):
    opts = {"query": q, "scope": "pins", "bookmarks": [b] if b else []}
    src = f"/search/pins/?q={urllib.parse.quote(q)}"
    url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url={urllib.parse.quote(src)}&data={urllib.parse.quote(json.dumps({'options': opts}))}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "X-Pinterest-AppState": "active",
            "X-Pinterest-PWS-Handler": "www/search/[scope].js"
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))["resource_response"]
            return [
                i["images"]["orig"]["url"]
                for i in res.get("data", {}).get("results", [])
                if "images" in i
            ], res.get("bookmark", "")
    except Exception:
        return [], ""

T = """<head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{background:#000;color:#fff;font-family:sans-serif;text-align:center;margin:0}
.g{column-count:4;gap:1em;padding:0 1em} @media(max-width:800px){.g{column-count:2}}
</style></head><body>
<h2 style="margin:1em 0 0"><a href="/" style="color:#fff;text-decoration:none">kipoboard</a></h2>
<form style="padding:1em"><input name="q" value="{{q}}" autofocus><input type="submit" value="Search"></form>
<div class="g">
{{imgs}}
</div>{{next_btn}}</body>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parts = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parts.query)
        if parts.path == "/":
            q = params.get("q", [""])[0][:100]
            b = params.get("b", [""])[0]
            imgs, n = search(q, b) if q else ([], "")
            img_html = "".join(f'<a href="/proxy?u={urllib.parse.quote(i)}"><img src="/proxy?u={urllib.parse.quote(i)}" style="width:100%;margin-bottom:1em" loading="lazy"></a>' for i in imgs)
            next_html = f'<a href="/?q={urllib.parse.quote(q)}&b={urllib.parse.quote(n)}" style="color:#fff;display:block;padding:2em">Next</a>' if n else ''
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(T.replace("{{q}}", html.escape(q)).replace("{{imgs}}", img_html).replace("{{next_btn}}", next_html).encode("utf-8"))
        elif parts.path == "/proxy":
            u = params.get("u", [""])[0]
            if "i.pinimg.com" not in u:
                self.send_error(403)
                return
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    self.send_response(200)
                    self.send_header("Content-Type", r.headers.get("Content-Type", "image/jpeg"))
                    self.end_headers()
                    self.wfile.write(r.read())
            except Exception:
                self.send_error(502)
        else:
            self.send_error(404)

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 5005), Handler).serve_forever()
