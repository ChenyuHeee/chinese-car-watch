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


@app.get("/auto/api/sales/ranking")
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
