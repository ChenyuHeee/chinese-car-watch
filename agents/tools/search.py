"""
Search tools for AG2 agents.
Currently uses web scraping, can be upgraded to Tavily/SerpAPI.
"""

import json
import logging
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def search_news(query: str, num_results: int = 8) -> str:
    """Search for recent auto industry news.

    Args:
        query: search query (in Chinese or English)
        num_results: max number of results
    """
    encoded = quote(query)
    url = f"https://www.google.com/search?q={encoded}+汽车&tbm=nws&num={num_results}&hl=zh-CN"

    try:
        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=10)
        resp.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for g in soup.select(".SoaBEf, .WlydOe")[:num_results]:
            title_el = g.select_one(".nDgy9d, .mCBkyc")
            snippet_el = g.select_one(".GI74Re, .GI74Re")
            link_el = g.select_one("a")
            results.append({
                "title": title_el.get_text() if title_el else "",
                "snippet": snippet_el.get_text()[:300] if snippet_el else "",
                "url": link_el["href"] if link_el and link_el.get("href") else "",
            })

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

        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Clean up whitespace
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
