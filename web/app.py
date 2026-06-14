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


@app.get("/auto/analysis/shanzhai")
async def analysis_shanzhai():
    """The Shanzhai-NEV data-driven analysis."""
    import markdown
    path = Path(__file__).parent.parent / "analysis" / "nev-shanzhai-by-the-numbers.md"
    if not path.exists():
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    md_text = path.read_text(encoding="utf-8")
    # Simple markdown→HTML (headings, tables, bold, lists)
    html_body = _simple_md(md_text)
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>新能源「山寨化」· AutoInsight</title>
<style>
  :root{{--text:#1a1a1a;--muted:#555;--accent:#1e40af;--border:#e5e5e5;--max-w:880px}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;font-size:16px;line-height:1.85;color:var(--text);background:#fff;-webkit-font-smoothing:antialiased}}
  main{{max-width:var(--max-w);width:90%;margin:0 auto;padding:56px 0 48px}}
  a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
  .back{{font-size:14px;color:var(--muted);margin-bottom:32px}}
  h1{{font-size:30px;margin-bottom:8px}}h2{{font-size:20px;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
  h3{{font-size:17px;margin:24px 0 8px}}
  p{{margin-bottom:14px}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}}
  th,td{{border:1px solid var(--border);padding:8px 14px;text-align:left}}
  th{{background:#f8f8f6;font-weight:600}}
  blockquote{{border-left:3px solid var(--accent);padding:8px 20px;margin:16px 0;color:var(--muted);font-size:15px;background:#f8f8f6}}
  ul,ol{{margin:8px 0 16px 24px}}li{{margin-bottom:4px}}
  code{{background:#f5f5f5;padding:2px 6px;border-radius:3px;font-size:14px}}
  em{{font-style:italic}}
  footer{{margin-top:48px;padding-top:16px;border-top:1px solid var(--border);font-size:13px;color:#aaa}}
</style></head>
<body><main>
<p class="back"><a href="/auto">← AutoInsight</a></p>
{html_body}
<footer><p>AutoInsight · <a href="https://github.com/ChenyuHeee/chinese-car-watch">GitHub</a> · 仅供参考，不构成投资建议</p></footer>
</main></body></html>""")


def _simple_md(md: str) -> str:
    """Minimal markdown→HTML converter (no external deps needed)."""
    import re
    lines = md.split("\n")
    out = []
    in_list = False
    for line in lines:
        # Headings
        if line.startswith("### "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{line[4:]}</h3>")
            continue
        if line.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{line[3:]}</h2>")
            continue
        # Blockquote
        if line.startswith("> "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
            continue
        # Tables
        if "|" in line and line.count("|") >= 2:
            if in_list: out.append("</ul>"); in_list = False
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-","").replace(":","") == "" for c in cells):
                continue  # separator row
            tag = "th" if "---" in "".join(cells) or (out and "</thead>" not in "".join(out[-3:])) else "td"
            row = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            if tag == "th" and (not out or not out[-1].startswith("<table")):
                out.append("<table>")
            if not out or out[-1] == "</tr>":
                pass
            out.append(f"<tr>{row}</tr>")
            # Close table on next non-table line
            continue
        elif out and out[-1].startswith("<tr>"):
            out.append("</table>")
        # Unordered list
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        elif in_list:
            out.append("</ul>")
            in_list = False
        # Bold
        line = _inline(line)
        if line.strip():
            out.append(f"<p>{line}</p>")
        elif out and out[-1] != "</table>":
            out.append("")
    if in_list: out.append("</ul>")
    return "\n".join(out)


def _inline(text: str) -> str:
    """Handle inline markdown: bold, italic, code, links."""
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)
    return text


@app.get("/auto/brand/{brand_name}")
async def brand_page(brand_name: str):
    """Brand detail page — server-side rendered."""
    from pipeline.db import get_db
    from collections import defaultdict
    db = get_db()

    # ── Collect all data ──
    bvs = db.query_one("SELECT score_label, score, run_date FROM agent_results WHERE product='bvs' AND target_name=? ORDER BY run_date DESC LIMIT 1", (brand_name,))
    scem = db.query_one("SELECT score_label, score FROM agent_results WHERE product='scem' AND target_name=? ORDER BY run_date DESC LIMIT 1", (brand_name,))
    tdg = db.query_one("SELECT score_label, score FROM agent_results WHERE product='tdg' AND target_name=? ORDER BY run_date DESC LIMIT 1", (brand_name,))
    stock = db.query_one("SELECT close, trade_date FROM stock_prices WHERE brand=? ORDER BY trade_date DESC LIMIT 1", (brand_name,))
    fin = db.query_one("SELECT * FROM financial_reports WHERE brand=? ORDER BY report_date DESC LIMIT 1", (brand_name,))
    news = db.query("SELECT title, source, published_at, sentiment FROM news_articles WHERE related_brands LIKE ? ORDER BY published_at DESC LIMIT 5", (f"%{brand_name}%",))

    sales_rows = db.query("SELECT month, model_name, sales_volume, rank FROM sales_monthly WHERE brand_name LIKE ? ORDER BY month DESC, rank ASC LIMIT 50", (f"%{brand_name}%",))
    monthly_totals = defaultdict(int)
    monthly_models = defaultdict(list)
    for r in sales_rows:
        monthly_totals[r["month"]] += r["sales_volume"]
        monthly_models[r["month"]].append(r)
    sales_trend = [{"month": m, "total": monthly_totals[m], "models": monthly_models[m][:5]} for m in sorted(monthly_totals.keys(), reverse=True)[:6]]

    # ── Rating helpers ──
    rating_desc = {"AAA":"行业领导者","AA":"强势品牌","A":"稳健运营","BBB":"正常经营","BB":"高风险","B":"极度危险","C":"停摆"}
    rating_cls = {"AAA":"g","AA":"g","A":"y","BBB":"y","BB":"r","B":"r","C":"r"}
    risk_cls = {"critical":"r","high":"y","moderate":"g","low":"g"}

    def tag(label, cls): return f'<span class="tag {cls}">{label}</span>'
    def num(v, fmt=",.0f"): return f"{v:{fmt}}" if v is not None else "—"
    def sent_tag(s): return f'<span class="sent {s}">{s}</span>' if s else ""

    # ── Build HTML ──
    sub_parts = []
    if bvs: sub_parts.append(f'BVS: {tag(bvs["score_label"], rating_cls.get(bvs["score_label"],""))} ({bvs["score"]:.0f})')
    if stock: sub_parts.append(f'Stock: {stock["close"]:.2f}')
    if sales_trend: sub_parts.append(f'Monthly sales: {sales_trend[0]["total"]:,}')
    subtitle = " · ".join(sub_parts)

    # KPIs
    kpis = []
    if bvs:
        kpis.append(("BVS Rating", bvs["score_label"], rating_cls.get(bvs["score_label"],""), f'Score: {bvs["score"]:.0f}'))
        kpis.append(("BVS Score", f'{bvs["score"]:.0f}', "", bvs["run_date"][:10] if bvs.get("run_date") else ""))
    latest_total = sales_trend[0]["total"] if sales_trend else 0
    kpis.append(("Monthly Sales", f"{latest_total:,}", "", "units"))
    if fin:
        kpis.append(("Revenue", f'{fin["revenue"]:.0f}亿', "", fin["report_date"][:10] if fin.get("report_date") else ""))
        kpis.append(("Gross Margin", f'{fin["gross_margin"]:.1f}%', "g" if fin["gross_margin"] > 15 else ("y" if fin["gross_margin"] > 5 else "r"), ""))
        kpis.append(("Net Profit", f'{fin["net_profit"]:.0f}亿', "g" if fin["net_profit"] >= 0 else "r", f'ROE: {fin["roe"]:.1f}%'))
    if scem:
        kpis.append(("Supply Risk", f'{scem["score"]:.0f}', risk_cls.get(scem["score_label"],""), scem["score_label"]))
    if tdg:
        kpis.append(("Tech Delivery", f'{tdg["score"]:.0f}', "g" if tdg["score"] > 70 else ("y" if tdg["score"] > 50 else "r"), f'{tdg["score_label"]}% gap'))

    kpi_html = "\n".join(
        f'<div class="kpi"><label>{l}</label><div class="v {c}">{v}</div><div class="subv">{sv}</div></div>'
        for l, v, c, sv in kpis
    )

    # Analysis
    analysis = ""
    if bvs:
        analysis += f'<p><strong>BVS {bvs["score_label"]}</strong> — {rating_desc.get(bvs["score_label"], "")}</p>'
    if fin:
        analysis += f'<p>Latest quarter: revenue {fin["revenue"]:.0f} 亿, net profit {fin["net_profit"]:.0f} 亿, gross margin {fin["gross_margin"]:.1f}%, debt ratio {fin["debt_ratio"]:.1f}%.</p>'
    if scem:
        analysis += f'<p>Supply chain exposure: <strong>{scem["score"]:.0f}/100</strong> ({scem["score_label"]}).</p>'
    if bvs and bvs["score"] < 50:
        analysis += '<p style="color:#dc2626">⚠ This brand is in the danger zone.</p>'
    if not analysis:
        analysis = "<p>No analysis data available yet.</p>"

    # Sales table rows
    sales_html = ""
    for m in sales_trend:
        model_str = ", ".join(f'{r["model_name"]} ({r["sales_volume"]:,})' for r in m["models"])
        sales_html += f'<tr><td>{m["month"]}</td><td class="n">{m["total"]:,}</td><td>{model_str}</td></tr>'

    # Financial row
    fin_html = ""
    if fin:
        fin_html = (f'<tr><td>{fin.get("report_date","")[:10]}</td>'
                    f'<td class="n">{fin["revenue"]:.0f}</td>'
                    f'<td class="n {"g" if fin["net_profit"]>=0 else "r"}">{fin["net_profit"]:.0f}</td>'
                    f'<td class="n">{fin["gross_margin"]:.1f}%</td><td class="n">{fin["net_margin"]:.1f}%</td>'
                    f'<td class="n">{fin["roe"]:.1f}%</td><td class="n">{fin["debt_ratio"]:.1f}%</td></tr>')

    # News rows
    news_html = "".join(
        f'<tr><td>{n.get("published_at","")[:10]}</td><td>{n["title"]}</td><td>{sent_tag(n.get("sentiment",""))}</td></tr>'
        for n in (news or [])
    ) or '<tr><td colspan="3">No recent news</td></tr>'

    # Extra row
    extra = '<tr>'
    extra += f'<td>Risk: {tag(scem["score_label"], risk_cls.get(scem["score_label"],""))} ({scem["score"]:.0f}/100)</td>' if scem else '<td>—</td>'
    extra += f'<td>Delivery: {tdg["score"]:.0f}/100 (gap: {tdg["score_label"]}%)</td>' if tdg else '<td>—</td>'
    extra += f'<td>{stock["close"]:.2f} ({stock.get("trade_date","")})</td>' if stock else '<td>—</td>'
    extra += '</tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand_name} · AutoInsight</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{--text:#1a1a1a;--muted:#555;--accent:#1e40af;--border:#e5e5e5;--max-w:880px}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;font-size:15px;line-height:1.7;color:var(--text);background:#fff;-webkit-font-smoothing:antialiased}}
  main{{max-width:var(--max-w);width:90%;margin:0 auto;padding:56px 0 48px}}
  a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
  .back{{font-size:14px;color:var(--muted)}}.back a{{color:var(--muted)}}
  h1{{font-size:30px;font-weight:700;letter-spacing:-0.02em;margin-bottom:4px}}
  .sub{{color:var(--muted);font-size:15px;margin-bottom:28px}}
  section{{margin-bottom:36px}}
  section h2{{font-size:15px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:14px;padding-bottom:5px;border-bottom:1px solid var(--border)}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
  .kpi{{border:1px solid var(--border);border-radius:8px;padding:14px 18px}}
  .kpi label{{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.03em}}
  .kpi .v{{font-size:26px;font-weight:700;margin:3px 0}}
  .kpi .subv{{font-size:13px;color:var(--muted)}}
  .g{{color:#059669}}.y{{color:#d97706}}.r{{color:#dc2626}}
  table{{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:12px}}
  th,td{{border:1px solid var(--border);padding:7px 10px}}
  th{{background:#f8f8f6;font-weight:600;font-size:13px}}
  td.n{{text-align:right;font-variant-numeric:tabular-nums}}
  .tag{{display:inline-block;padding:0.2em 0.55em;border-radius:4px;font-size:12px;font-weight:700;min-width:40px;text-align:center}}
  .tag.AAA,.tag.AA{{background:#ecfdf5;color:#059669}}.tag.A,.tag.BBB{{background:#fffbeb;color:#d97706}}.tag.BB,.tag.B,.tag.C{{background:#fef2f2;color:#dc2626}}
  .tag.critical{{background:#fef2f2;color:#dc2626}}.tag.high{{background:#fffbeb;color:#d97706}}.tag.moderate,.tag.low{{background:#ecfdf5;color:#059669}}
  .sent{{display:inline-block;padding:0.15em 0.5em;border-radius:999px;font-size:11px;font-weight:600}}
  .sent.positive{{background:#ecfdf5;color:#059669}}.sent.negative{{background:#fef2f2;color:#dc2626}}.sent.neutral{{background:#f5f5f5;color:var(--muted)}}
  .insight{{background:#f8f8f6;border-left:3px solid var(--accent);padding:16px 20px;margin:16px 0;font-size:14px;line-height:1.8}}
  footer{{margin-top:40px;padding-top:16px;border-top:1px solid var(--border);font-size:13px;color:#aaa}}
  @media(max-width:640px){{main{{padding-top:40px}}h1{{font-size:26px}}}}
</style>
</head>
<body>
<main>
  <p class="back"><a href="/auto">← AutoInsight</a></p>
  <h1>{brand_name}</h1>
  <p class="sub">{subtitle}</p>

  <div class="kpis">{kpi_html}</div>

  <section>
    <h2>Analysis</h2>
    <div class="insight">{analysis}</div>
  </section>

  <section>
    <h2>Sales Trend</h2>
    <table><thead><tr><th>Month</th><th>Total Sales</th><th>Top Models</th></tr></thead>
    <tbody>{sales_html}</tbody></table>
  </section>

  <section>
    <h2>Financials</h2>
    <table><thead><tr><th>Report Date</th><th>Revenue (亿)</th><th>Net Profit (亿)</th><th>Gross Margin</th><th>Net Margin</th><th>ROE</th><th>Debt Ratio</th></tr></thead>
    <tbody>{fin_html}</tbody></table>
  </section>

  <section>
    <h2>Recent News</h2>
    <table><thead><tr><th>Date</th><th>Title</th><th>Sentiment</th></tr></thead>
    <tbody>{news_html}</tbody></table>
  </section>

  <section>
    <h2>Supply Chain & Tech</h2>
    <table><thead><tr><th>Supply Chain Risk</th><th>Tech Delivery</th><th>Stock</th></tr></thead>
    <tbody>{extra}</tbody></table>
  </section>

  <footer>
    <p>仅供参考，不构成投资建议 · Auto-generated · <a href="https://github.com/ChenyuHeee/chinese-car-watch">GitHub</a> · Chenyu He &copy; 2026</p>
  </footer>
</main>
</body>
</html>"""
    return HTMLResponse(html)


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
