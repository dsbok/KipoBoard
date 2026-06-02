package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

var (
	client    = &http.Client{Timeout: 15 * time.Second}
	csrfRegex = regexp.MustCompile(`csrftoken=([^;]+)`)
	tmpl      = template.Must(template.New("").Parse(htmlTmpl))
)

type SearchResult struct {
	Images []string `json:"images"`
	Book   string   `json:"bookmark"`
	CSRF   string   `json:"csrftoken"`
}

type PinResp struct {
	Resource struct {
		Options struct{ Bookmarks []string }
	}
	ResourceResponse struct {
		Bookmark string
		Data     struct {
			Results []struct {
				Images struct{ Orig struct{ URL string } }
			}
		}
	} `json:"resource_response"`
}

const htmlTmpl = `<!DOCTYPE html>
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
		<input type="text" name="q" value="{{.Q}}" required placeholder="Search images..." autofocus> 
		<input type="submit" value="Search">
	</form>
	
	<div id="grid" class="masonry"></div>
	<div id="raw" style="display:none;">{{.HTML}}</div>
	<p id="s" style="opacity:0.5; margin:2rem;">{{.Msg}}</p>

	<script>
		let q="{{.Q}}", b="{{.B}}", c="{{.C}}", l=false, s=document.getElementById('s'), g=document.getElementById('grid');
		
		const cols = Array.from({length: Math.max(3, Math.floor(window.innerWidth/200))}, () => {
			let c = document.createElement('div'); c.className='col'; g.appendChild(c); return c;
		});

		function addItems(cnt) {
			Array.from(cnt.children).forEach(i => {
				cols.reduce((min, cur) => cur.offsetHeight < min.offsetHeight ? cur : min, cols[0]).appendChild(i);
			});
		}
		addItems(document.getElementById('raw'));

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
</html>`

func search(q, b, c string) (SearchResult, error) {
	opts := map[string]any{"query": q, "scope": "pins"}
	if b != "" {
		opts["bookmarks"] = []string{b}
	}
	p, _ := json.Marshal(map[string]any{"options": opts, "context": map[string]any{}})

	targetURL := "https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q=" + url.QueryEscape(q) + "&data=" + url.QueryEscape(string(p))
	req, _ := http.NewRequest("GET", targetURL, nil)
	
	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-Pinterest-AppState", "active")
	req.Header.Set("X-Pinterest-PWS-Handler", "www/search/[scope].js")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	
	if c != "" {
		req.Header.Set("X-CSRFToken", c)
		req.Header.Set("Cookie", "csrftoken="+c)
	}

	res, err := client.Do(req)
	if err != nil {
		return SearchResult{}, err
	}
	defer res.Body.Close()

	for _, ck := range res.Header["Set-Cookie"] {
		if m := csrfRegex.FindStringSubmatch(ck); len(m) > 1 {
			c = m[1]
			break
		}
	}

	var pr PinResp
	json.NewDecoder(res.Body).Decode(&pr)

	var imgs []string
	for _, r := range pr.ResourceResponse.Data.Results {
		if u := r.Images.Orig.URL; u != "" {
			imgs = append(imgs, u)
		}
	}

	nb := pr.ResourceResponse.Bookmark
	if nb == "" && len(pr.Resource.Options.Bookmarks) > 0 {
		nb = pr.Resource.Options.Bookmarks[0]
	}

	return SearchResult{Images: imgs, Book: nb, CSRF: c}, nil
}

func home(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		tmpl.Execute(w, map[string]any{})
		return
	}

	res, _ := search(q, "", "")
	var html strings.Builder
	for _, i := range res.Images {
		u := url.QueryEscape(i)
		html.WriteString(fmt.Sprintf(`<a class="item" href="/proxy?u=%s" target="_blank"><img src="/proxy?u=%s" loading="lazy"></a>`, u, u))
	}

	msg := ""
	if res.Book != "" {
		msg = "Loading..."
	} else if len(res.Images) == 0 {
		msg = "No results."
	}
	tmpl.Execute(w, map[string]any{"Q": q, "HTML": template.HTML(html.String()), "Msg": msg, "B": res.Book, "C": res.CSRF})
}

func api(w http.ResponseWriter, r *http.Request) {
	res, _ := search(r.URL.Query().Get("q"), r.URL.Query().Get("b"), r.URL.Query().Get("c"))
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(res)
}

func proxy(w http.ResponseWriter, r *http.Request) {
	u := r.URL.Query().Get("u")
	if !strings.Contains(u, "pinimg.com") && !strings.Contains(u, "pinterest.com") {
		http.Error(w, "Forbidden domain", http.StatusForbidden)
		return
	}

	req, _ := http.NewRequest("GET", u, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")
	if res, err := client.Do(req); err == nil {
		defer res.Body.Close()
		w.Header().Set("Content-Type", res.Header.Get("Content-Type"))
		w.Header().Set("Cache-Control", "public, max-age=86400")
		io.Copy(w, res.Body)
	}
}

func main() {
	http.HandleFunc("/", home)
	http.HandleFunc("/api", api)
	http.HandleFunc("/proxy", proxy)
	
	fmt.Println("KipoBoard is running on http://localhost:5003")
	http.ListenAndServe(":5003", nil)
}
