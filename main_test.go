package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"
)

func TestSecureHeaders(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := secureHeaders(mux)
	req := httptest.NewRequest("GET", "/", nil)
	rr := httptest.NewRecorder()

	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("expected status OK, got %d", rr.Code)
	}

	headers := []string{"X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"}
	for _, h := range headers {
		if rr.Result().Header.Get(h) == "" {
			t.Errorf("expected header %q to be set", h)
		}
	}
}

func TestSearchCache(t *testing.T) {
	c := newSearchCache()

	_, _, found := c.get("query1", "")
	if found {
		t.Error("expected not to find non-existent query")
	}

	urls := []string{"https://i.pinimg.com/1.jpg"}
	c.set("query1", "bookmark1", urls, "next_bookmark", 100*time.Millisecond)

	cachedURLs, bookmark, found := c.get("query1", "bookmark1")
	if !found {
		t.Error("expected to find cached query")
	}
	if len(cachedURLs) != 1 || cachedURLs[0] != urls[0] || bookmark != "next_bookmark" {
		t.Error("cached data mismatch")
	}

	time.Sleep(150 * time.Millisecond)
	_, _, found = c.get("query1", "bookmark1")
	if found {
		t.Error("expected cached query to expire")
	}
}

func TestProxyHostValidation(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/proxy", handleProxy)

	testCases := []struct {
		name         string
		urlParam     string
		expectedCode int
	}{
		{
			name:         "Allowed Host",
			urlParam:     "https://i.pinimg.com/originals/foo.jpg",
			expectedCode: http.StatusBadGateway, // Will try to make outbound request to i.pinimg.com and fail/timeout or return 502/504 in test sandbox
		},
		{
			name:         "HTTP Scheme (Disallowed)",
			urlParam:     "http://i.pinimg.com/originals/foo.jpg",
			expectedCode: http.StatusForbidden,
		},
		{
			name:         "Unauthorized Host",
			urlParam:     "https://evil.com/i.pinimg.com/originals/foo.jpg",
			expectedCode: http.StatusForbidden,
		},
		{
			name:         "Subdomain Hijacking Attempt",
			urlParam:     "https://i.pinimg.com.evil.com/foo.jpg",
			expectedCode: http.StatusForbidden,
		},
		{
			name:         "Malformed URL",
			urlParam:     "://invalid-url",
			expectedCode: http.StatusBadRequest,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/proxy?u="+url.QueryEscape(tc.urlParam), nil)
			rr := httptest.NewRecorder()
			mux.ServeHTTP(rr, req)

			if rr.Code != tc.expectedCode {
				t.Errorf("expected status %d, got %d", tc.expectedCode, rr.Code)
			}
		})
	}
}
