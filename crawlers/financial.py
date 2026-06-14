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
        revenue_cols = {"营业总收入", "净利润"}
        for _, row in df.iterrows():
            r = {
                "brand": co["brand"], "symbol": co["symbol"], "market": "a",
                "report_date": str(row.get("报告期", "")),
                "revenue": _parse_revenue(row.get("营业总收入")),
                "revenue_yoy": _parse_pct_or_num(row.get("营业总收入同比增长率")),
                "net_profit": _parse_revenue(row.get("净利润")),
                "net_profit_yoy": _parse_pct_or_num(row.get("净利润同比增长率")),
                "gross_margin": _parse_pct_or_num(row.get("销售毛利率")),
                "net_margin": _parse_pct_or_num(row.get("销售净利率")),
                "roe": _parse_pct_or_num(row.get("净资产收益率")),
                "debt_ratio": _parse_pct_or_num(row.get("资产负债率")),
                "eps": _parse_pct_or_num(row.get("基本每股收益")),
                "ocf_per_share": _parse_pct_or_num(row.get("每股经营现金流")),
            }
            rows.append(r)
        return rows

    def _fetch_us(self, co: dict) -> list[dict]:
        """Fetch US-listed financials via Eastmoney."""
        df = ak.stock_financial_us_analysis_indicator_em(
            symbol=co["symbol"], indicator="累计季报"
        )
        rows = []
        for _, row in df.iterrows():
            r = {
                "brand": co["brand"], "symbol": co["symbol"], "market": "us",
                "report_date": str(row.get("REPORT_DATE", "")),
                "revenue": _parse_revenue(row.get("OPERATE_INCOME")),
                "revenue_yoy": _parse_pct_or_num(row.get("OPERATE_INCOME_YOY")),
                "net_profit": _parse_revenue(row.get("PARENT_HOLDER_NETPROFIT")),
                "net_profit_yoy": _parse_pct_or_num(row.get("PARENT_HOLDER_NETPROFIT_YOY")),
                "gross_margin": _parse_pct_or_num(row.get("GROSS_PROFIT_RATIO")),
                "net_margin": _parse_pct_or_num(row.get("NET_PROFIT_RATIO")),
                "roe": _parse_pct_or_num(row.get("ROE_AVG")),
                "debt_ratio": _parse_pct_or_num(row.get("DEBT_ASSET_RATIO")),
                "eps": _parse_pct_or_num(row.get("BASIC_EPS")),
                "ocf_per_share": 0,
            }
            rows.append(r)
        return rows


def _parse_pct_or_num(val) -> float:
    """Parse akshare values: NaN, '155.11亿', '23.30%', '1.7100', numeric."""
    import pandas as pd
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, str):
        val = val.strip()
        # "155.11亿" → 155.11 (in 亿)
        if "亿" in val:
            try:
                return float(val.replace("亿", "").replace(",", ""))
            except ValueError:
                return 0.0
        # "23.30%" → 23.30
        val = val.replace("%", "").replace(",", "")
        try:
            return float(val)
        except ValueError:
            return 0.0
    return float(val) if val else 0.0


def _parse_revenue(val) -> float:
    """Parse revenue values. A-share returns '1502.25亿', US returns raw 元."""
    import pandas as pd
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, str):
        val = val.strip()
        if "亿" in val:
            try:
                return float(val.replace("亿", "").replace(",", ""))
            except ValueError:
                return 0.0
        try:
            return float(val.replace(",", "")) / 1e8  # raw 元 → 亿
        except ValueError:
            return 0.0
    # US stocks return raw 元 (e.g., 5.2e10)
    if isinstance(val, (int, float)) and abs(val) > 1e8:
        return val / 1e8
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
        for brand in sorted(set(r["brand"] for r in rows)):
            brand_rows = [r for r in rows if r["brand"] == brand]
            latest = max(brand_rows, key=lambda r: str(r.get("report_date", "")))
            rev = latest.get("revenue", 0)
            margin = latest.get("gross_margin", 0)
            debt = latest.get("debt_ratio", 0)
            profit = latest.get("net_profit", 0)
            print(f"  {brand}: rev={rev:.0f} margin={margin:.1f}% profit={profit:.0f} debt={debt:.1f}%")
