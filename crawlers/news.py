"""
Auto industry news crawler.
Scrapes recent news from multiple Chinese auto media sources.
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

# Known auto brands for entity extraction
BRAND_NAMES = [
    "比亚迪", "特斯拉", "蔚来", "小鹏", "理想", "零跑", "极氪", "问界",
    "小米汽车", "鸿蒙智行", "深蓝", "方程豹", "腾势", "阿维塔", "岚图",
    "智己", "乐道", "银河", "埃安", "五菱", "吉利", "长城", "长安",
    "奇瑞", "大众", "丰田", "本田", "日产", "奔驰", "宝马", "奥迪",
    "别克", "福特", "现代", "起亚", "宁德时代", "华为", "地平线",
]


class NewsCrawler(BaseCrawler):
    name = "news"
    request_interval = 1.5

    sources = [
        {
            "label": "autohome-news",
            "url": "https://www.autohome.com.cn/news/",
        },
    ]

    def parse(self, html: str, **kwargs) -> list[dict]:
        """Parse autohome news listing."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for item in soup.select(".article li, .news-list li, .article-item")[:20]:
            link = item.find("a")
            if not link:
                continue
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            full_url = href if href.startswith("http") else urljoin("https://www.autohome.com.cn", href)

            # Try to get summary
            summary_el = item.find(["p", "span"], class_=re.compile(r"summary|desc|intro"))
            summary = summary_el.get_text(strip=True)[:300] if summary_el else ""

            # Find mentioned brands
            related = [b for b in BRAND_NAMES if b in title]

            results.append({
                "title": title,
                "url": full_url,
                "summary": summary,
                "source": "autohome",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "related_brands": related,
            })

        return results


def fetch_article_text(url: str, max_chars: int = 3000) -> str:
    """Fetch full article text."""
    try:
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8" if resp.apparent_encoding is None else resp.apparent_encoding

        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        article = soup.find("article") or soup.find(class_=re.compile(r"article|content|main"))
        if article:
            text = article.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 20]
        text = "\n".join(lines)
        return text[:max_chars]
    except Exception as e:
        log.warning("fetch_article_text failed for %s: %s", url, e)
        return ""


def save_news(rows: list[dict]):
    """Save news articles to DB with auto-sentiment classification."""
    from pipeline.db import get_db
    db = get_db()

    # Simple keyword-based sentiment
    negative_words = ["下滑", "暴跌", "亏损", "召回", "事故", "裁员", "倒闭", "破产",
                      "投诉", "维权", "起火", "自燃", "刹车失灵", "降价", "退市"]
    positive_words = ["增长", "突破", "创新", "领先", "交付", "上市", "融资",
                      "盈利", "获奖", "出口", "突破", "新高"]

    count = 0
    for r in rows:
        text = (r.get("title", "") + " " + r.get("summary", "")).lower()
        neg = sum(1 for w in negative_words if w in text)
        pos = sum(1 for w in positive_words if w in text)
        sentiment = "negative" if neg > pos else ("positive" if pos > neg else "neutral")

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

    log.info("news: saved %d articles to DB", count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = NewsCrawler()
    rows = crawler.run()
    if rows:
        save_news(rows)
        for r in rows[:5]:
            brands = ", ".join(r.get("related_brands", [])[:3])
            print(f"  {r['title'][:60]}... [{brands}]")
