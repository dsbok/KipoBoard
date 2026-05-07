package main

import (
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)


type SearchResult struct {
	Images    []string `json:"images"`
	Bookmark  string   `json:"bookmark"`
	CsrfToken string   `json:"csrftoken,omitempty"`
}

func renderHeader(w http.ResponseWriter, title string) {
	fmt.Fprintf(w, `<!DOCTYPE html>

<html>

<head>

<title>%s</title>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

</head>

<body bgcolor="#ffffff" text="#000000" link="#0000EE" vlink="#551A8B">

<center>

<h1>dinterest</h1>

<p>
Simple Pinterest image search proxy
</p>

<hr width="80%%">

</center>`, html.EscapeString(title))
}

func renderFooter(w http.ResponseWriter, images []string) {
	fmt.Fprint(w, `

<hr width="80%">

<center>

<p>

<a href="https://github.com/dsbok/dinterest/" target="_blank">
Source
</a>

</p>`)

	if images != nil {
		fmt.Fprintf(w, "<p>%d images found</p>", len(images))
	}

	fmt.Fprint(w, `

</center>

</body>

</html>`)
}

func getRootDomain(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return ""
	}

	return parsed.Hostname()
}

func requestURL(rawURL string) ([]byte, error) {
	client := &http.Client{
		Timeout: 30 * time.Second,
	}

	req, err := http.NewRequest("GET", rawURL, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("User-Agent", "Mozilla/1.0")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	return io.ReadAll(resp.Body)
}

func performSearch(
	query string,
	bookmark string,
	csrftoken string,
) (*SearchResult, error) {

	baseURL :=
		"https://www.pinterest.com/resource/BaseSearchResource/get/"

	options := map[string]interface{}{
		"query": query,
		"scope": "pins",
	}

	if bookmark != "" {
		options["bookmarks"] = []string{bookmark}
	}

	payload := map[string]interface{}{
		"options": options,
		"context": map[string]interface{}{},
	}

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	searchURL :=
		baseURL +
			"?source_url=/search/pins/?q=" +
			url.QueryEscape(query) +
			"&data=" +
			url.QueryEscape(string(jsonPayload))

	req, err := http.NewRequest("GET", searchURL, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Accept", "application/json")
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	req.Header.Set("X-Pinterest-AppState", "active")
	req.Header.Set("X-Pinterest-PWS-Handler", "www/search/[scope].js")
	req.Header.Set("User-Agent", "Mozilla/1.0")

	if csrftoken != "" {
		req.Header.Set("X-CSRFToken", csrftoken)
		req.Header.Set("Cookie", "csrftoken="+csrftoken)
	}

	client := &http.Client{
		Timeout: 30 * time.Second,
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()

	for _, cookie := range resp.Cookies() {
		if cookie.Name == "csrftoken" {
			csrftoken = cookie.Value
		}
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var raw map[string]interface{}

	err = json.Unmarshal(body, &raw)
	if err != nil {
		return nil, err
	}

	result := &SearchResult{
		Images:    []string{},
		CsrfToken: csrftoken,
	}

	resourceResponse, ok :=
		raw["resource_response"].(map[string]interface{})

	if ok {

		data, ok :=
			resourceResponse["data"].(map[string]interface{})

		if ok {

			results, ok :=
				data["results"].([]interface{})

			if ok {

				for _, item := range results {

					entry, ok :=
						item.(map[string]interface{})

					if !ok {
						continue
					}

					images, ok :=
						entry["images"].(map[string]interface{})

					if !ok {
						continue
					}

					orig, ok :=
						images["orig"].(map[string]interface{})

					if !ok {
						continue
					}

					imageURL, ok :=
						orig["url"].(string)

					if ok && imageURL != "" {
						result.Images =
							append(result.Images, imageURL)
					}
				}
			}
		}
	}

	resource, ok :=
		raw["resource"].(map[string]interface{})

	if ok {

		options, ok :=
			resource["options"].(map[string]interface{})

		if ok {

			bookmarks, ok :=
				options["bookmarks"].([]interface{})

			if ok && len(bookmarks) > 0 {

				if bookmarkValue, ok := bookmarks[0].(string); ok {
					result.Bookmark = bookmarkValue
				}
			}
		}
	}

	if result.Bookmark == "" && resourceResponse != nil {

		if bookmarkValue, ok :=
			resourceResponse["bookmark"].(string); ok {

			result.Bookmark = bookmarkValue
		}
	}

	return result, nil
}


func imageProxyHandler(w http.ResponseWriter, r *http.Request) {
	rawURL := r.URL.Query().Get("url")

	allowedDomains := []string{
		"pinimg.com",
		"i.pinimg.com",
		"pinterest.com",
	}

	host := getRootDomain(rawURL)

	allowed := false

	for _, domain := range allowedDomains {

		if host == domain ||
			strings.HasSuffix(host, "."+domain) {

			allowed = true
			break
		}
	}

	if !allowed {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	image, err := requestURL(rawURL)
	if err != nil {
		http.Error(w, "Failed to fetch image", 500)
		return
	}

	w.Header().Set("Content-Type", "image/jpeg")

	w.Write(image)
}


func apiHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	query :=
		strings.TrimSpace(
			r.URL.Query().Get("q"),
		)

	bookmark :=
		r.URL.Query().Get("bookmark")

	csrftoken :=
		r.URL.Query().Get("csrftoken")

	result, err := performSearch(
		query,
		bookmark,
		csrftoken,
	)

	if err != nil {

		http.Error(
			w,
			`{"error":"search failed"}`,
			http.StatusInternalServerError,
		)

		return
	}

	json.NewEncoder(w).Encode(result)
}


func searchHandler(w http.ResponseWriter, r *http.Request) {
	query :=
		strings.TrimSpace(
			r.URL.Query().Get("q"),
		)

	if len(query) < 1 || len(query) > 64 {

		http.Redirect(
			w,
			r,
			"/",
			http.StatusFound,
		)

		return
	}

	renderHeader(
		w,
		query+" - dinterest",
	)

	fmt.Fprintf(w, `

<center>

<form
    method="get"
    autocomplete="off"
>

<input
    type="hidden"
    name="page"
    value="search"
>

<input
    type="text"
    name="q"
    size="40"
    value="%s"
>

<input
    type="submit"
    value="Search"
>

</form>

</center>

<hr width="80%%">`,
		html.EscapeString(query),
	)

	bookmark :=
		r.URL.Query().Get("bookmark")

	csrftoken :=
		r.URL.Query().Get("csrftoken")

	result, err := performSearch(
		query,
		bookmark,
		csrftoken,
	)

	if err == nil &&
		result != nil &&
		len(result.Images) > 0 {

		fmt.Fprint(w, "<center>")

		for _, image := range result.Images {

			safe :=
				html.EscapeString(image)

			fmt.Fprintf(w, `

<p>

<a
    href="?page=image_proxy&url=%s"
    target="_blank"
>

<img
    src="?page=image_proxy&url=%s"
    width="300"
    border="1"
>

</a>

</p>`,
				safe,
				safe,
			)
		}

		fmt.Fprint(w, "</center>")

	} else {

		fmt.Fprint(w, `

<center>

<p>
No results found.
</p>

</center>`)
	}


	if result != nil &&
		result.Bookmark != "" {

		queryEncoded :=
			url.QueryEscape(query)

		bookmarkEncoded :=
			url.QueryEscape(result.Bookmark)

		csrfEncoded :=
			url.QueryEscape(result.CsrfToken)

		fmt.Fprintf(w, `

<hr width="80%%">

<center>

<p>

<a href="?page=search&q=%s&bookmark=%s&csrftoken=%s">

[ Next ]

</a>

</p>

</center>`,
			queryEncoded,
			bookmarkEncoded,
			csrfEncoded,
		)
	}

	if result != nil {
		renderFooter(w, result.Images)
	} else {
		renderFooter(w, []string{})
	}
}


func homeHandler(w http.ResponseWriter, r *http.Request) {
	renderHeader(w, "Binternet")

	fmt.Fprint(w, `

<center>

<form
    method="get"
    autocomplete="off"
>

<input
    type="hidden"
    name="page"
    value="search"
>

<p>

<input
    type="text"
    name="q"
    size="40"
>

<input
    type="submit"
    value="Search"
>

</p>

</form>

</center>`)

	renderFooter(w, nil)
}

func main() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {

		page :=
			r.URL.Query().Get("page")

		switch page {

		case "image_proxy":
			imageProxyHandler(w, r)

		case "api":
			apiHandler(w, r)

		case "search":
			searchHandler(w, r)

		default:
			homeHandler(w, r)
		}
	})

	fmt.Println("dinterest running on :5003")

	err := http.ListenAndServe(":5003", nil)

	if err != nil {
		panic(err)
	}
}