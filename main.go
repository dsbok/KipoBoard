package main

import (
	"context"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

var tmpl = template.Must(template.New("index").Parse(`<head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{background:#000;color:#fff;font-family:sans-serif;text-align:center;margin:0}
.g{column-count:4;gap:1em;padding:0 1em} @media(max-width:800px){.g{column-count:2}}
</style></head><body>
<h2 style="margin:1em 0 0"><a href="/" style="color:#fff;text-decoration:none">kipoboard</a></h2>
<form style="padding:1em"><input name="q" value="{{.Query}}" autofocus><input type="submit" value="Search"></form>
<div class="g">
{{range .Images}}<a href="/proxy?u={{.}}"><img src="/proxy?u={{.}}" style="width:100%;margin-bottom:1em" loading="lazy"></a>{{end}}
</div>{{if .NextBookmark}}<a href="/?q={{.Query}}&b={{.NextBookmark}}" style="color:#fff;display:block;padding:2em">Next</a>{{end}}</body>`))

type PageData struct {
	Query        string
	Images       []string
	NextBookmark string
}

var (
	httpTransport = &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		MaxIdleConns:          500,
		MaxIdleConnsPerHost:   100,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   5 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
	}
	pinterestClient = &http.Client{
		Timeout:   10 * time.Second,
		Transport: httpTransport,
	}
	proxyClient = &http.Client{
		Timeout:   5 * time.Second,
		Transport: httpTransport,
	}
)

type cachedSearch struct {
	urls     []string
	bookmark string
	expiry   time.Time
}

type searchCache struct {
	mu    sync.RWMutex
	store map[string]cachedSearch
}

func newSearchCache(ctx context.Context) *searchCache {
	c := &searchCache{
		store: make(map[string]cachedSearch),
	}
	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				c.mu.Lock()
				now := time.Now()
				for key, val := range c.store {
					if now.After(val.expiry) {
						delete(c.store, key)
					}
				}
				c.mu.Unlock()
			}
		}
	}()
	return c
}

func (c *searchCache) get(q, b string) ([]string, string, bool) {
	key := q + "\x00" + b
	c.mu.RLock()
	defer c.mu.RUnlock()
	item, exists := c.store[key]
	if !exists || time.Now().After(item.expiry) {
		return nil, "", false
	}
	return item.urls, item.bookmark, true
}

func (c *searchCache) set(q, b string, urls []string, bookmark string, ttl time.Duration) {
	key := q + "\x00" + b
	c.mu.Lock()
	defer c.mu.Unlock()
	c.store[key] = cachedSearch{
		urls:     urls,
		bookmark: bookmark,
		expiry:   time.Now().Add(ttl),
	}
}

var cache = newSearchCache(context.Background())

func secureHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self';")
		next.ServeHTTP(w, r)
	})
}

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

func search(ctx context.Context, q, b string) ([]string, string, error) {
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

	req, err := http.NewRequestWithContext(ctx, "GET", pinterestURL, nil)
	if err != nil {
		return nil, "", err
	}

	req.Header.Set("User-Agent", "Mozilla/5.0")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Pinterest-AppState", "active")
	req.Header.Set("X-Pinterest-PWS-Handler", "www/search/[scope].js")

	resp, err := pinterestClient.Do(req)
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
	qRunes := []rune(q)
	if len(qRunes) > 100 {
		q = string(qRunes[:100])
	}
	b := r.URL.Query().Get("b")

	var imgs []string
	var n string
	if q != "" {
		var found bool
		imgs, n, found = cache.get(q, b)
		if !found {
			var err error
			imgs, n, err = search(r.Context(), q, b)
			if err != nil {
				log.Printf("[ERROR] Search failed for query %q, bookmark %q: %v", q, b, err)
				http.Error(w, "Search failed", http.StatusInternalServerError)
				return
			}
			cache.set(q, b, imgs, n, 10*time.Minute)
		}
	}

	data := PageData{
		Query:        q,
		Images:       imgs,
		NextBookmark: n,
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	if err := tmpl.Execute(w, data); err != nil {
		log.Printf("[ERROR] Template execution failed: %v", err)
	}
}

func handleProxy(w http.ResponseWriter, r *http.Request) {
	u := r.URL.Query().Get("u")
	parsedURL, err := url.Parse(u)
	if err != nil {
		log.Printf("[SECURITY] Failed to parse proxy target URL %q: %v", u, err)
		http.Error(w, "Invalid URL", http.StatusBadRequest)
		return
	}

	if parsedURL.Scheme != "https" {
		log.Printf("[SECURITY] Rejected proxy attempt with non-https scheme: %q from %s", parsedURL.Scheme, r.RemoteAddr)
		http.Error(w, "Forbidden scheme", http.StatusForbidden)
		return
	}

	if parsedURL.Host != "i.pinimg.com" {
		log.Printf("[SECURITY] Rejected proxy attempt to unauthorized host: %q from %s", parsedURL.Host, r.RemoteAddr)
		http.Error(w, "Forbidden host", http.StatusForbidden)
		return
	}

	targetURL := &url.URL{
		Scheme:   "https",
		Host:     "i.pinimg.com",
		Path:     parsedURL.Path,
		RawQuery: parsedURL.RawQuery,
	}

	req, err := http.NewRequestWithContext(r.Context(), "GET", targetURL.String(), nil)
	if err != nil {
		log.Printf("[ERROR] Failed to create proxy request for URL %q: %v", targetURL.String(), err)
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")

	resp, err := proxyClient.Do(req)
	if err != nil {
		log.Printf("[ERROR] Proxy request failed for URL %q: %v", targetURL.String(), err)
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("[ERROR] Proxy response returned non-OK status: %d for URL %q", resp.StatusCode, targetURL.String())
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
		return
	}

	contentType := resp.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "image/jpeg"
	}

	if !strings.HasPrefix(contentType, "image/") {
		log.Printf("[SECURITY] Rejected proxy response with non-image Content-Type: %q", contentType)
		http.Error(w, "Forbidden Content-Type", http.StatusForbidden)
		return
	}

	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Cache-Control", "public, max-age=31536000")
	w.WriteHeader(http.StatusOK)
	_, _ = io.Copy(w, resp.Body)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", handleIndex)
	mux.HandleFunc("/proxy", handleProxy)

	handler := secureHeaders(mux)

	port := os.Getenv("PORT")
	if port == "" {
		port = "5005"
	}

	log.Printf("Server starting on port %s...\n", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, handler); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}
