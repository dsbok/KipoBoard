import json
import logging
import urllib.parse
from contextlib import asynccontextmanager
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import DictLoader, Environment
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kipoboard")

ALLOWED_DOMAINS = {"pinimg.com", "i.pinimg.com", "pinterest.com"}
PINTEREST_BASE_URL = "https://www.pinterest.com/resource/BaseSearchResource/get/"

http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await http_client.aclose()


app = FastAPI(title="KipoBoard Proxy", lifespan=lifespan)


class SearchResult(BaseModel):
    images: List[str]
    bookmark: str
    csrftoken: Optional[str] = None


template_loader = DictLoader(
    {
        "base.html": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>{{ title }}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {
                color-scheme: light dark;
                font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            }
            body {
                margin: 0;
                padding: 1rem;
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            header, footer, main {
                width: 100%;
                max-width: 1400px;
                text-align: center;
            }
            a { color: inherit; text-decoration: none; }
            hr { border: 0; border-top: 1px solid var(--Field-border, #888); margin: 1.5rem auto; width: 100%; opacity: 0.3; }
            h1 { margin-bottom: 0.2rem; }
            
            form { margin: 1rem 0; }
            input[type="text"], input[type="submit"] {
                padding: 0.6rem 1rem;
                font-size: 1rem;
                border-radius: 6px;
                border: 1px solid #88888888;
            }
            input[type="text"] { width: 300px; max-width: 60vw; }
            input[type="submit"] { cursor: pointer; font-weight: bold; }
            
            .masonry {
                column-count: 1;
                column-gap: 1rem;
                padding: 1rem 0;
            }
            @media (min-width: 600px) { .masonry { column-count: 2; } }
            @media (min-width: 900px) { .masonry { column-count: 3; } }
            @media (min-width: 1200px) { .masonry { column-count: 4; } }
            @media (min-width: 1600px) { .masonry { column-count: 5; } }
            
            .masonry-item {
                break-inside: avoid;
                margin-bottom: 1rem;
                border-radius: 8px;
                overflow: hidden;
                display: block;
                transition: opacity 0.2s;
            }
            .masonry-item:hover { opacity: 0.85; }
            .masonry-item img {
                width: 100%;
                display: block;
                height: auto;
                background-color: #88888822;
            }
            
            .indicator { margin: 2rem 0; font-style: italic; opacity: 0.6; }
        </style>
    </head>
    <body>
        <header>
            <h1>KipoBoard</h1>
            <p style="opacity: 0.8; margin-top: 0;">Minimal Pinterest proxy</p>
        </header>
        
        <main>
            {% block content %}{% endblock %}
        </main>
        
        <footer>
            <hr>
            <p><small><a href="https://github.com/dsbok/kipoboard/" target="_blank">View Source</a></small></p>
        </footer>
    </body>
    </html>
    """,
        "home.html": """
    {% extends "base.html" %}
    {% block content %}
    <div style="margin-top: 10vh;">
        <form method="get" action="/search" autocomplete="off">
            <input type="text" name="q" required placeholder="Search images..." autofocus>
            <input type="submit" value="Search">
        </form>
    </div>
    {% endblock %}
    """,
        "search.html": """
    {% extends "base.html" %}
    {% block content %}
    <div>
        <form method="get" action="/search" autocomplete="off">
            <input type="text" name="q" value="{{ query }}" required>
            <input type="submit" value="Search">
        </form>
    </div>
    <hr>
    
    <div id="image-grid" class="masonry">
        {% if results and results.images %}
            {% for image in results.images %}
                <a class="masonry-item" href="/image_proxy?url={{ image | urlencode }}" target="_blank">
                    <img src="/image_proxy?url={{ image | urlencode }}" loading="lazy" alt="Pin">
                </a>
            {% endfor %}
        {% else %}
            <p class="indicator">No results found.</p>
        {% endif %}
    </div>

    {% if results and results.bookmark %}
        <div id="sentinel" class="indicator">Loading more images...</div>
    {% endif %}

    <script>
        let currentQuery = "{{ query }}";
        let currentBookmark = "{{ results.bookmark if results else '' }}";
        let currentCsrf = "{{ results.csrftoken if results else '' }}";
        let isLoading = false;
        let hasMore = !!currentBookmark;

        const sentinel = document.getElementById('sentinel');
        
        if (sentinel) {
            const observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting && !isLoading && hasMore) {
                    loadMore();
                }
            }, { rootMargin: "800px" });
            
            observer.observe(sentinel);
        }

        async function loadMore() {
            isLoading = true;

            try {
                const url = `/api?q=${encodeURIComponent(currentQuery)}&bookmark=${encodeURIComponent(currentBookmark)}&csrftoken=${encodeURIComponent(currentCsrf)}`;
                const res = await fetch(url);
                if (!res.ok) throw new Error('Network response was not ok');
                
                const data = await res.json();

                if (data.images && data.images.length > 0) {
                    const grid = document.getElementById('image-grid');
                    data.images.forEach(imgUrl => {
                        const a = document.createElement('a');
                        a.className = 'masonry-item';
                        
                        const proxyUrl = `/image_proxy?url=${encodeURIComponent(imgUrl)}`;
                        a.href = proxyUrl;
                        a.target = '_blank';
                        
                        const img = document.createElement('img');
                        img.src = proxyUrl;
                        img.loading = 'lazy';
                        img.alt = 'Pin';
                        
                        a.appendChild(img);
                        grid.appendChild(a);
                    });
                }

                currentBookmark = data.bookmark || "";
                currentCsrf = data.csrftoken || "";
                hasMore = !!currentBookmark;

                if (!hasMore && sentinel) {
                    sentinel.textContent = "No more results.";
                }

            } catch (e) {
                console.error("Failed to load more images:", e);
                hasMore = false; 
                if (sentinel) sentinel.textContent = "Error loading more images.";
            } finally {
                isLoading = false;
            }
        }
    </script>
    {% endblock %}
    """,
    }
)
jinja_env = Environment(loader=template_loader, autoescape=True)


def is_allowed_domain(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
        host = parsed.hostname
        if not host:
            return False
        return any(
            host == domain or host.endswith(f".{domain}") for domain in ALLOWED_DOMAINS
        )
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

    try:
        resp = await http_client.get(search_url, headers=headers)
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


@app.get("/", response_class=HTMLResponse)
async def home_handler():
    template = jinja_env.get_template("home.html")
    return template.render(title="KipoBoard")


@app.get("/search", response_class=HTMLResponse)
async def search_handler(
    q: str = Query(..., min_length=1, max_length=64),
    bookmark: str = "",
    csrftoken: str = "",
):
    try:
        result = await perform_search(q, bookmark, csrftoken)
    except Exception as e:
        logger.error(f"Search error: {e}")
        result = None

    template = jinja_env.get_template("search.html")
    return template.render(title=f"{q} - KipoBoard", query=q, results=result)


@app.get("/api", response_model=SearchResult)
async def api_handler(
    q: str = Query(..., min_length=1), bookmark: str = "", csrftoken: str = ""
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
            async with client.stream(
                "GET", url, headers={"User-Agent": "Mozilla/5.0"}
            ) as response:
                if response.status_code != 200:
                    yield b""
                    return
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk

    return StreamingResponse(stream_image(), media_type="image/jpeg")


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting KipoBoard on port 5003...")
    uvicorn.run("main:app", host="0.0.0.0", port=5003, log_level="info", reload=True)
