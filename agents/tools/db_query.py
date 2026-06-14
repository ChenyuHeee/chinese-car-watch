"""
Database query tools for AG2 agents.
"""

import json
import logging

log = logging.getLogger(__name__)


def query_sales(brand_or_model: str, months: int = 6) -> str:
    """Query recent monthly sales for a brand or model.

    Args:
        brand_or_model: brand name or model name to search
        months: number of recent months to return
    """
    from pipeline.db import get_db
    db = get_db()

    # Try exact model first
    rows = db.query("""
        SELECT month, model_name, brand_name, sales_volume, rank, is_nev
        FROM sales_monthly
        WHERE model_name LIKE ?
        ORDER BY month DESC
        LIMIT ?
    """, (f"%{brand_or_model}%", months))

    if not rows:
        # Try brand-level aggregation
        rows = db.query("""
            SELECT month, SUM(sales_volume) as total_sales, COUNT(*) as model_count
            FROM sales_monthly
            WHERE brand_name LIKE ?
            GROUP BY month
            ORDER BY month DESC
            LIMIT ?
        """, (f"%{brand_or_model}%", months))
        if rows:
            return json.dumps(
                [{"month": r["month"], "total_sales": r["total_sales"], "model_count": r["model_count"]}
                 for r in rows],
                ensure_ascii=False, indent=2,
            )

    if rows:
        return json.dumps(
            [{"month": r["month"], "model": r["model_name"], "brand": r["brand_name"],
              "sales": r["sales_volume"], "rank": r["rank"], "is_nev": bool(r["is_nev"])}
             for r in rows],
            ensure_ascii=False, indent=2,
        )

    return json.dumps({"error": f"No sales data found for '{brand_or_model}'"})


def query_news(brand: str, limit: int = 10) -> str:
    """Query recent news articles mentioning a brand.

    Args:
        brand: brand name
        limit: max number of articles
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.get_news_for_brand(brand, limit)
    if not rows:
        return json.dumps({"message": f"No news found for '{brand}'"})
    return json.dumps(
        [{"title": r["title"], "source": r["source"], "date": r["published_at"],
          "sentiment": r["sentiment"], "summary": r["summary"][:200] if r["summary"] else ""}
         for r in rows],
        ensure_ascii=False, indent=2,
    )


def query_sentiment(brand: str, periods: int = 4) -> str:
    """Query social sentiment data for a brand.

    Args:
        brand: brand name
        periods: number of recent periods
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.get_latest_sentiment(brand, periods)
    if not rows:
        return json.dumps({"message": f"No sentiment data for '{brand}'"})
    return json.dumps(
        [{"period": r["period"], "platform": r["platform"],
          "positive": r["positive_ratio"], "negative": r["negative_ratio"],
          "neutral": r["neutral_ratio"], "mentions": r["total_mentions"]}
         for r in rows],
        ensure_ascii=False, indent=2,
    )


def query_supply_chain(brand: str) -> str:
    """Query supplier dependencies for a brand.

    Args:
        brand: brand name
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.get_supplier_dependencies(brand)
    if not rows:
        return json.dumps({"message": f"No supplier data for '{brand}'"})
    return json.dumps(
        [{"supplier": r["supplier_name"], "component": r["component_type"],
          "dependency": r["dependency_level"]}
         for r in rows],
        ensure_ascii=False, indent=2,
    )


def query_latest_ranking(top_n: int = 20) -> str:
    """Query the latest monthly sales ranking.

    Args:
        top_n: number of top models to return
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.get_latest_sales()
    if not rows:
        return json.dumps({"error": "No sales data available"})
    return json.dumps(
        [{"rank": r["rank"], "model": r["model_name"], "brand": r["brand_name"],
          "sales": r["sales_volume"], "is_nev": bool(r["is_nev"]),
          "price": r["price_range"]}
         for r in rows[:top_n]],
        ensure_ascii=False, indent=2,
    )


def query_stock(brand: str, days: int = 30) -> str:
    """Query recent stock price data for a listed auto company.

    Args:
        brand: brand name (e.g. '比亚迪', '蔚来')
        days: number of recent trading days
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.query("""
        SELECT trade_date, close, open, high, low, volume
        FROM stock_prices WHERE brand=? OR stock_code IN (
            SELECT stock_code FROM stock_prices WHERE brand=?
        )
        ORDER BY trade_date DESC LIMIT ?
    """, (brand, brand, days))
    if not rows:
        return json.dumps({"message": f"No stock data for '{brand}'"})
    # Compute trend
    prices = [r["close"] for r in reversed(rows)]
    if len(prices) >= 2:
        change = (prices[-1] - prices[0]) / prices[0] * 100
        trend = f"{change:+.1f}% over {len(prices)} days"
    else:
        trend = "insufficient data"
    return json.dumps({
        "brand": brand,
        "latest_close": rows[0]["close"],
        "latest_date": rows[0]["trade_date"],
        "trend": trend,
        "recent": [{"date": r["trade_date"], "close": r["close"], "volume": r["volume"]}
                    for r in rows[:10]],
    }, ensure_ascii=False, indent=2)


def query_financial(brand: str) -> str:
    """Query latest financial report data for a company.

    Args:
        brand: brand name (e.g. '比亚迪', '蔚来')
    Returns revenue, profit, margins, ROE, debt ratio, etc.
    """
    from pipeline.db import get_db
    db = get_db()
    rows = db.query("""
        SELECT report_date, revenue, revenue_yoy, net_profit, net_profit_yoy,
               gross_margin, net_margin, roe, debt_ratio, eps, ocf_per_share
        FROM financial_reports WHERE brand=?
        ORDER BY report_date DESC LIMIT 4
    """, (brand,))
    if not rows:
        return json.dumps({"message": f"No financial data for '{brand}'"})
    return json.dumps([{
        "report_date": r["report_date"][:10] if r["report_date"] else "",
        "revenue_亿": r["revenue"],
        "revenue_yoy": f"{r['revenue_yoy']}%",
        "net_profit_亿": r["net_profit"],
        "gross_margin": f"{r['gross_margin']}%",
        "net_margin": f"{r['net_margin']}%",
        "roe": f"{r['roe']}%",
        "debt_ratio": f"{r['debt_ratio']}%",
    } for r in rows], ensure_ascii=False, indent=2)


# AG2 tool registry
DB_TOOLS = [
    query_sales,
    query_news,
    query_sentiment,
    query_supply_chain,
    query_latest_ranking,
    query_stock,
    query_financial,
]
