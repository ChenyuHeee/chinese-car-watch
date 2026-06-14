"""
Base crawler with retry, proxy, rate limiting, and logging.
All crawlers inherit from this.
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import requests

log = logging.getLogger(__name__)

# Respect proxy env vars
PROXIES: dict = {}
for scheme in ("http", "https"):
    env_val = os.environ.get(f"{scheme.upper()}_PROXY") or os.environ.get(f"{scheme}_proxy")
    if env_val:
        PROXIES[scheme] = env_val

if "all_proxy" in os.environ or "ALL_PROXY" in os.environ:
    all_p = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy", "")
    if all_p:
        PROXIES["http"] = all_p
        PROXIES["https"] = all_p

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


class BaseCrawler(ABC):
    """Abstract base crawler.

    Subclass and implement:
      - name: str
      - sources: list[dict]  (each with 'url', 'label')
      - parse(html: str) -> list[dict]
    """

    name: str = "base"
    sources: list[dict] = []
    request_interval: float = 1.0   # seconds between requests
    max_retries: int = 3

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA_POOL[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self._ua_idx = 0

    def _rotate_ua(self):
        self._ua_idx = (self._ua_idx + 1) % len(UA_POOL)
        self.session.headers["User-Agent"] = UA_POOL[self._ua_idx]

    def fetch(self, url: str) -> Optional[str]:
        """Fetch URL with retries and backoff."""
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url,
                    proxies=PROXIES or None,
                    timeout=30,
                )
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return resp.text
            except requests.RequestException as e:
                log.warning("%s: attempt %d/%d for %s: %s", self.name, attempt + 1, self.max_retries, url, e)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    self._rotate_ua()
        log.error("%s: failed to fetch %s", self.name, url)
        return None

    @abstractmethod
    def parse(self, html: str, **kwargs) -> list[dict]:
        """Parse HTML into list of dict rows."""
        ...

    def run(self, **kwargs) -> list[dict]:
        """Run the crawler: fetch + parse all sources."""
        all_rows = []
        for src in self.sources:
            log.info("%s: scraping %s (%s)", self.name, src["label"], src["url"])
            html = self.fetch(src["url"])
            if html is None:
                continue
            rows = self.parse(html, source=src, **kwargs)
            for r in rows:
                r["crawler"] = self.name
                r["scraped_at"] = datetime.now().isoformat()
            all_rows.extend(rows)
            log.info("%s: %d rows from %s", self.name, len(rows), src["label"])
            time.sleep(self.request_interval)
        log.info("%s: %d total rows", self.name, len(all_rows))
        return all_rows
