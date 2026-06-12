import json
import re
import urllib.parse
from flask import Flask, request, jsonify, render_template_string, Response
import requests

app = Flask(__name__)
session = requests.Session()

csrf_regex = re.compile(r"csrftoken=([^;]+)")

HTML_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
	<title>KipoBoard</title>
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<style>
		body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; text-align: center; background: #000; color: #fff; }
		a { color: #fff; text-decoration: none; }
		.masonry { display: flex; gap: 1rem; padding: 1rem 0; align-items: flex-start; }
		.col { display: flex; flex-direction: column; gap: 1rem; flex: 1 1 0; min-width: 0; }
		.item img { width: 100%; display: block; background: #111; min-height: 100px; object-fit: cover; border-radius: 4px; transition: opacity 0.2s ease; cursor: zoom-in; content-visibility: auto; }
		.item img:hover { opacity: 0.8; }
		
		.btn, input[type="submit"] { background: #000; border: 1px solid #333; color: #fff; padding: 10px 20px; border-radius: 4px; cursor: pointer; transition: all 0.2s ease; font-family: inherit; font-size: 14px; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; margin: 0; box-sizing: border-box; }
		.btn:hover, input[type="submit"]:hover { background: #fff; color: #000; border-color: #fff; }
		.btn.active { background: #fff; color: #000; border-color: #fff; }
		
		input[type="text"] { background: #000; border: 1px solid #333; color: #fff; padding: 10px 16px; border-radius: 4px; width: 300px; max-width: 100%; outline: none; font-family: inherit; font-size: 14px; transition: border-color 0.2s ease; box-sizing: border-box; }
		input[type="text"]:focus { border-color: #fff; }
		
		.header-container { display: flex; flex-direction: column; align-items: center; gap: 1.5rem; margin: 1rem 0 2rem 0; }
		.controls { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; }
		
		#lightbox { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; align-items: center; justify-content: center; flex-direction: column; cursor: zoom-out; backdrop-filter: blur(5px); }
		#lightbox img { max-width: 90vw; max-height: 80vh; object-fit: contain; border-radius: 4px; }
		#lightbox.active { display: flex; }
		
		.lightbox-actions { display: flex; gap: 0.5rem; margin-top: 1.5rem; flex-wrap: wrap; justify-content: center; }
		
		#btt { display: none; position: fixed; bottom: 20px; right: 20px; z-index: 999; }
	</style>
</head>
<body>
	<div class="header-container">
		<h2 style="margin: 0;"><a href="/">KipoBoard</a></h2>
		<form id="search-form" class="controls" style="margin: 0;">
			<input type="text" name="q" value="{{ Q }}" required placeholder="Search images..." autofocus> 
			<input type="submit" value="Search" class="btn">
			<button type="button" id="view-favs" class="btn">Favorites</button>
		</form>
	</div>
	
	<div id="grid" class="masonry"></div>
	<div id="raw" style="display:none;">{{ HTML|safe }}</div>
	<p id="s" style="opacity:0.5; margin:2rem;">{{ Msg }}</p>

	<div id="lightbox" onclick="if(event.target.id === 'lightbox' || event.target.id === 'lightbox-img') this.classList.remove('active')">
		<img id="lightbox-img" src="" data-raw-url="" decoding="async">
		<div class="lightbox-actions">
			<button id="lightbox-fav" class="btn">Favorite</button>
			<button id="lightbox-copy" class="btn">Copy Link</button>
			<a id="lightbox-dl" href="" class="btn">Download</a>
		</div>
	</div>

	<button id="btt" class="btn" onclick="window.scrollTo({top:0, behavior:'smooth'})">Top</button>

	<script>
		let q={{ Q|tojson }}, b={{ B|tojson }}, c={{ C|tojson }}, l=false, s=document.getElementById('s'), g=document.getElementById('grid');
		
		const cols = Array.from({length: Math.max(3, Math.floor(window.innerWidth/200))}, () => {
			let c = document.createElement('div'); c.className='col'; g.appendChild(c); return c;
		});

		function addItems(cnt) {
			Array.from(cnt.children).forEach(i => {
				cols.reduce((min, cur) => cur.offsetHeight < min.offsetHeight ? cur : min, cols[0]).appendChild(i);
			});
		}
		
		if (document.getElementById('raw').children.length > 0) {
			addItems(document.getElementById('raw'));
		}

		if(s && b) {
			new IntersectionObserver(e => {
				if(e[0].isIntersecting && !l && b) loadMore();
			}, {rootMargin: "800px"}).observe(s);
		}

		async function loadMore() {
			l = true;
			try {
				let d = await (await fetch('/api?q='+encodeURIComponent(q)+'&b='+encodeURIComponent(b)+'&c='+encodeURIComponent(c))).json();
				let tmp = document.createElement('div');
				d.images.forEach(i => {
					let p = '/proxy?u='+encodeURIComponent(i);
					tmp.innerHTML += '<a class="item" href="'+p+'" target="_blank"><img src="'+p+'" loading="lazy" decoding="async"></a>';
				});
				addItems(tmp);
				b=d.bookmark; c=d.csrftoken;
				if(!b) s.textContent="No more results.";
			} catch(e) {
				s.textContent="Error loading more.";
			}
			l = false;
		}

		g.addEventListener('click', e => {
			let item = e.target.closest('.item');
			if (item) {
				e.preventDefault(); 
				let url = item.getAttribute('href');
				document.getElementById('lightbox-img').src = item.href;
				document.getElementById('lightbox-img').setAttribute('data-raw-url', url);
				document.getElementById('lightbox-dl').href = url + '&dl=1';
				
				let favs = JSON.parse(localStorage.getItem('kipofavs') || '[]');
				let favBtn = document.getElementById('lightbox-fav');
				if (favs.includes(url)) {
					favBtn.textContent = "Favorited";
					favBtn.classList.add('active');
				} else {
					favBtn.textContent = "Favorite";
					favBtn.classList.remove('active');
				}
				document.getElementById('lightbox').classList.add('active');
			}
		});

		document.getElementById('lightbox-fav').addEventListener('click', (e) => {
			e.stopPropagation();
			let url = document.getElementById('lightbox-img').getAttribute('data-raw-url');
			let favs = JSON.parse(localStorage.getItem('kipofavs') || '[]');
			
			if (favs.includes(url)) {
				favs = favs.filter(u => u !== url);
				e.target.textContent = "Favorite";
				e.target.classList.remove('active');
			} else {
				favs.push(url);
				e.target.textContent = "Favorited";
				e.target.classList.add('active');
			}
			localStorage.setItem('kipofavs', JSON.stringify(favs));
		});

		document.getElementById('view-favs').addEventListener('click', (e) => {
			e.preventDefault();
			let favs = JSON.parse(localStorage.getItem('kipofavs') || '[]');
			
			document.querySelector('input[name="q"]').style.display = 'none';
			document.querySelector('input[type="submit"]').style.display = 'none';
			s.style.display = 'none';
			g.innerHTML = '';
			
			cols.length = 0; 
			Array.from({length: Math.max(3, Math.floor(window.innerWidth/200))}).forEach(() => {
				let colDiv = document.createElement('div'); 
				colDiv.className = 'col'; 
				g.appendChild(colDiv); 
				cols.push(colDiv);
			});

			if (favs.length === 0) {
				s.style.display = 'block';
				s.textContent = "No favorites saved.";
				return;
			}

			let tmp = document.createElement('div');
			favs.forEach(url => {
				tmp.innerHTML += '<a class="item" href="'+url+'" target="_blank"><img src="'+url+'" loading="lazy" decoding="async"></a>';
			});
			addItems(tmp);
		});

		document.getElementById('lightbox-copy').addEventListener('click', (e) => {
			e.stopPropagation();
			let rawPath = document.getElementById('lightbox-img').getAttribute('data-raw-url');
			let fullUrl = window.location.origin + rawPath;
			
			navigator.clipboard.writeText(fullUrl).then(() => {
				let btn = e.target;
				btn.textContent = "Copied";
				setTimeout(() => { btn.textContent = "Copy Link"; }, 2000);
			}).catch(err => {});
		});

		window.addEventListener('scroll', () => {
			document.getElementById('btt').style.display = window.scrollY > 800 ? 'block' : 'none';
		}, { passive: true });
	</script>
</body>
</html>"""


def search_pinterest(q, b="", c=""):
    opts = {"query": q, "scope": "pins"}
    if b:
        opts["bookmarks"] = [b]

    payload = json.dumps({"options": opts, "context": {}})
    target_url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q={urllib.parse.quote(q)}&data={urllib.parse.quote(payload)}"

    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    if c:
        headers["X-CSRFToken"] = c
        headers["Cookie"] = f"csrftoken={c}"

    try:
        res = session.get(target_url, headers=headers, timeout=15)
    except requests.RequestException:
        return {"images": [], "bookmark": "", "csrftoken": c}

    if "set-cookie" in res.headers:
        m = csrf_regex.search(res.headers["set-cookie"])
        if m:
            c = m.group(1)

    try:
        data = res.json()
    except ValueError:
        return {"images": [], "bookmark": "", "csrftoken": c}

    imgs = []
    resource_response = data.get("resource_response", {})
    results = resource_response.get("data", {}).get("results", [])

    for r in results:
        img_url = r.get("images", {}).get("orig", {}).get("url", "")
        if img_url:
            imgs.append(img_url)

    nb = resource_response.get("bookmark", "")
    if not nb:
        bookmarks = data.get("resource", {}).get("options", {}).get("bookmarks", [])
        if bookmarks:
            nb = bookmarks[0]

    return {"images": imgs, "bookmark": nb, "csrftoken": c}


@app.route("/")
def home():
    q = request.args.get("q", "")
    if not q:
        return render_template_string(HTML_TMPL, Q="", HTML="", Msg="", B="", C="")

    res = search_pinterest(q, "", "")
    html = ""
    for img in res["images"]:
        u = urllib.parse.quote(img)
        html += f'<a class="item" href="/proxy?u={u}" target="_blank"><img src="/proxy?u={u}" loading="lazy" decoding="async"></a>'

    msg = ""
    if res["bookmark"]:
        msg = "Loading..."
    elif not res["images"]:
        msg = "No results."

    return render_template_string(
        HTML_TMPL, Q=q, HTML=html, Msg=msg, B=res["bookmark"], C=res["csrftoken"]
    )


@app.route("/api")
def api():
    q = request.args.get("q", "")
    b = request.args.get("b", "")
    c = request.args.get("c", "")
    return jsonify(search_pinterest(q, b, c))


@app.route("/proxy")
def proxy():
    u = request.args.get("u", "")
    dl = request.args.get("dl", "0")
    
    try:
        parsed_url = urllib.parse.urlparse(u)
        hostname = parsed_url.hostname or ""
        valid_domains = ("pinimg.com", ".pinimg.com", "pinterest.com", ".pinterest.com")
        
        if not hostname.endswith(valid_domains) or parsed_url.scheme not in ["http", "https"]:
            return "Forbidden domain or scheme", 403
    except Exception:
        return "Invalid URL format", 400

    try:
        res = session.get(
            u, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=15
        )
        
        content_type = res.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return "Forbidden content type", 403
            
        headers = {"Cache-Control": "public, max-age=86400"}
        
        if dl == "1":
            filename = u.split("/")[-1] if "/" in u else "download.jpg"
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        return Response(
            res.iter_content(chunk_size=4096),
            content_type=content_type,
            headers=headers,
        )
    except requests.RequestException:
        return "Bad Gateway", 502
