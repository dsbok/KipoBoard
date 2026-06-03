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
		.item img { width: 100%; display: block; background: #111; min-height: 100px; object-fit: cover; }
		a { color: #fff; }
	</style>
</head>
<body>
	<h2><a href="https://github.com/dsbok/kipoboard" style="text-decoration:none;" target="_blank">KipoBoard</a></h2>
	<form>
		<input type="text" name="q" value="{{ Q }}" required placeholder="Search images..." autofocus> 
		<input type="submit" value="Search">
	</form>
	
	<div id="grid" class="masonry"></div>
	<div id="raw" style="display:none;">{{ HTML|safe }}</div>
	<p id="s" style="opacity:0.5; margin:2rem;">{{ Msg }}</p>

	<script>
		let q="{{ Q }}", b="{{ B }}", c="{{ C }}", l=false, s=document.getElementById('s'), g=document.getElementById('grid');
		
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
    if "pinimg.com" not in u and "pinterest.com" not in u:
        return "Forbidden domain", 403

    try:
        res = requests.get(
            u, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=15
        )
        return Response(
            res.iter_content(chunk_size=4096),
            content_type=res.headers.get("Content-Type"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except requests.RequestException:
        return "Bad Gateway", 502


if __name__ == "__main__":
    print("KipoBoard is running on http://localhost:5005")
    app.run(host="0.0.0.0", port=5005)
