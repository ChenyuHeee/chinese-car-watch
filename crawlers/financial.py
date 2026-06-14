"""
Financial report crawler via akshare.
Fetches quarterly financials for listed Chinese auto companies.
Uses THS (同花顺) API for A-shares, Eastmoney for US/HK stocks.
"""

import logging
from datetime import datetime

import akshare as ak

from crawlers.base import BaseCrawler

log = logging.getLogger(__name__)

# Tracked companies with their akshare symbols
COMPANIES = [
    # A-share (同花顺)
    {"symbol": "002594", "market": "a", "brand": "比亚迪"},
    {"symbol": "601127", "market": "a", "brand": "问界"},
    {"symbol": "601238", "market": "a", "brand": "广汽"},
    {"symbol": "000625", "market": "a", "brand": "长安汽车"},
    {"symbol": "600104", "market": "a", "brand": "上汽集团"},
    {"symbol": "000800", "market": "a", "brand": "一汽"},
    # US-listed (Eastmoney)
    {"symbol": "NIO", "market": "us", "brand": "蔚来"},
    {"symbol": "LI", "market": "us", "brand": "理想"},
    {"symbol": "XPEV", "market": "us", "brand": "小鹏"},
    {"symbol": "ZK", "market": "us", "brand": "极氪"},
    {"symbol": "TSLA", "market": "us", "brand": "特斯拉"},
]


class FinancialCrawler(BaseCrawler):
    name = "financial"
    request_interval = 1.0

    def parse(self, html: str, **kwargs) -> list[dict]:
        return []

    def run(self) -> list[dict]:
        all_rows = []

        for co in COMPANIES:
            try:
                if co["market"] == "a":
                    rows = self._fetch_a_share(co)
                else:
                    rows = self._fetch_us(co)
                all_rows.extend(rows)
                log.info("financial: %s — %d quarters", co["brand"], len(rows))
            except Exception as e:
                log.warning("financial: %s failed: %s", co["brand"], e)

        now = datetime.now().isoformat()
        for r in all_rows:
            r["scraped_at"] = now

        log.info("financial: %d total rows", len(all_rows))
        return all_rows

    def _fetch_a_share(self, co: dict) -> list[dict]:
        """Fetch A-share financials via THS."""
        df = ak.stock_financial_abstract_ths(symbol=co["symbol"], indicator="按报告期")
        rows = []
        key_cols = {
            "报告期": "report_date",
            "营业总收入": "revenue",
            "营业总收入同比增长率": "revenue_yoy",
            "净利润": "net_profit",
            "净利润同比增长率": "net_profit_yoy",
            "销售毛利率": "gross_margin",
            "销售净利率": "net_margin",
            "净资产收益率": "roe",
            "资产负债率": "debt_ratio",
            "基本每股收益": "eps",
            "每股经营现金流": "ocf_per_share",
        }
        for _, row in df.iterrows():
            r = {"brand": co["brand"], "symbol": co["symbol"], "market": "a"}
            for cn, en in key_cols.items():
                val = row.get(cn)
                r[en] = _parse_pct_or_num(val)
            rows.append(r)
        return rows

    def _fetch_us(self, co: dict) -> list[dict]:
        """Fetch US-listed financials via Eastmoney."""
        df = ak.stock_financial_us_analysis_indicator_em(
            symbol=co["symbol"], indicator="累计季报"
        )
        rows = []
        key_cols = {
            "REPORT_DATE": "report_date",
            "OPERATE_INCOME": "revenue",
            "OPERATE_INCOME_YOY": "revenue_yoy",
            "GROSS_PROFIT_RATIO": "gross_margin",
            "NET_PROFIT_RATIO": "net_margin",
            "PARENT_HOLDER_NETPROFIT": "net_profit",
            "PARENT_HOLDER_NETPROFIT_YOY": "net_profit_yoy",
            "ROE_AVG": "roe",
            "DEBT_ASSET_RATIO": "debt_ratio",
            "BASIC_EPS": "eps",
        }
        for _, row in df.iterrows():
            r = {"brand": co["brand"], "symbol": co["symbol"], "market": "us"}
            for cn, en in key_cols.items():
                val = row.get(cn)
                r[en] = _parse_pct_or_num(val)
            rows.append(r)
        return rows


def _parse_pct_or_num(val) -> float:
    """Parse akshare values: handle NaN, percentage strings, numeric."""
    import pandas as pd
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, str):
        val = val.replace("%", "").replace("亿", "").replace(",", "")
        try:
            return float(val)
        except ValueError:
            return 0.0
    return float(val) if val else 0.0


def save_financials(rows: list[dict]):
    """Save financial data to a dedicated DB table."""
    from pipeline.db import get_db
    db = get_db()

    # Ensure table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS financial_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            symbol TEXT,
            market TEXT,
            report_date TEXT NOT NULL,
            revenue REAL,
            revenue_yoy REAL,
            net_profit REAL,
            net_profit_yoy REAL,
            gross_margin REAL,
            net_margin REAL,
            roe REAL,
            debt_ratio REAL,
            eps REAL,
            ocf_per_share REAL,
            scraped_at TEXT DEFAULT (datetime('now')),
            UNIQUE(brand, report_date)
        )
    """)

    for r in rows:
        db.execute("""
            INSERT OR REPLACE INTO financial_reports
            (brand, symbol, market, report_date, revenue, revenue_yoy,
             net_profit, net_profit_yoy, gross_margin, net_margin,
             roe, debt_ratio, eps, ocf_per_share, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            r["brand"], r["symbol"], r["market"], r["report_date"],
            r.get("revenue", 0), r.get("revenue_yoy", 0),
            r.get("net_profit", 0), r.get("net_profit_yoy", 0),
            r.get("gross_margin", 0), r.get("net_margin", 0),
            r.get("roe", 0), r.get("debt_ratio", 0),
            r.get("eps", 0), r.get("ocf_per_share", 0),
        ))

    log.info("financial: saved %d rows to DB", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    crawler = FinancialCrawler()
    rows = crawler.run()
    if rows:
        save_financials(rows)
        for brand in set(r["brand"] for r in rows):
            latest = max(r for r in rows if r["brand"] == brand)
            print(f"  {brand}: rev={latest.get('revenue',0):.0f} margin={latest.get('gross_margin',0):.1f}% debt={latest.get('debt_ratio',0):.1f}%")
