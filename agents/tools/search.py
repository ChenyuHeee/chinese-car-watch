"""
Search tools for AG2 agents.

Currently uses a lightweight web-based approach.
For production, upgrade to a proper search API:
  - Tavily (https://tavily.com) — AI-optimized search
  - SerpAPI (https://serpapi.com) — Google/Bing search
  - Bing Search API (Azure)
  - DuckDuckGo Instant Answer API (free, no key needed)
"""

import json
import logging

import requests

log = logging.getLogger(__name__)

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def search_news(query: str, num_results: int = 8) -> str:
    """Search for recent auto industry news using DuckDuckGo (no API key needed).

    Args:
        query: search query (in Chinese or English)
        num_results: max number of results
    """
    try:
        # Use DuckDuckGo Instant Answer API — free, no key required
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"{query} 汽车", "format": "json", "no_html": 1, "skip_disambig": 1},
            headers=SEARCH_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        # Abstract
        if data.get("AbstractText"):
            results.append({
                "title": data.get("AbstractSource", "DuckDuckGo"),
                "snippet": data["AbstractText"][:500],
                "url": data.get("AbstractURL", ""),
            })
        # Related topics
        for topic in data.get("RelatedTopics", [])[:num_results - 1]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic["Text"][:300],
                    "url": topic.get("FirstURL", ""),
                })

        if not results:
            return json.dumps({"message": f"No results found for '{query}'", "query": query}, ensure_ascii=False)

        return json.dumps(results, ensure_ascii=False, indent=2)

    except Exception as e:
        log.warning("search_news failed: %s", e)
        return json.dumps({"error": str(e), "query": query})


def fetch_url_content(url: str, max_chars: int = 5000) -> str:
    """Fetch and extract text content from a URL.

    Args:
        url: the URL to fetch
        max_chars: maximum characters to return
    """
    try:
        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated, {len(text)} total chars]"

        return text

    except Exception as e:
        log.warning("fetch_url_content failed for %s: %s", url, e)
        return f"Error fetching {url}: {e}"


SEARCH_TOOLS = [
    search_news,
    fetch_url_content,
]
