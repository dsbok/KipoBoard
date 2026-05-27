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

type pinterestRequest struct {
	Options struct {
		Query     string   `json:"query"`
		Scope     string   `json:"scope"`
		Bookmarks []string `json:"bookmarks,omitempty"`
	} `json:"options"`
	Context struct{} `json:"context"`
}

type pinterestResponse struct {
	ResourceResponse struct {
		Data struct {
			Results []struct {
				Images struct {
					Orig struct {
						URL string `json:"url"`
					} `json:"orig"`
				} `json:"images"`
			} `json:"results"`
		} `json:"data"`
		Bookmark string `json:"bookmark"`
	} `json:"resource_response"`
	Resource struct {
		Options struct {
			Bookmarks []string `json:"bookmarks"`
		} `json:"options"`
	} `json:"resource"`
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
        
        const cols = Array.from({ length: nCols }, () => {
            const c = document.createElement('div');
            c.className = 'col';
            g.appendChild(c);
            return c;
        });
        
        function getShortestColIndex() {
            return cols.reduce((minIdx, col, idx) => col.offsetHeight < cols[minIdx].offsetHeight ? idx : minIdx, 0);
        }
        
        let fallbackIdx = 0;
        function addItems(container) {
            Array.from(container.children).forEach(item => {
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
	for _, d := range allowedDomains {
		if host == d || strings.HasSuffix(host, "."+d) {
			return true
		}
	}
	return false
}

func performSearch(query, bookmark, csrfToken string) (SearchResult, error) {
	var reqPayload pinterestRequest
	reqPayload.Options.Query = query
	reqPayload.Options.Scope = "pins"
	if bookmark != "" {
		reqPayload.Options.Bookmarks = []string{bookmark}
	}

	payloadBytes, err := json.Marshal(reqPayload)
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

	var apiResp pinterestResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return SearchResult{}, err
	}

	var images []string
	for _, res := range apiResp.ResourceResponse.Data.Results {
		if imgURL := res.Images.Orig.URL; imgURL != "" {
			images = append(images, imgURL)
		}
	}

	var newBookmark string
	if len(apiResp.Resource.Options.Bookmarks) > 0 {
		newBookmark = apiResp.Resource.Options.Bookmarks[0]
	}
	if newBookmark == "" {
		newBookmark = apiResp.ResourceResponse.Bookmark
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
