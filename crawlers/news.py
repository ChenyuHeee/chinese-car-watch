"""
Auto industry news crawler.
Multi-source aggregation with brand detection and sentiment.
"""

import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler

log = logging.getLogger(__name__)

BRAND_NAMES = [
    "比亚迪", "特斯拉", "蔚来", "小鹏", "理想", "零跑", "极氪", "问界",
    "小米汽车", "鸿蒙智行", "深蓝", "方程豹", "腾势", "阿维塔", "岚图",
    "智己", "乐道", "银河", "埃安", "五菱", "吉利", "长城", "长安",
    "奇瑞", "大众", "丰田", "本田", "日产", "奔驰", "宝马", "奥迪",
    "别克", "福特", "现代", "起亚", "宁德时代", "华为", "地平线",
]

SENTIMENT_WORDS = {
    "negative": ["下滑", "暴跌", "亏损", "召回", "事故", "裁员", "倒闭", "破产",
                 "投诉", "维权", "起火", "自燃", "刹车失灵", "降价", "退市",
                 "减配", "漏油", "异响", "黑屏", "死机", "续航虚标"],
    "positive": ["增长", "突破", "创新", "领先", "交付", "上市", "融资",
                 "盈利", "获奖", "出口", "新高", "好评", "推荐"],
}


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class NewsCrawler(BaseCrawler):
    name = "news"
    request_interval = 1.0

    sources = [
        {
            "label": "autohome-news",
            "url": "https://www.autohome.com.cn/news/",
            "parser": "_parse_autohome",
        },
        {
            "label": "dongchedi-news",
            "url": "https://www.dongchedi.com/",
            "parser": "_parse_dongchedi",
        },
        {
            "label": "36kr-auto",
            "url": "https://36kr.com/newsflashes",
            "parser": "_parse_36kr",
        },
    ]

    def parse(self, html: str, **kwargs) -> list[dict]:
        return []

    def run(self) -> list[dict]:
        all_rows = []
        for src in self.sources:
            log.info("news: trying %s (%s)", src["label"], src["url"])
            html = self.fetch(src["url"])
            if not html:
                continue

            parser = getattr(self, src["parser"], None)
            if parser:
                rows = parser(html, src["label"])
            else:
                rows = self._parse_generic(html, src["label"])

            for r in rows:
                r["source"] = src["label"]
                r["scraped_at"] = datetime.now().isoformat()
            all_rows.extend(rows)
            log.info("  → %d articles from %s", len(rows), src["label"])
            time.sleep(self.request_interval)

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in all_rows:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)

        log.info("news: %d unique articles", len(unique))
        return unique

    def _parse_autohome(self, html: str, source: str) -> list[dict]:
        """Parse autohome news listing — find article links in any container."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Find all article-like links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 8:
                continue

            # Filter for actual news articles
            if not (href.startswith("//") or "news" in href.lower() or "article" in href.lower()):
                continue

            full_url = href if href.startswith("http") else urljoin("https://www.autohome.com.cn", href)
            if "autohome.com.cn" not in full_url:
                continue

            related = [b for b in BRAND_NAMES if b in text]
            results.append({
                "title": text[:200],
                "url": full_url,
                "summary": "",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "related_brands": related,
            })

        # Limit to 50, prefer ones with brand mentions
        with_brands = [r for r in results if r["related_brands"]]
        without = [r for r in results if not r["related_brands"]]
        return (with_brands + without)[:50]

    def _parse_dongchedi(self, html: str, source: str) -> list[dict]:
        """Parse dongchedi homepage — article listings."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 8:
                continue

            full_url = href if href.startswith("http") else urljoin("https://www.dongchedi.com", href)
            if "dongchedi.com" not in full_url:
                continue

            related = [b for b in BRAND_NAMES if b in text]
            results.append({
                "title": text[:200],
                "url": full_url,
                "summary": "",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "related_brands": related,
            })

        with_brands = [r for r in results if r["related_brands"]]
        return (with_brands + [r for r in results if not r["related_brands"]])[:30]

    def _parse_36kr(self, html: str, source: str) -> list[dict]:
        """Parse 36kr newsflashes."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for item in soup.select(".newsflash-item, .article-item, .item"):
            link = item.find("a")
            if not link:
                continue
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if not text or len(text) < 8:
                continue

            # Only auto-related
            auto_kw = ["车", "新能源", "电动", "电池", "智驾", "自动驾驶", "蔚来", "比亚迪", "特斯拉", "理想", "小鹏", "宁德"]
            if not any(kw in text for kw in auto_kw):
                continue

            full_url = href if href.startswith("http") else urljoin("https://36kr.com", href)
            related = [b for b in BRAND_NAMES if b in text]
            results.append({
                "title": text[:200],
                "url": full_url,
                "summary": "",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "related_brands": related,
            })

        return results[:20]

    def _parse_generic(self, html: str, source: str) -> list[dict]:
        """Generic parser — extract all article-like links."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or len(text) < 10:
                continue

            # Only auto-related content
            auto_kw = ["车", "新能源", "电动", "电池", "智驾", "蔚来", "比亚迪", "特斯拉", "理想", "小鹏", "小米汽车", "零跑"]
            if not any(kw in text for kw in auto_kw):
                continue

            full_url = href if href.startswith("http") else ""
            if not full_url:
                continue

            related = [b for b in BRAND_NAMES if b in text]
            results.append({
                "title": text[:200],
                "url": full_url,
                "summary": "",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "related_brands": related,
            })

        return results[:30]


def classify_sentiment(text: str) -> str:
    """Simple keyword sentiment classifier."""
    text_lower = text.lower()
    neg = sum(1 for w in SENTIMENT_WORDS["negative"] if w in text_lower)
    pos = sum(1 for w in SENTIMENT_WORDS["positive"] if w in text_lower)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def save_news(rows: list[dict]):
    """Save news articles to DB."""
    from pipeline.db import get_db
    db = get_db()
    count = 0
    for r in rows:
        if not r.get("url"):
            continue
        sentiment = classify_sentiment(r.get("title", ""))
        db.upsert_news(
            title=r["title"],
            source=r.get("source", "unknown"),
            url=r["url"],
            published_at=r.get("published_at", ""),
            summary=r.get("summary", ""),
            related_brands=r.get("related_brands", []),
            sentiment=sentiment,
        )
        count += 1
    log.info("news: saved %d/%d articles", count, len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = NewsCrawler()
    rows = crawler.run()
    if rows:
        save_news(rows)
        # Show first few
        for r in rows[:8]:
            brands = ", ".join(r.get("related_brands", [])[:3])
            print(f"  [{brands}] {r['title'][:80]}")
