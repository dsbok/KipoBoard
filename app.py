import json
import re
import urllib.parse
from flask import Flask, request, jsonify, render_template_string, Response
import requests

app = Flask(__name__)

csrf_regex = re.compile(r"csrftoken=([^;]+)")

HTML_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
	<title>KipoBoard</title>
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<style>
		body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; text-align: center; background: #000; color: #fff; }
		form { margin: 1.5rem 0; }
		input[type="text"] { width: 300px; max-width: 80vw; padding: 4px; }
		.masonry { display: flex; gap: 1rem; padding: 1rem 0; align-items: flex-start; }
		.col { display: flex; flex-direction: column; gap: 1rem; flex: 1 1 0; min-width: 0; }
		.item img { width: 100%; display: block; background: #111; min-height: 100px; object-fit: cover; border-radius: 4px; transition: opacity 0.2s ease; cursor: zoom-in; }
		.item img:hover { opacity: 0.8; }
		a { color: #fff; }

		#lightbox { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; align-items: center; justify-content: center; flex-direction: column; cursor: zoom-out; backdrop-filter: blur(5px); }
		#lightbox img { max-width: 90vw; max-height: 85vh; object-fit: contain; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.7); }
		#lightbox.active { display: flex; }
        
        .dl-btn { margin-top: 20px; padding: 10px 24px; background: #fff; color: #000; text-decoration: none; border-radius: 20px; font-weight: bold; cursor: pointer; transition: background 0.2s; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        .dl-btn:hover { background: #ddd; }

        #btt { display: none; position: fixed; bottom: 20px; right: 20px; padding: 12px 18px; background: #333; color: #fff; border: none; border-radius: 50px; cursor: pointer; z-index: 999; opacity: 0.8; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.5); transition: opacity 0.2s; }
        #btt:hover { opacity: 1; }
	</style>
</head>
<body>
	<h2><a href="https://github.com/dsbok/KipoBoard" style="text-decoration:none;" target="_blank">KipoBoard</a></h2>
	<form>
		<input type="text" name="q" value="{{ Q }}" required placeholder="Search images..." autofocus> 
		<input type="submit" value="Search">
	</form>
	
	<div id="grid" class="masonry"></div>
	<div id="raw" style="display:none;">{{ HTML|safe }}</div>
	<p id="s" style="opacity:0.5; margin:2rem;">{{ Msg }}</p>

	<div id="lightbox" onclick="if(event.target.id === 'lightbox' || event.target.id === 'lightbox-img') this.classList.remove('active')">
		<img id="lightbox-img" src="">
        <a id="lightbox-dl" href="" class="dl-btn">Download Image</a>
	</div>

    <button id="btt" onclick="window.scrollTo({top:0, behavior:'smooth'})">↑ Top</button>

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
					tmp.innerHTML += '<a class="item" href="'+p+'" target="_blank"><img src="'+p+'" loading="lazy"></a>';
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
				document.getElementById('lightbox-img').src = item.href;
                document.getElementById('lightbox-dl').href = item.href + '&dl=1';
				document.getElementById('lightbox').classList.add('active');
			}
		});

        window.addEventListener('scroll', () => {
            document.getElementById('btt').style.display = window.scrollY > 800 ? 'block' : 'none';
        });
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
        res = requests.get(target_url, headers=headers, timeout=15)
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
        html += f'<a class="item" href="/proxy?u={u}" target="_blank"><img src="/proxy?u={u}" loading="lazy"></a>'

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
        res = requests.get(
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
