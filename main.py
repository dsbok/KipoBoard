import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 5003
ALLOWED_DOMAINS = {"pinimg.com", "i.pinimg.com", "pinterest.com"}

@dataclass
class SearchResult:
    images: list
    bookmark: str
    csrftoken: str = ""

def is_allowed_domain(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).hostname
        return bool(host and any(host == d or host.endswith(f".{d}") for d in ALLOWED_DOMAINS))
    except Exception:
        return False

def perform_search(query: str, bookmark: str = "", csrftoken: str = "") -> SearchResult:
    options = {"query": query, "scope": "pins"}
    if bookmark:
        options["bookmarks"] = [bookmark]

    payload = urllib.parse.quote(json.dumps({"options": options, "context": {}}))
    query_quoted = urllib.parse.quote(query)
    url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q={query_quoted}&data={payload}"

    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if csrftoken:
        headers["X-CSRFToken"] = csrftoken
        headers["Cookie"] = f"csrftoken={csrftoken}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
        cookie_header = dict(resp.getheaders()).get("Set-Cookie", "")

    new_csrf = csrftoken
    if match := re.search(r"csrftoken=([^;]+)", cookie_header):
        new_csrf = match.group(1)

    images = []
    res_resp = resp_data.get("resource_response", {})
    for item in res_resp.get("data", {}).get("results", []):
        if isinstance(item, dict) and (img_url := item.get("images", {}).get("orig", {}).get("url")):
            images.append(img_url)

    bookmarks = resp_data.get("resource", {}).get("options", {}).get("bookmarks", [])
    new_bookmark = bookmarks[0] if bookmarks else res_resp.get("bookmark", "")

    return SearchResult(images=images, bookmark=new_bookmark, csrftoken=new_csrf)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>KipoBoard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {{ color-scheme: dark; }}
        body {{ font-family: system-ui, sans-serif; margin: 0; padding: 1rem; text-align: center; background-color: #000000; color: #FFFFFF; }}
        form {{ margin: 1.5rem 0; }}
        input {{ font-size: 1rem; }}
        input[type="text"] {{ width: 300px; max-width: 80vw; }}
        
        /* Flexbox Masonry layout */
        .masonry {{ display: flex; gap: 1rem; padding: 1rem 0; align-items: flex-start; }}
        .col {{ display: flex; flex-direction: column; gap: 1rem; flex: 1 1 0; min-width: 0; }}
        
        .item {{ display: block; width: 100%; }}
        .item img {{ width: 100%; border-radius: 8px; display: block; background-color: #111; min-height: 100px; object-fit: cover; }}
        a {{ color: inherit; text-decoration: none; }}
    </style>
</head>
<body>
    <h1><a href="https://github.com/dsbok/kipoboard">KipoBoard</a></h1>
    <form method="get" action="/search">
        <input type="text" name="q" value="{query}" required placeholder="Search images..." autofocus>
        <input type="submit" value="Search">
    </form>
    
    <div id="grid" class="masonry"></div>
    <div id="raw" style="display:none;">{images_html}</div>
    <div id="sentinel" style="margin: 2rem; opacity: 0.5;">{sentinel_text}</div>

    <script>
        let q = "{query}", bookmark = "{bookmark}", csrf = "{csrf}", loading = false;
        const s = document.getElementById('sentinel');
        const g = document.getElementById('grid');
        
        // Auto-calculate columns based on width, enforcing a minimum of 2 columns
        const targetColWidth = 200; 
        const nCols = Math.max(2, Math.floor(window.innerWidth / targetColWidth));
        
        const cols = [];
        for(let i=0; i<nCols; i++) {{
            let c = document.createElement('div');
            c.className = 'col';
            g.appendChild(c);
            cols.push(c);
        }}
        
        // Find the shortest column to append to, maintaining an even layout
        function getShortestColIndex() {{
            let shortestIdx = 0;
            let minHeight = cols[0].offsetHeight;
            for (let i = 1; i < nCols; i++) {{
                if (cols[i].offsetHeight < minHeight) {{
                    minHeight = cols[i].offsetHeight;
                    shortestIdx = i;
                }}
            }}
            return shortestIdx;
        }}
        
        let fallbackIdx = 0;
        function addItems(container) {{
            // We use a small delay between appending items to let the DOM calculate heights properly
            const items = Array.from(container.children);
            items.forEach(item => {{
                // Fallback to round-robin if heights aren't calculated yet (e.g. initial load before images fetch)
                let targetCol = cols[getShortestColIndex()];
                if (targetCol.offsetHeight === 0) {{
                    targetCol = cols[fallbackIdx % nCols];
                    fallbackIdx++;
                }}
                targetCol.appendChild(item);
            }});
        }}
        
        // Process initial load
        addItems(document.getElementById('raw'));
        
        if (s && bookmark) {{
            new IntersectionObserver(e => {{
                if (e[0].isIntersecting && !loading && bookmark) loadMore();
            }}, {{rootMargin: "800px"}}).observe(s);
        }}

        async function loadMore() {{
            loading = true;
            try {{
                const res = await fetch(`/api?q=${{encodeURIComponent(q)}}&bookmark=${{encodeURIComponent(bookmark)}}&csrftoken=${{encodeURIComponent(csrf)}}`);
                const data = await res.json();
                
                const temp = document.createElement('div');
                data.images.forEach(img => {{
                    const proxyUrl = `/image_proxy?url=${{encodeURIComponent(img)}}`;
                    temp.innerHTML += `<a class="item" href="${{proxyUrl}}" target="_blank"><img src="${{proxyUrl}}" loading="lazy"></a>`;
                }});
                
                addItems(temp);
                
                bookmark = data.bookmark;
                csrf = data.csrftoken;
                if (!bookmark) s.textContent = "No more results.";
            }} catch(e) {{
                s.textContent = "Error loading more.";
            }}
            loading = false;
        }}
    </script>
</body>
</html>
"""

class KipoBoardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, content, content_type="text/html"):
        try:
            self.send_response(status)
            self.send_header("Content-type", content_type)
            self.end_headers()
            if isinstance(content, str):
                content = content.encode("utf-8")
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        if path == "/":
            self.respond(200, HTML_TEMPLATE.format(query="", images_html="", sentinel_text="", bookmark="", csrf=""))
        
        elif path == "/search":
            q = params.get("q", "")
            if not q:
                return self.respond(400, "Missing query")
            
            try:
                res = perform_search(q)
                imgs = "".join(f'<a class="item" href="/image_proxy?url={urllib.parse.quote(img)}" target="_blank"><img src="/image_proxy?url={urllib.parse.quote(img)}" loading="lazy"></a>' for img in res.images)
                sentinel = "Loading..." if res.bookmark else ("No results." if not res.images else "")
                self.respond(200, HTML_TEMPLATE.format(query=q.replace('"', '&quot;'), images_html=imgs, sentinel_text=sentinel, bookmark=res.bookmark, csrf=res.csrftoken))
            except Exception:
                self.respond(500, "Search failed")

        elif path == "/api":
            q = params.get("q", "")
            if not q:
                return self.respond(400, "Missing query")
            try:
                res = perform_search(q, params.get("bookmark", ""), params.get("csrftoken", ""))
                self.respond(200, json.dumps({"images": res.images, "bookmark": res.bookmark, "csrftoken": res.csrftoken}), "application/json")
            except Exception:
                self.respond(500, '{"error": "Search failed"}', "application/json")

        elif path == "/image_proxy":
            url = params.get("url", "")
            if not is_allowed_domain(url):
                return self.respond(403, "Forbidden domain")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30.0) as img_resp:
                    self.send_response(200)
                    self.send_header("Content-type", img_resp.headers.get("Content-Type", "image/jpeg"))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    
                    try:
                        while chunk := img_resp.read(8192):
                            self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
            except Exception:
                self.respond(502, "Bad Gateway")
        else:
            self.respond(404, "Not Found")

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), KipoBoardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
