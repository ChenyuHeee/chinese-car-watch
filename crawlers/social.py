"""
Social sentiment crawler.
Scrapes user reviews and comments from auto community platforms.

Currently: keyword-based sentiment on news + a simple scoring heuristic.
Can be upgraded with real social media APIs (Weibo, Zhihu) or ML models.
"""

import json
import logging
import re
from datetime import datetime
from collections import Counter

import requests
from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler

log = logging.getLogger(__name__)

# Tracked brands for sentiment analysis
TRACKED_BRANDS = [
    "比亚迪", "特斯拉", "蔚来", "小鹏", "理想", "零跑", "极氪", "问界",
    "小米汽车", "深蓝", "方程豹", "腾势", "阿维塔", "岚图", "智己",
    "乐道", "银河", "埃安", "吉利", "长城", "长安", "奇瑞",
]

TARGET_PLATFORMS = ["autohome", "dongchedi"]

# Keyword sentiment lexicon
NEGATIVE_WORDS = [
    "下滑", "暴跌", "亏损", "召回", "事故", "裁员", "倒闭", "破产",
    "投诉", "维权", "起火", "自燃", "刹车失灵", "降价", "退市", "减配",
    "漏油", "异响", "黑屏", "死机", "续航虚标", "售后差", "等车太久",
]
POSITIVE_WORDS = [
    "增长", "突破", "创新", "领先", "交付", "上市", "融资", "盈利",
    "获奖", "出口", "新高", "好评", "推荐", "性价比", "颜值", "智能",
    "好开", "舒适", "省油", "续航长", "充电快", "服务好", "保值",
]


def analyze_text_sentiment(text: str) -> tuple[float, float, list[str]]:
    """Simple keyword-based sentiment analysis.
    Returns (positive_ratio, negative_ratio, top_keywords).
    """
    text_lower = text.lower()
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    total = pos_count + neg_count
    if total == 0:
        return 0.33, 0.33, []

    pos_ratio = pos_count / (pos_count + neg_count + 1)
    neg_ratio = neg_count / (pos_count + neg_count + 1)
    neutral_ratio = 1.0 - pos_ratio - neg_ratio

    # Extract top keywords
    keyword_counts = Counter()
    for w in POSITIVE_WORDS + NEGATIVE_WORDS:
        if w in text_lower:
            keyword_counts[w] = text_lower.count(w)
    top_kw = [w for w, _ in keyword_counts.most_common(10)]

    return round(pos_ratio, 3), round(neg_ratio, 3), top_kw


class SocialSentimentCrawler(BaseCrawler):
    name = "social"
    request_interval = 1.0

    sources = [
        {
            "label": "dongchedi-hot",
            "url": "https://www.dongchedi.com/",
        },
    ]

    def parse(self, html: str, **kwargs) -> list[dict]:
        """Parse dongchedi homepage for trending content."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Find article links and titles
        for item in soup.select("a[href]"):
            href = item.get("href", "")
            text = item.get_text(strip=True)
            if not text or len(text) < 5:
                continue

            # Check if it's an article about a tracked brand
            for brand in TRACKED_BRANDS:
                if brand in text:
                    full_url = href if href.startswith("http") else f"https://www.dongchedi.com{href}"
                    results.append({
                        "title": text[:200],
                        "url": full_url,
                        "brand": brand,
                        "platform": "dongchedi",
                    })
                    break

        return results[:30]


def compute_brand_sentiment(brand: str, articles: list[dict]) -> dict:
    """Aggregate sentiment for a brand from collected articles."""
    if not articles:
        return {"brand": brand, "total_mentions": 0}

    total_pos = 0.0
    total_neg = 0.0
    all_keywords = Counter()

    for a in articles:
        pos, neg, kws = analyze_text_sentiment(a.get("title", ""))
        total_pos += pos
        total_neg += neg
        for kw in kws:
            all_keywords[kw] += 1

    n = len(articles)
    return {
        "brand": brand,
        "positive_ratio": round(total_pos / n, 3),
        "negative_ratio": round(total_neg / n, 3),
        "neutral_ratio": round(1.0 - (total_pos + total_neg) / n, 3),
        "total_mentions": n,
        "top_keywords": [w for w, _ in all_keywords.most_common(10)],
    }


def save_sentiment(results: list[dict], period: str = None):
    """Save sentiment data to DB."""
    if period is None:
        period = datetime.now().strftime("%Y%m")
    from pipeline.db import get_db
    db = get_db()

    # Group by brand
    brand_articles = {}
    for r in results:
        brand = r.get("brand", "unknown")
        brand_articles.setdefault(brand, []).append(r)

    for brand, articles in brand_articles.items():
        sentiment = compute_brand_sentiment(brand, articles)
        db.upsert_sentiment(
            brand_name=brand,
            period=period,
            platform="dongchedi",
            positive_ratio=sentiment["positive_ratio"],
            negative_ratio=sentiment["negative_ratio"],
            neutral_ratio=sentiment["neutral_ratio"],
            total_mentions=sentiment["total_mentions"],
            top_keywords=sentiment["top_keywords"],
        )

    log.info("social: saved sentiment for %d brands", len(brand_articles))


def run_news_sentiment_fallback():
    """Fallback: compute sentiment from news articles already in DB."""
    from pipeline.db import get_db
    db = get_db()
    period = datetime.now().strftime("%Y%m")

    for brand in TRACKED_BRANDS:
        rows = db.get_news_for_brand(brand, limit=30)
        if not rows:
            continue

        total_pos = total_neg = 0.0
        all_kw = Counter()
        for r in rows:
            text = (r.get("title", "") + " " + r.get("summary", ""))
            pos, neg, kws = analyze_text_sentiment(text)
            total_pos += pos
            total_neg += neg
            for kw in kws:
                all_kw[kw] += 1

        n = len(rows)
        db.upsert_sentiment(
            brand_name=brand, period=period, platform="news_aggregate",
            positive_ratio=round(total_pos / n, 3),
            negative_ratio=round(total_neg / n, 3),
            neutral_ratio=round(1.0 - (total_pos + total_neg) / n, 3),
            total_mentions=n,
            top_keywords=[w for w, _ in all_kw.most_common(10)],
        )

    log.info("social: news-based sentiment computed for %d brands", len(TRACKED_BRANDS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Try scraping
    crawler = SocialSentimentCrawler()
    rows = crawler.run()
    if rows:
        save_sentiment(rows)
        print(f"Scraped {len(rows)} items")
    else:
        print("Scraping returned no results, running news fallback...")
        run_news_sentiment_fallback()
