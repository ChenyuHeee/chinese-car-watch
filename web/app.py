"""
AutoInsight Web API — deployed at insight.hechenyu.xin/auto
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="AutoInsight", version="0.1.0")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

STATIC = Path(__file__).parent / "static"
TEMPLATES = Path(__file__).parent / "templates"

app.mount("/auto/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/auto/brand/{brand_name}")
async def brand_page(brand_name: str):
    """Brand detail page."""
    template_path = TEMPLATES / "brand.html"
    if template_path.exists():
        html = template_path.read_text(encoding="utf-8")
        return HTMLResponse(html.replace("{{brand}}", brand_name))
    return HTMLResponse(f"<h1>{brand_name}</h1>")


@app.get("/auto")
@app.get("/auto/")
async def dashboard():
    """Main dashboard page."""
    index_path = STATIC / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AutoInsight</h1><p>Dashboard coming soon.</p>")


@app.get("/auto/api/health")
async def health_check():
    """Health check endpoint."""
    from pipeline.db import get_db
    db = get_db()
    latest = db.query_one("SELECT month FROM sales_monthly ORDER BY month DESC LIMIT 1")
    return {
        "status": "ok",
        "version": "0.1.0",
        "latest_data_month": latest["month"] if latest else None,
        "server_time": datetime.now().isoformat(),
    }


@app.get("/auto/api/bvs/{brand}")
async def get_bvs(brand: str):
    """Get BVS rating for a specific brand."""
    from pipeline.db import get_db
    db = get_db()
    result = db.get_latest_agent_result("bvs", brand)
    if not result:
        raise HTTPException(status_code=404, detail=f"No BVS rating for '{brand}'")
    return {
        "brand": result["target_name"],
        "rating": result["score_label"],
        "score": result["score"],
        "date": result["run_date"],
        "details": json.loads(result["details"]) if result["details"] else {},
    }


@app.get("/auto/api/bvs")
async def list_bvs(
    limit: int = Query(default=20, le=100),
    min_score: float = Query(default=None),
):
    """List all BVS ratings, optionally filtered."""
    from pipeline.db import get_db
    db = get_db()
    rows = db.query("""
        SELECT target_name, score_label, score, run_date
        FROM agent_results WHERE product='bvs'
        ORDER BY run_date DESC, score ASC
        LIMIT ?
    """, (limit,))
    results = [
        {"brand": r["target_name"], "rating": r["score_label"],
         "score": r["score"], "date": r["run_date"]}
        for r in rows
    ]
    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]
    return {"count": len(results), "results": results}


@app.get("/auto/api/scem")
async def list_scem(limit: int = Query(default=20, le=100)):
    """List SCEM supply chain exposure scores."""
    from pipeline.db import get_db
    db = get_db()
    rows = db.query("""
        SELECT target_name, score_label, score, run_date, details
        FROM agent_results WHERE product='scem'
        ORDER BY run_date DESC, score DESC
        LIMIT ?
    """, (limit,))
    return {
        "count": len(rows),
        "results": [{"brand": r["target_name"], "risk": r["score_label"],
                      "score": r["score"], "date": r["run_date"]} for r in rows],
    }


@app.get("/auto/api/tdg")
async def list_tdg(limit: int = Query(default=20, le=100)):
    """List TDG tech delivery gap scores."""
    from pipeline.db import get_db
    db = get_db()
    rows = db.query("""
        SELECT target_name, score_label, score, run_date, details
        FROM agent_results WHERE product='tdg'
        ORDER BY run_date DESC, score DESC
        LIMIT ?
    """, (limit,))
    return {
        "count": len(rows),
        "results": [{"brand": r["target_name"], "gap": r["score_label"],
                      "delivery": r["score"], "date": r["run_date"]} for r in rows],
    }


@app.get("/auto/api/all-products")
async def all_products():
    """Return all product results in a single call (for dashboard)."""
    from pipeline.db import get_db
    db = get_db()

    # Get latest run date for each product
    bvs = db.query("""
        SELECT target_name, score_label, score
        FROM agent_results WHERE product='bvs'
        AND run_date = (SELECT MAX(run_date) FROM agent_results WHERE product='bvs')
        ORDER BY score DESC
    """)
    scem = db.query("""
        SELECT target_name, score_label, score
        FROM agent_results WHERE product='scem'
        AND run_date = (SELECT MAX(run_date) FROM agent_results WHERE product='scem')
        ORDER BY score DESC
    """)
    tdg = db.query("""
        SELECT target_name, score_label, score
        FROM agent_results WHERE product='tdg'
        AND run_date = (SELECT MAX(run_date) FROM agent_results WHERE product='tdg')
        ORDER BY score DESC
    """)

    return {
        "bvs": [{"brand": r["target_name"], "rating": r["score_label"],
                  "score": r["score"]} for r in bvs],
        "scem": [{"brand": r["target_name"], "risk": r["score_label"],
                   "exposure": r["score"]} for r in scem],
        "tdg": [{"brand": r["target_name"], "gap": r["score_label"],
                  "delivery": r["score"]} for r in tdg],
    }


@app.get("/auto/api/brand/{brand_name}")
async def brand_detail(brand_name: str):
    """Full brand dossier: BVS, sales trend, financials, SCEM, TDG, news, sentiment."""
    from pipeline.db import get_db
    db = get_db()

    # BVS — latest
    bvs = db.query_one("""
        SELECT score_label, score, run_date, details
        FROM agent_results WHERE product='bvs' AND target_name=?
        ORDER BY run_date DESC LIMIT 1
    """, (brand_name,))

    # SCEM
    scem = db.query_one("""
        SELECT score_label, score, run_date
        FROM agent_results WHERE product='scem' AND target_name=?
        ORDER BY run_date DESC LIMIT 1
    """, (brand_name,))

    # TDG
    tdg = db.query_one("""
        SELECT score_label, score, run_date
        FROM agent_results WHERE product='tdg' AND target_name=?
        ORDER BY run_date DESC LIMIT 1
    """, (brand_name,))

    # Sales trend — last 3 months, all models
    sales_rows = db.query("""
        SELECT month, model_name, sales_volume, rank
        FROM sales_monthly WHERE brand_name LIKE ?
        ORDER BY month DESC, rank ASC
        LIMIT 50
    """, (f"%{brand_name}%",))

    # Aggregate by month
    from collections import defaultdict
    monthly_totals = defaultdict(int)
    monthly_models = defaultdict(list)
    for r in sales_rows:
        monthly_totals[r["month"]] += r["sales_volume"]
        monthly_models[r["month"]].append({
            "model": r["model_name"],
            "sales": r["sales_volume"],
            "rank": r["rank"],
        })

    sales_trend = [
        {"month": m, "total": monthly_totals[m], "models": monthly_models[m][:5]}
        for m in sorted(monthly_totals.keys(), reverse=True)[:6]
    ]
    # Fill with any data from other brands if one brand has multiple rows
    latest_month_sales = sum(r["sales_volume"] for r in sales_rows
                            if r["month"] == (sales_rows[0]["month"] if sales_rows else ""))

    # Financials — latest quarter
    fin = db.query_one("""
        SELECT * FROM financial_reports WHERE brand=?
        ORDER BY report_date DESC LIMIT 1
    """, (brand_name,))

    # Recent news
    news = db.query("""
        SELECT title, source, published_at, sentiment, summary
        FROM news_articles WHERE related_brands LIKE ?
        ORDER BY published_at DESC LIMIT 5
    """, (f"%{brand_name}%",))

    # Sentiment
    sentiment = db.query("""
        SELECT * FROM social_sentiment WHERE brand_name=?
        ORDER BY period DESC LIMIT 2
    """, (brand_name,))

    # Stock
    stock = db.query_one("""
        SELECT close, trade_date FROM stock_prices WHERE brand=?
        ORDER BY trade_date DESC LIMIT 1
    """, (brand_name,))

    return {
        "brand": brand_name,
        "bvs": {"rating": bvs["score_label"], "score": bvs["score"], "date": bvs["run_date"]} if bvs else None,
        "scem": {"risk": scem["score_label"], "exposure": scem["score"]} if scem else None,
        "tdg": {"gap": tdg["score_label"], "delivery": tdg["score"]} if tdg else None,
        "sales": {
            "latest_month_total": latest_month_sales or sales_trend[0]["total"] if sales_trend else 0,
            "trend": sales_trend,
        },
        "financial": {
            "report_date": fin["report_date"][:10] if fin and fin["report_date"] else None,
            "revenue": fin["revenue"] if fin else None,
            "net_profit": fin["net_profit"] if fin else None,
            "gross_margin": fin["gross_margin"] if fin else None,
            "net_margin": fin["net_margin"] if fin else None,
            "roe": fin["roe"] if fin else None,
            "debt_ratio": fin["debt_ratio"] if fin else None,
        } if fin else None,
        "stock": {"price": stock["close"], "date": stock["trade_date"]} if stock else None,
        "news": [{"title": n["title"], "source": n["source"], "date": n["published_at"],
                   "sentiment": n["sentiment"]} for n in (news or [])],
        "sentiment": [{"period": s["period"], "positive": s["positive_ratio"],
                        "negative": s["negative_ratio"], "mentions": s["total_mentions"]}
                       for s in (sentiment or [])],
    }
async def sales_ranking(
    top_n: int = Query(default=20, le=100),
    month: str = Query(default=None),
):
    """Get sales ranking."""
    from pipeline.db import get_db
    db = get_db()
    rows = db.get_latest_sales() if not month else db.query(
        "SELECT * FROM sales_monthly WHERE month=? ORDER BY rank LIMIT ?", (month, top_n)
    )
    return {
        "month": rows[0]["month"] if rows else None,
        "results": [
            {"rank": r["rank"], "model": r["model_name"], "brand": r["brand_name"],
             "sales": r["sales_volume"], "is_nev": bool(r["is_nev"]),
             "price": r["price_range"]}
            for r in rows[:top_n]
        ],
    }


@app.get("/auto/api/report/latest")
async def latest_report():
    """Get the latest weekly report."""
    from pipeline.db import get_db
    db = get_db()
    row = db.query_one(
        "SELECT * FROM agent_results WHERE product='weekly_report' ORDER BY run_date DESC LIMIT 1"
    )
    if not row:
        raise HTTPException(status_code=404, detail="No reports yet")
    return {
        "date": row["run_date"],
        "report_md": row["report_md"],
    }


@app.get("/auto/api/stats")
async def overview_stats():
    """Get overview statistics for the dashboard."""
    from pipeline.db import get_db
    db = get_db()

    latest = db.get_latest_sales()
    if not latest:
        raise HTTPException(status_code=404, detail="No sales data available")

    total_sales = sum(r["sales_volume"] for r in latest)
    nev_sales = sum(r["sales_volume"] for r in latest if r["is_nev"])
    nev_pct = round(nev_sales / total_sales * 100, 1) if total_sales else 0

    from collections import Counter
    brands = Counter(r["brand_name"] for r in latest)

    return {
        "month": latest[0]["month"],
        "total_sales": total_sales,
        "nev_share_pct": nev_pct,
        "top_brands": brands.most_common(10),
        "model_count": len(latest),
    }
