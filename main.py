import json
import logging
import urllib.parse
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import DictLoader, Environment
from pydantic import BaseModel

# ==========================================
# Configuration & Setup
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dinterest")

app = FastAPI(title="Dinterest Proxy")

ALLOWED_DOMAINS = {"pinimg.com", "i.pinimg.com", "pinterest.com"}
PINTEREST_BASE_URL = "https://www.pinterest.com/resource/BaseSearchResource/get/"

# ==========================================
# Models
# ==========================================
class SearchResult(BaseModel):
    images: List[str]
    bookmark: str
    csrftoken: Optional[str] = None

# ==========================================
# Templating (Jinja2 In-Memory)
# ==========================================
template_loader = DictLoader({
    "base.html": """
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ title }}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                background-color: #121212;
                color: #e0e0e0;
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
            }
            header, footer {
                text-align: center;
                max-width: 800px;
                margin: 0 auto;
            }
            a { color: #bb86fc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            hr { border: 0; border-top: 1px solid #333; margin: 20px auto; width: 80%; }
            h1 { margin-bottom: 5px; }
            
            /* Form Styling */
            input[type="text"] {
                background-color: #2c2c2c;
                color: #ffffff;
                border: 1px solid #444;
                padding: 10px;
                border-radius: 4px;
                font-size: 16px;
                width: 300px;
                max-width: 100%;
            }
            input[type="submit"] {
                background-color: #3700b3;
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 16px;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            input[type="submit"]:hover {
                background-color: #6200ea;
            }
            
            /* Responsive Grid Styling for 4-5 images per row */
            .grid-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                gap: 15px;
                padding: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }
            
            .grid-item {
                display: block;
                overflow: hidden;
                border: 1px solid #333;
                border-radius: 8px;
                background-color: #1e1e1e;
                transition: transform 0.2s, border-color 0.2s;
            }
            
            .grid-item:hover {
                transform: scale(1.02);
                border-color: #bb86fc;
            }
            
            .grid-item img {
                width: 100%;
                height: 250px;
                object-fit: cover; /* Keeps images nicely cropped into standard dimensions */
                display: block;
            }
            
            .loading {
                display: none;
                color: #888;
                font-style: italic;
                margin: 20px 0;
                text-align: center;
            }
            .no-results {
                text-align: center;
                grid-column: 1 / -1;
                color: #888;
            }
        </style>
    </head>
    <body>
        <header>
            <h1>dinterest</h1>
            <p>Simple Pinterest image search proxy</p>
            <hr>
        </header>
        
        {% block content %}{% endblock %}
        
        <footer>
            <hr>
            <p><a href="https://github.com/dsbok/dinterest/" target="_blank">Source</a></p>
        </footer>
    </body>
    </html>
    """,
    "home.html": """
    {% extends "base.html" %}
    {% block content %}
    <div style="text-align: center; margin-top: 50px;">
        <form method="get" action="/search" autocomplete="off">
            <p>
                <input type="text" name="q" required placeholder="Search images...">
                <input type="submit" value="Search">
            </p>
        </form>
    </div>
    {% endblock %}
    """,
    "search.html": """
    {% extends "base.html" %}
    {% block content %}
    <div style="text-align: center;">
        <form method="get" action="/search" autocomplete="off">
            <input type="text" name="q" value="{{ query }}" required>
            <input type="submit" value="Search">
        </form>
    </div>
    <hr>
    
    <div id="image-grid" class="grid-container">
        {% if results and results.images %}
            {% for image in results.images %}
                <a class="grid-item" href="/image_proxy?url={{ image | urlencode }}" target="_blank">
                    <img src="/image_proxy?url={{ image | urlencode }}" loading="lazy">
                </a>
            {% endfor %}
        {% else %}
            <p class="no-results">No results found.</p>
        {% endif %}
    </div>

    <div id="loading" class="loading">Loading more images...</div>

    <!-- Infinite Scroll Logic -->
    <script>
        let currentQuery = "{{ query }}";
        let currentBookmark = "{{ results.bookmark if results else '' }}";
        let currentCsrf = "{{ results.csrftoken if results else '' }}";
        let isLoading = false;
        let hasMore = !!currentBookmark;

        window.addEventListener('scroll', () => {
            if (isLoading || !hasMore) return;
            
            // Trigger load when within 800px of the bottom
            if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 800) {
                loadMore();
            }
        });

        async function loadMore() {
            isLoading = true;
            document.getElementById('loading').style.display = 'block';

            try {
                const url = `/api?q=${encodeURIComponent(currentQuery)}&bookmark=${encodeURIComponent(currentBookmark)}&csrftoken=${encodeURIComponent(currentCsrf)}`;
                const res = await fetch(url);
                if (!res.ok) throw new Error('Network response was not ok');
                
                const data = await res.json();

                if (data.images && data.images.length > 0) {
                    const grid = document.getElementById('image-grid');
                    data.images.forEach(imgUrl => {
                        const a = document.createElement('a');
                        a.className = 'grid-item';
                        
                        const proxyUrl = `/image_proxy?url=${encodeURIComponent(imgUrl)}`;
                        a.href = proxyUrl;
                        a.target = '_blank';
                        
                        const img = document.createElement('img');
                        img.src = proxyUrl;
                        img.loading = 'lazy';
                        
                        a.appendChild(img);
                        grid.appendChild(a);
                    });
                }

                currentBookmark = data.bookmark || "";
                currentCsrf = data.csrftoken || "";
                hasMore = !!currentBookmark;

            } catch (e) {
                console.error("Failed to load more images:", e);
                hasMore = false; 
            } finally {
                isLoading = false;
                document.getElementById('loading').style.display = 'none';
            }
        }
    </script>
    {% endblock %}
    """
})
jinja_env = Environment(loader=template_loader, autoescape=True)

# ==========================================
# Core Logic
# ==========================================
def is_allowed_domain(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
        host = parsed.hostname
        if not host:
            return False
        return any(host == domain or host.endswith(f".{domain}") for domain in ALLOWED_DOMAINS)
    except Exception:
        return False

async def perform_search(
    query: str, bookmark: str = "", csrftoken: str = ""
) -> SearchResult:
    options = {"query": query, "scope": "pins"}
    if bookmark:
        options["bookmarks"] = [bookmark]

    payload = {"options": options, "context": {}}
    json_payload = json.dumps(payload)

    search_url = (
        f"{PINTEREST_BASE_URL}?source_url=/search/pins/?q="
        f"{urllib.parse.quote(query)}&data={urllib.parse.quote(json_payload)}"
    )

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

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(search_url, headers=headers)
            resp.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Request failed: {e}")
            raise HTTPException(status_code=500, detail="Search request failed")
        
        new_csrftoken = resp.cookies.get("csrftoken", csrftoken)
        raw_data = resp.json()

    result = SearchResult(images=[], bookmark="", csrftoken=new_csrftoken)

    resource_response = raw_data.get("resource_response") or {}
    data = resource_response.get("data") or {}
    results_list = data.get("results") or []

    for item in results_list:
        if not isinstance(item, dict):
            continue
        image_url = item.get("images", {}).get("orig", {}).get("url")
        if image_url:
            result.images.append(image_url)

    resource = raw_data.get("resource") or {}
    resource_options = resource.get("options") or {}
    bookmarks = resource_options.get("bookmarks") or []
    
    if bookmarks and isinstance(bookmarks[0], str):
        result.bookmark = bookmarks[0]
    elif resource_response.get("bookmark"):
        result.bookmark = resource_response.get("bookmark")

    return result

# ==========================================
# Routes
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def home_handler():
    template = jinja_env.get_template("home.html")
    return template.render(title="dinterest")


@app.get("/search", response_class=HTMLResponse)
async def search_handler(
    q: str = Query(..., min_length=1, max_length=64),
    bookmark: str = "",
    csrftoken: str = ""
):
    try:
        result = await perform_search(q, bookmark, csrftoken)
    except Exception as e:
        logger.error(f"Search error: {e}")
        result = None

    template = jinja_env.get_template("search.html")
    return template.render(
        title=f"{q} - dinterest",
        query=q,
        results=result
    )


@app.get("/api", response_model=SearchResult)
async def api_handler(
    q: str = Query(..., min_length=1),
    bookmark: str = "",
    csrftoken: str = ""
):
    try:
        return await perform_search(q, bookmark, csrftoken)
    except Exception:
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/image_proxy")
async def image_proxy_handler(url: str = Query(...)):
    if not is_allowed_domain(url):
        raise HTTPException(status_code=403, detail="Forbidden domain")

    async def stream_image():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                if response.status_code != 200:
                    yield b""
                    return
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(stream_image(), media_type="image/jpeg")

# ==========================================
# Entry Point
# ==========================================
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Dinterest on port 5003...")
    uvicorn.run(app, host="0.0.0.0", port=5003, log_level="info")
