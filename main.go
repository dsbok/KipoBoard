package main

import (
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const T = `<head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{background:#000;color:#fff;font-family:sans-serif;text-align:center;margin:0}
.g{column-count:4;gap:1em;padding:0 1em} @media(max-width:800px){.g{column-count:2}}
</style></head><body>
<h2 style="margin:1em 0 0"><a href="/" style="color:#fff;text-decoration:none">kipoboard</a></h2>
<form style="padding:1em"><input name="q" value="{{q}}" autofocus><input type="submit" value="Search"></form>
<div class="g">
{{imgs}}
</div>{{next_btn}}</body>`

type SearchOptions struct {
	Query     string   `json:"query"`
	Scope     string   `json:"scope"`
	Bookmarks []string `json:"bookmarks"`
}

type SearchData struct {
	Options SearchOptions `json:"options"`
}

type PinterestResponse struct {
	ResourceResponse struct {
		Data struct {
			Results []struct {
				Images map[string]struct {
					URL string `json:"url"`
				} `json:"images"`
			} `json:"results"`
		} `json:"data"`
		Bookmark string `json:"bookmark"`
	} `json:"resource_response"`
}

func urlQuote(s string) string {
	return strings.ReplaceAll(url.QueryEscape(s), "+", "%20")
}

func search(q, b string) ([]string, string, error) {
	bookmarks := []string{}
	if b != "" {
		bookmarks = append(bookmarks, b)
	}

	options := SearchOptions{
		Query:     q,
		Scope:     "pins",
		Bookmarks: bookmarks,
	}

	searchData := SearchData{
		Options: options,
	}

	dataBytes, err := json.Marshal(searchData)
	if err != nil {
		return nil, "", err
	}

	src := "/search/pins/?q=" + urlQuote(q)
	pinterestURL := fmt.Sprintf("https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=%s&data=%s",
		urlQuote(src),
		urlQuote(string(dataBytes)),
	)

	req, err := http.NewRequest("GET", pinterestURL, nil)
	if err != nil {
		return nil, "", err
	}

	req.Header.Set("User-Agent", "Mozilla/5.0")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Pinterest-AppState", "active")
	req.Header.Set("X-Pinterest-PWS-Handler", "www/search/[scope].js")

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()

	var pResp PinterestResponse
	if err := json.NewDecoder(resp.Body).Decode(&pResp); err != nil {
		return nil, "", err
	}

	var urls []string
	for _, result := range pResp.ResourceResponse.Data.Results {
		if result.Images != nil {
			if orig, ok := result.Images["orig"]; ok && orig.URL != "" {
				urls = append(urls, orig.URL)
			}
		}
	}

	return urls, pResp.ResourceResponse.Bookmark, nil
}

func handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.Error(w, "Not Found", http.StatusNotFound)
		return
	}

	q := r.URL.Query().Get("q")
	if len(q) > 100 {
		q = q[:100]
	}
	b := r.URL.Query().Get("b")

	var imgs []string
	var n string
	if q != "" {
		var err error
		imgs, n, err = search(q, b)
		if err != nil {
			imgs = []string{}
			n = ""
		}
	}

	var imgHTMLBuilder strings.Builder
	for _, img := range imgs {
		escapedImg := urlQuote(img)
		imgHTMLBuilder.WriteString(fmt.Sprintf(`<a href="/proxy?u=%s"><img src="/proxy?u=%s" style="width:100%%;margin-bottom:1em" loading="lazy"></a>`, escapedImg, escapedImg))
	}
	imgHTML := imgHTMLBuilder.String()

	var nextHTML string
	if n != "" {
		nextHTML = fmt.Sprintf(`<a href="/?q=%s&b=%s" style="color:#fff;display:block;padding:2em">Next</a>`, urlQuote(q), urlQuote(n))
	}

	escapedQ := html.EscapeString(q)

	resHTML := strings.ReplaceAll(T, "{{q}}", escapedQ)
	resHTML = strings.ReplaceAll(resHTML, "{{imgs}}", imgHTML)
	resHTML = strings.ReplaceAll(resHTML, "{{next_btn}}", nextHTML)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(resHTML))
}

func handleProxy(w http.ResponseWriter, r *http.Request) {
	u := r.URL.Query().Get("u")
	if !strings.Contains(u, "i.pinimg.com") {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	req, err := http.NewRequest("GET", u, nil)
	if err != nil {
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")

	client := &http.Client{
		Timeout: 5 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}

	contentType := resp.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "image/jpeg"
	}

	w.Header().Set("Content-Type", contentType)
	w.WriteHeader(http.StatusOK)
	_, _ = io.Copy(w, resp.Body)
}

func main() {
	http.HandleFunc("/", handleIndex)
	http.HandleFunc("/proxy", handleProxy)

	port := os.Getenv("PORT")
	if port == "" {
		port = "5005"
	}

	fmt.Printf("Server starting on port %s...\n", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, nil); err != nil {
		panic(err)
	}
}
