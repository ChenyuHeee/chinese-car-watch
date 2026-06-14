"""
Stock price crawler using akshare.
Fetches A-share and US-listed Chinese auto stocks.
"""

import logging
from datetime import datetime
from typing import Optional

import akshare as ak

from crawlers.base import BaseCrawler

log = logging.getLogger(__name__)

# Listed Chinese auto companies
STOCKS = [
    # A-shares
    {"code": "002594", "market": "a", "brand": "比亚迪", "label": "BYD A"},
    {"code": "601127", "market": "a", "brand": "问界", "label": "Seres"},
    {"code": "601238", "market": "a", "brand": "广汽埃安", "label": "GAC Group"},
    {"code": "000625", "market": "a", "brand": "长安汽车", "label": "Changan"},
    # US/HK listed
    {"code": "106.NIO", "market": "us", "brand": "蔚来", "label": "NIO US"},
    {"code": "105.LI", "market": "us", "brand": "理想", "label": "Li Auto US"},
    {"code": "108.XPEV", "market": "us", "brand": "小鹏", "label": "XPeng US"},
    {"code": "107.ZK", "market": "us", "brand": "极氪", "label": "Zeekr US"},
    {"code": "103.TSLA", "market": "us", "brand": "特斯拉", "label": "Tesla US"},
]


class StockCrawler(BaseCrawler):
    name = "stock"
    request_interval = 2.0

    def run(self) -> list[dict]:
        """Fetch stock data for all tracked companies."""
        all_rows = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = "20260101"

        for stock in STOCKS:
            try:
                log.info("stock: fetching %s (%s)", stock["label"], stock["code"])
                if stock["market"] == "a":
                    df = ak.stock_zh_a_hist(
                        symbol=stock["code"], period="daily",
                        start_date=start_date, end_date=end_date, adjust="qfq",
                    )
                else:
                    df = ak.stock_us_hist(
                        symbol=stock["code"], period="daily",
                        start_date=start_date, end_date=end_date, adjust="qfq",
                    )

                for _, row in df.iterrows():
                    all_rows.append({
                        "stock_code": stock["code"],
                        "brand": stock["brand"],
                        "trade_date": str(row.get("日期", "")),
                        "open": float(row.get("开盘", 0) or 0),
                        "high": float(row.get("最高", 0) or 0),
                        "low": float(row.get("最低", 0) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                    })
                log.info("  → %d days for %s", len(df), stock["label"])

            except Exception as e:
                log.warning("stock: failed %s (%s): %s", stock["label"], stock["code"], e)

        # Attach metadata
        now = datetime.now().isoformat()
        for r in all_rows:
            r["scraped_at"] = now

        log.info("stock: %d total rows", len(all_rows))
        return all_rows


def save_stock_data(rows: list[dict]):
    """Save stock data to DB."""
    from pipeline.db import get_db
    db = get_db()
    for r in rows:
        db.execute("""
            INSERT OR REPLACE INTO stock_prices (stock_code, trade_date, open, high, low, close, volume, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            r["stock_code"], r["trade_date"],
            r["open"], r["high"], r["low"], r["close"], r["volume"],
        ))
    log.info("stock: saved %d rows to DB", len(rows))


# ── CLI ──
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = StockCrawler()
    rows = crawler.run()
    if rows:
        save_stock_data(rows)
        # Quick summary
        from collections import defaultdict
        latest = defaultdict(list)
        for r in rows:
            latest[r["brand"]].append(r["close"])
        for brand, prices in latest.items():
            print(f"  {brand}: latest close {prices[-1]:.2f}")
