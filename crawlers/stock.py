"""
Stock price crawler via Sina Finance API.
Works from Alibaba Cloud ECS (unlike akshare which hits blocked Eastmoney endpoints).
"""

import logging
import re
import time
from datetime import datetime

import requests

from crawlers.base import BaseCrawler

log = logging.getLogger(__name__)

# Sina stock code format
# A-share: sh600000, sz000001
# US: gb_tsla, gb_nio
STOCKS = [
    {"sina_code": "sz002594", "code": "002594.SZ", "brand": "比亚迪", "market": "a"},
    {"sina_code": "sh601127", "code": "601127.SH", "brand": "问界", "market": "a"},
    {"sina_code": "sh601238", "code": "601238.SH", "brand": "广汽", "market": "a"},
    {"sina_code": "sz000625", "code": "000625.SZ", "brand": "长安汽车", "market": "a"},
    {"sina_code": "sh600104", "code": "600104.SH", "brand": "上汽集团", "market": "a"},
    {"sina_code": "sz000800", "code": "000800.SZ", "brand": "一汽", "market": "a"},
    {"sina_code": "gb_nio", "code": "NIO", "brand": "蔚来", "market": "us"},
    {"sina_code": "gb_li", "code": "LI", "brand": "理想", "market": "us"},
    {"sina_code": "gb_xpev", "code": "XPEV", "brand": "小鹏", "market": "us"},
    {"sina_code": "gb_zk", "code": "ZK", "brand": "极氪", "market": "us"},
    {"sina_code": "gb_tsla", "code": "TSLA", "brand": "特斯拉", "market": "us"},
]

SINA_API = "https://hq.sinajs.cn/list={codes}"
HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


class StockCrawler(BaseCrawler):
    name = "stock"
    request_interval = 0.5

    def parse(self, html: str, **kwargs) -> list[dict]:
        return []

    def run(self) -> list[dict]:
        """Fetch latest stock data via Sina API."""
        codes = ",".join(s["sina_code"] for s in STOCKS)
        url = SINA_API.format(codes=codes)

        log.info("stock: fetching %d stocks via Sina API", len(STOCKS))
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "gb2312"
            text = resp.text
        except Exception as e:
            log.error("stock: API request failed: %s", e)
            return []

        results = []
        today = datetime.now().strftime("%Y-%m-%d")

        for line in text.strip().split("\n"):
            if not line.strip():
                continue

            # Parse Sina's var lines
            m = re.match(r'var hq_str_(\w+)="(.+)"', line)
            if not m:
                continue

            code = m.group(1)
            fields = m.group(2).split(",")

            # Find matching stock
            stock = next((s for s in STOCKS if s["sina_code"] == code), None)
            if not stock or len(fields) < 4:
                continue

            try:
                if stock["market"] == "a":
                    # A-share fields: name, open, prev_close, price, high, low, ...
                    name = fields[0]
                    open_p = float(fields[1]) if fields[1] else 0
                    prev_close = float(fields[2]) if fields[2] else 0
                    price = float(fields[3]) if fields[3] else 0
                    high = float(fields[4]) if fields[4] else 0
                    low = float(fields[5]) if fields[5] else 0
                    volume = float(fields[8]) if len(fields) > 8 and fields[8] else 0
                else:
                    # US stock fields: name, price, change_pct, ...
                    name = fields[0]
                    price = float(fields[1]) if fields[1] else 0
                    open_p = float(fields[5]) if len(fields) > 5 and fields[5] else 0
                    high = float(fields[6]) if len(fields) > 6 and fields[6] else 0
                    low = float(fields[7]) if len(fields) > 7 and fields[7] else 0
                    prev_close = price  # approximate
                    volume = 0

                results.append({
                    "stock_code": stock["code"],
                    "brand": stock["brand"],
                    "trade_date": today,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": volume,
                })
            except (ValueError, IndexError) as e:
                log.warning("stock: parse error for %s: %s", stock["brand"], e)

        log.info("stock: %d prices fetched", len(results))
        return results


def save_stock_data(rows: list[dict]):
    """Save stock data to DB."""
    from pipeline.db import get_db
    db = get_db()
    for r in rows:
        db.execute("""
            INSERT OR REPLACE INTO stock_prices
            (stock_code, trade_date, open, high, low, close, volume, scraped_at, brand)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """, (
            r["stock_code"], r["trade_date"],
            r["open"], r["high"], r["low"], r["close"], r["volume"],
            r["brand"],
        ))
    log.info("stock: saved %d rows to DB", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = StockCrawler()
    rows = crawler.run()
    if rows:
        save_stock_data(rows)
        for r in rows:
            print(f"  {r['brand']}: {r['close']:.2f} ({r['stock_code']})")
