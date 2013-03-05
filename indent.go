package main

import (
	"appengine"
	"appengine/urlfetch"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"io/ioutil"
	"net/http"
	"regexp"
)

const (
	EXAMPLE_URL    = "https://www.googleapis.com/plus/v1/people/+DeWittClinton"
	API_KEY        = "AIzaSyDyMJWU-cElvX5NESC8zdQ3XoURbkT4DOc" // rate limited per user in console
	USAGE_TEMPLATE = "templates/usage.tmpl"
	COLOR_TEMPLATE = "templates/color.tmpl"
)

var (
	UNSAFE_JSON_CHARS, _ = regexp.Compile("[^\\w\\d\\-\\_]")
)

func init() {
	http.HandleFunc("/", usage)
	http.HandleFunc("/indent", indent)
}

func usage(w http.ResponseWriter, r *http.Request) {
	t, err := template.ParseFiles(USAGE_TEMPLATE)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	} else {
		data := map[string]interface{}{"Url": template.URL(EXAMPLE_URL)}
		t.Execute(w, data)
	}
}

func santizeCallback(s string) string {
	if UNSAFE_JSON_CHARS.Match([]byte(s)) {
		return ""
	}
	return s
}

func content(w http.ResponseWriter, r *http.Request) (string, error, int) {
	content := r.FormValue("content")
	if content != "" {
		return content, nil, http.StatusOK
	}
	url := r.FormValue("url")
	if url == "" {
		return "", errors.New("Either a 'content' or 'url' parameter is required."), http.StatusBadRequest
	}
	c := appengine.NewContext(r)
	client := urlfetch.Client(c)
	if url == EXAMPLE_URL {
		url = fmt.Sprintf("%s?key=%s&userIp=%s", url, API_KEY, r.RemoteAddr)
	}
	resp, err := client.Get(url)
	if err != nil {
		return "", err, http.StatusInternalServerError
	}
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return "", err, http.StatusInternalServerError
	}
	return string(body), nil, http.StatusOK
}

func print(w http.ResponseWriter, r *http.Request, indented string) {
	color := r.FormValue("color")
	if color == "true" {
		printColor(w, r, indented)
	} else {
		callback := santizeCallback(r.FormValue("callback"))
		if callback != "" {
			w.Header().Set("Content-type", "application/javascript")
			fmt.Fprintf(w, "%s(%s)", callback, indented)
		} else {
			w.Header().Set("Content-type", "application/json")
			fmt.Fprint(w, indented)
		}
	}
}

func printColor(w http.ResponseWriter, r *http.Request, indented string) {
	t, err := template.ParseFiles(COLOR_TEMPLATE)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	} else {
		data := map[string]interface{}{"Indented": template.HTML(indented)}
		t.Execute(w, data)
	}
}

func indent(w http.ResponseWriter, r *http.Request) {
	content, err, status := content(w, r)
	if err != nil {
		http.Error(w, err.Error(), status)
		return
	}
	buffer := bytes.NewBuffer([]byte{})
	err = json.Indent(buffer, []byte(content), "", "  ")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	print(w, r, buffer.String())
}
