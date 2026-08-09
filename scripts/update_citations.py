#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "citations.json"
INDEX_PATH = ROOT / "index.html"
SERPAPI_URL = "https://serpapi.com/search.json"


def fetch_scholar_result(api_key, query):
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": api_key,
    }
    url = f"{SERPAPI_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "homepage-citation-updater/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def pick_result(payload, expected_title):
    expected = normalize_title(expected_title)
    results = payload.get("organic_results") or []
    if not results:
        raise ValueError("SerpAPI response has no organic_results")

    for result in results:
        if normalize_title(result.get("title", "")) == expected:
            return result

    for result in results:
        title = normalize_title(result.get("title", ""))
        if expected in title or title in expected:
            return result

    return results[0]


def citation_count(result):
    cited_by = (result.get("inline_links") or {}).get("cited_by") or {}
    total = cited_by.get("total")
    if total is None:
        raise ValueError("SerpAPI result has no cited_by.total")
    return int(str(total).replace(",", ""))


def update_html(html, citation_id, count):
    pattern = re.compile(
        rf'(<a\b[^>]*\bdata-citation-id="{re.escape(citation_id)}"[^>]*>)(.*?)(</a>)',
        re.DOTALL,
    )

    def replace(match):
        return f"{match.group(1)}Cited by {count}{match.group(3)}"

    updated, num_replacements = pattern.subn(replace, html)
    if num_replacements != 1:
        raise ValueError(f"Expected exactly one citation link for id {citation_id}, found {num_replacements}")
    return updated


def main():
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("SERPAPI_API_KEY is not set", file=sys.stderr)
        return 2

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    html = INDEX_PATH.read_text(encoding="utf-8")

    for i, item in enumerate(config):
        payload = fetch_scholar_result(api_key, item["query"])
        result = pick_result(payload, item["title"])
        count = citation_count(result)
        html = update_html(html, item["id"], count)
        print(f'{item["id"]}: {count}')
        if i < len(config) - 1:
            time.sleep(1)

    INDEX_PATH.write_text(html, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
