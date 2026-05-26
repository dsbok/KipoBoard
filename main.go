package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

const Port = 5003

var allowedDomains = []string{"pinimg.com", "i.pinimg.com", "pinterest.com"}
var csrfRegex = regexp.MustCompile(`csrftoken=([^;]+)`)

type SearchResult struct {
	Images    []string `json:"images"`
	Bookmark  string   `json:"bookmark"`
	CSRFToken string   `json:"csrftoken"`
}

type TemplateData struct {
	Query        string
	ImagesHTML   template.HTML
	SentinelText string
	Bookmark     string
	CSRFToken    string
}

const htmlTemplateStr = `
<!DOCTYPE html>
<html lang="en">
<head>
    <title>KipoBoard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root { color-scheme: dark; }
        body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; text-align: center; background-color: #000000; color: #FFFFFF; }
        form { margin: 1.5rem 0; }
        input { font-size: 1rem; }
        input[type="text"] { width: 300px; max-width: 80vw; }
        
        .masonry { display: flex; gap: 1rem; padding: 1rem 0; align-items: flex-start; }
        .col { display: flex; flex-direction: column; gap: 1rem; flex: 1 1 0; min-width: 0; }
        
        .item { display: block; width: 100%; }
        .item img { width: 100%; border-radius: 8px; display: block; background-color: #111; min-height: 100px; object-fit: cover; }
        a { color: inherit; text-decoration: none; }
    </style>
</head>
<body>
    <h1><a href="https://github.com/dsbok/kipoboard">KipoBoard</a></h1>
    <form method="get" action="/search">
        <input type="text" name="q" value="{{.Query}}" required placeholder="Search images..." autofocus>
        <input type="submit" value="Search">
    </form>
    
    <div id="grid" class="masonry"></div>
    <div id="raw" style="display:none;">{{.ImagesHTML}}</div>
    <div id="sentinel" style="margin: 2rem; opacity: 0.5;">{{.SentinelText}}</div>

    <script>
        let q = "{{.Query}}", bookmark = "{{.Bookmark}}", csrf = "{{.CSRFToken}}", loading = false;
        const s = document.getElementById('sentinel');
        const g = document.getElementById('grid');
        
        const targetColWidth = 200; 
        const nCols = Math.max(3, Math.floor(window.innerWidth / targetColWidth));
        
        const cols = [];
        for(let i=0; i<nCols; i++) {
            let c = document.createElement('div');
            c.className = 'col';
            g.appendChild(c);
            cols.push(c);
        }
        
        function getShortestColIndex() {
            let shortestIdx = 0;
            let minHeight = cols[0].offsetHeight;
            for (let i = 1; i < nCols; i++) {
                if (cols[i].offsetHeight < minHeight) {
                    minHeight = cols[i].offsetHeight;
                    shortestIdx = i;
                }
            }
            return shortestIdx;
        }
        
        let fallbackIdx = 0;
        function addItems(container) {
            const items = Array.from(container.children);
            items.forEach(item => {
                let targetCol = cols[getShortestColIndex()];
                if (targetCol.offsetHeight === 0) {
                    targetCol = cols[fallbackIdx % nCols];
                    fallbackIdx++;
                }
                targetCol.appendChild(item);
            });
        }
        
        addItems(document.getElementById('raw'));
        
        if (s && bookmark) {
            new IntersectionObserver(e => {
                if (e[0].isIntersecting && !loading && bookmark) loadMore();
            }, {rootMargin: "800px"}).observe(s);
        }

        async function loadMore() {
            loading = true;
            try {
                const res = await fetch('/api?q=' + encodeURIComponent(q) + '&bookmark=' + encodeURIComponent(bookmark) + '&csrftoken=' + encodeURIComponent(csrf));
                const data = await res.json();
                
                const temp = document.createElement('div');
                data.images.forEach(img => {
                    const proxyUrl = '/image_proxy?url=' + encodeURIComponent(img);
                    temp.innerHTML += '<a class="item" href="' + proxyUrl + '" target="_blank"><img src="' + proxyUrl + '" loading="lazy"></a>';
                });
                
                addItems(temp);
                
                bookmark = data.bookmark;
                csrf = data.csrftoken;
                if (!bookmark) s.textContent = "No more results.";
            } catch(e) {
                s.textContent = "Error loading more.";
            }
            loading = false;
        }
    </script>
</body>
</html>
`

var htmlTemplate = template.Must(template.New("board").Parse(htmlTemplateStr))

func isAllowedDomain(rawURL string) bool {
	u, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := u.Hostname()
	if host == "" {
		return false
	}
	for _, d := range allowedDomains {
		if host == d || strings.HasSuffix(host, "."+d) {
			return true
		}
	}
	return false
}

func performSearch(query, bookmark, csrfToken string) (SearchResult, error) {
	options := map[string]interface{}{
		"query": query,
		"scope": "pins",
	}
	if bookmark != "" {
		options["bookmarks"] = []string{bookmark}
	}

	payloadMap := map[string]interface{}{
		"options": options,
		"context": map[string]interface{}{},
	}

	payloadBytes, err := json.Marshal(payloadMap)
	if err != nil {
		return SearchResult{}, err
	}

	payload := url.QueryEscape(string(payloadBytes))
	queryQuoted := url.QueryEscape(query)
	targetURL := fmt.Sprintf("https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=/search/pins/?q=%s&data=%s", queryQuoted, payload)

	req, err := http.NewRequest("GET", targetURL, nil)
	if err != nil {
		return SearchResult{}, err
	}

	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-Pinterest-AppState", "active")
	req.Header.Set("X-Pinterest-PWS-Handler", "www/search/[scope].js")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	if csrfToken != "" {
		req.Header.Set("X-CSRFToken", csrfToken)
		req.Header.Set("Cookie", fmt.Sprintf("csrftoken=%s", csrfToken))
	}

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return SearchResult{}, err
	}
	defer resp.Body.Close()

	newCSRF := csrfToken
	for _, cookie := range resp.Header["Set-Cookie"] {
		matches := csrfRegex.FindStringSubmatch(cookie)
		if len(matches) > 1 {
			newCSRF = matches[1]
			break
		}
	}

	var respData map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&respData); err != nil {
		return SearchResult{}, err
	}

	var images []string
	var newBookmark string

	resResp, _ := respData["resource_response"].(map[string]interface{})
	if resResp != nil {
		if dataMap, ok := resResp["data"].(map[string]interface{}); ok {
			if results, ok := dataMap["results"].([]interface{}); ok {
				for _, itemInf := range results {
					if item, ok := itemInf.(map[string]interface{}); ok {
						if imagesMap, ok := item["images"].(map[string]interface{}); ok {
							if orig, ok := imagesMap["orig"].(map[string]interface{}); ok {
								if imgURL, ok := orig["url"].(string); ok && imgURL != "" {
									images = append(images, imgURL)
								}
							}
						}
					}
				}
			}
		}
	}

	if resource, ok := respData["resource"].(map[string]interface{}); ok {
		if opts, ok := resource["options"].(map[string]interface{}); ok {
			if bookmarks, ok := opts["bookmarks"].([]interface{}); ok && len(bookmarks) > 0 {
				newBookmark, _ = bookmarks[0].(string)
			}
		}
	}
	
	if newBookmark == "" && resResp != nil {
		if bm, ok := resResp["bookmark"].(string); ok {
			newBookmark = bm
		}
	}

	return SearchResult{
		Images:    images,
		Bookmark:  newBookmark,
		CSRFToken: newCSRF,
	}, nil
}

func indexHandler(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	htmlTemplate.Execute(w, TemplateData{})
}

func searchHandler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "Missing query", http.StatusBadRequest)
		return
	}

	res, err := performSearch(q, "", "")
	if err != nil {
		http.Error(w, "Search failed", http.StatusInternalServerError)
		return
	}

	var imgsBuilder strings.Builder
	for _, img := range res.Images {
		escapedURL := url.QueryEscape(img)
		imgsBuilder.WriteString(fmt.Sprintf(`<a class="item" href="/image_proxy?url=%s" target="_blank"><img src="/image_proxy?url=%s" loading="lazy"></a>`, escapedURL, escapedURL))
	}

	sentinel := ""
	if res.Bookmark != "" {
		sentinel = "Loading..."
	} else if len(res.Images) == 0 {
		sentinel = "No results."
	}

	w.Header().Set("Content-Type", "text/html")
	htmlTemplate.Execute(w, TemplateData{
		Query:        q,
		ImagesHTML:   template.HTML(imgsBuilder.String()),
		SentinelText: sentinel,
		Bookmark:     res.Bookmark,
		CSRFToken:    res.CSRFToken,
	})
}

func apiHandler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		http.Error(w, "Missing query", http.StatusBadRequest)
		return
	}
	
	bookmark := r.URL.Query().Get("bookmark")
	csrfToken := r.URL.Query().Get("csrftoken")

	res, err := performSearch(q, bookmark, csrfToken)
	if err != nil {
		http.Error(w, `{"error": "Search failed"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(res)
}

func proxyHandler(w http.ResponseWriter, r *http.Request) {
	targetURL := r.URL.Query().Get("url")
	if !isAllowedDomain(targetURL) {
		http.Error(w, "Forbidden domain", http.StatusForbidden)
		return
	}

	req, err := http.NewRequest("GET", targetURL, nil)
	if err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	contentType := resp.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "image/jpeg"
	}

	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Cache-Control", "public, max-age=86400")
	w.WriteHeader(http.StatusOK)
 
	io.Copy(w, resp.Body)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", indexHandler)
	mux.HandleFunc("/search", searchHandler)
	mux.HandleFunc("/api", apiHandler)
	mux.HandleFunc("/image_proxy", proxyHandler)

	addr := fmt.Sprintf("0.0.0.0:%d", Port)
	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}

	fmt.Printf("KipoBoard is running. Open http://localhost:%d in your browser.\n", Port)
	log.Fatal(server.ListenAndServe())
}
