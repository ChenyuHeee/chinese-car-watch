"""
AutoInsight Web API — deployed at insight.hechenyu.xin/auto
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="AutoInsight", version="0.1.0")

STATIC = Path(__file__).parent / "static"
TEMPLATES = Path(__file__).parent / "templates"

app.mount("/auto/static", StaticFiles(directory=str(STATIC)), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _get_db():
    from pipeline.db import get_db
    return get_db()


# ── Pages ────────────────────────────────────────────────────

@app.get("/auto")
@app.get("/auto/")
async def dashboard():
    index_path = STATIC / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AutoInsight</h1>")


@app.get("/auto/report/latest")
async def latest_report_page():
    """Render the latest monthly report from DB."""
    db = _get_db()
    row = db.query_one("SELECT * FROM agent_results WHERE product='weekly_report' ORDER BY run_date DESC LIMIT 1")
    if not row:
        return HTMLResponse("<h1>No report yet</h1>")
    md = row["report_md"]
    html_body = _simple_md(md)
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Monthly Report · AutoInsight</title>
<style>
  :root{{--text:#1a1a1a;--muted:#555;--accent:#1e40af;--border:#e5e5e5;--max-w:880px}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;font-size:16px;line-height:1.8;color:var(--text);background:#fff}}
  main{{max-width:var(--max-w);width:90%;margin:0 auto;padding:56px 0 48px}}
  a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
  .back{{font-size:14px;color:var(--muted);margin-bottom:32px}}
  h1{{font-size:28px;margin-bottom:8px}}h2{{font-size:20px;margin:40px 0 16px;padding-bottom:6px;border-bottom:2px solid #1a1a1a}}
  h3{{font-size:17px;margin:24px 0 10px}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}}
  th,td{{border:1px solid var(--border);padding:8px 14px}}
  th{{background:#f8f8f6;font-weight:600}}
  blockquote{{border-left:3px solid var(--accent);padding:8px 20px;margin:16px 0;color:var(--muted);background:#f8f8f6}}
  hr{{border:none;border-top:1px solid var(--border);margin:24px 0}}
  ul,ol{{margin:8px 0 16px 24px}}li{{margin-bottom:4px}}
  strong{{color:#1a1a1a}}
  footer{{margin-top:48px;padding-top:16px;border-top:1px solid var(--border);font-size:13px;color:#aaa}}
</style></head>
<body><main>
<p class="back"><a href="/auto">&larr; AutoInsight</a></p>
{html_body}
<footer><p>AutoInsight · <a href="https://github.com/ChenyuHeee/chinese-car-watch">GitHub</a> · Auto-generated monthly</p></footer>
</main></body></html>""")


@app.get("/auto/research/nev-industry-2026h1")
async def research_report():
    """Investment research report — China NEV Industry H1 2026."""
    db = _get_db()

    # ── Data ──
    sales = db.get_latest_sales()
    total_sales = sum(r["sales_volume"] for r in sales)
    brand_sales = defaultdict(int)
    for r in sales:
        brand_sales[r["brand_name"]] += r["sales_volume"]

    top10_nev = sum(1 for r in sales[:10] if r["is_nev"])
    nev_top50 = sum(1 for r in sales[:50] if r["is_nev"])
    top5_share = sum(s for _, s in sorted(brand_sales.items(), key=lambda x: x[1], reverse=True)[:5]) / total_sales * 100

    # BVS
    bvs_rows = db.query("SELECT target_name, score_label, score, details FROM agent_results WHERE product='bvs' ORDER BY score DESC")
    bvs_map = {r["target_name"]: r for r in bvs_rows}

    # Financials
    fin_all = db.query("SELECT * FROM financial_reports ORDER BY brand, report_date DESC")
    fin_latest = {}
    seen_brands = set()
    for r in fin_all:
        if r["brand"] not in seen_brands:
            seen_brands.add(r["brand"])
            fin_latest[r["brand"]] = r

    # SCEM
    scem_rows = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='scem' ORDER BY score DESC")
    scem_map = {}
    seen_scem = set()
    for r in scem_rows:
        if r["target_name"] not in seen_scem:
            seen_scem.add(r["target_name"])
            scem_map[r["target_name"]] = r

    # Supplier relations
    suppliers = db.query("SELECT supplier_name, COUNT(*) as n FROM supplier_relations GROUP BY supplier_name ORDER BY n DESC")

    # News sentiment
    sentiment = db.query("SELECT sentiment, COUNT(*) as n FROM news_articles GROUP BY sentiment")
    sent_map = {r["sentiment"]: r["n"] for r in sentiment}
    total_news = sum(sent_map.values())

    # Stock prices
    stocks_all = db.query("SELECT brand, close, trade_date FROM stock_prices ORDER BY brand, trade_date DESC")
    stock_map = {}
    seen_stock = set()
    for r in stocks_all:
        if r["brand"] not in seen_stock:
            seen_stock.add(r["brand"])
            stock_map[r["brand"]] = r

    # ── Build tables ──
    def row(cells, tag="td"):
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"

    # Peer comparison table
    peer_header = row(["Brand", "BVS", "Revenue (Bn)", "Net Profit (Bn)", "Gross Margin", "Net Margin", "ROE", "D/E Ratio", "Stock"], "th")
    peer_rows = ""
    peer_order = ["比亚迪", "特斯拉", "理想", "问界", "小米汽车", "零跑", "小鹏", "蔚来", "吉利"]
    for b in peer_order:
        f = fin_latest.get(b, {})
        bvs = bvs_map.get(b, {})
        stk = stock_map.get(b, {})
        rev = f.get("revenue", 0) or 0
        pr = f.get("net_profit", 0) or 0
        gmar = f.get("gross_margin", 0) or 0
        nmar = f.get("net_margin", 0) or 0
        roe = f.get("roe", 0) or 0
        debt = f.get("debt_ratio", 0) or 0
        rating = bvs.get("score_label", "—")
        score = bvs.get("score", 0)
        rating_cls = "g" if score >= 70 else ("y" if score >= 40 else "r")
        pr_cls = "g" if pr >= 0 else "r"
        stk_price = stk.get("close", 0) or 0
        peer_rows += row([
            f"<strong>{b}</strong>",
            f'<span class="tag {rating_cls}">{rating}</span>',
            f'{rev:.0f}',
            f'<span class="{pr_cls}">{pr:+.0f}</span>',
            f'{gmar:.1f}%',
            f'{nmar:.1f}%',
            f'{roe:.1f}%',
            f'{debt:.1f}%',
            f'{stk_price:.2f}',
        ])

    # Market share table
    ms_header = row(["Rank", "Brand", "Sales", "Share", "Cumulative"], "th")
    ms_rows = ""
    cum = 0
    for i, (b, s) in enumerate(sorted(brand_sales.items(), key=lambda x: x[1], reverse=True)[:12]):
        share = s / total_sales * 100
        cum += share
        ms_rows += row([str(i+1), b, f"{s:,}", f"{share:.1f}%", f"{cum:.1f}%"])

    # Top models
    model_header = row(["Rank", "Model", "Brand", "Sales", "Type"], "th")
    model_rows = ""
    for r in sales[:20]:
        t = "NEV" if r["is_nev"] else "ICE"
        cls = "g" if r["is_nev"] else ""
        model_rows += row([r["rank"], r["model_name"], r["brand_name"], f'{r["sales_volume"]:,}', f'<span class="{cls}">{t}</span>'])

    # Supply chain table
    sc_header = row(["Supplier", "Brands Served", "Component", "Risk Assessment"], "th")
    sc_rows = ""
    sc_components = {"宁德时代": "Battery", "博世": "Chassis/Braking", "华为": "AD/ADAS + Cockpit", "弗迪电池": "Battery (BYD)", "地平线": "ADAS Chip"}
    for s in suppliers:
        name = s["supplier_name"]
        n = s["n"]
        comp = sc_components.get(name, "Other")
        risk = "High" if n >= 8 else ("Medium" if n >= 5 else "Low")
        risk_cls = "r" if risk == "High" else ("y" if risk == "Medium" else "g")
        sc_rows += row([name, str(n), comp, f'<span class="{risk_cls}">{risk}</span>'])

    # Risk matrix
    risk_header = row(["Risk Factor", "Severity", "Probability", "Impact"], "th")
    risk_items = [
        ("Price war escalation", "High", "~70%", "Further margin compression to <2%"),
        ("Brand bankruptcies (2-5 brands)", "High", "~60%", "Supply chain disruption, consumer confidence"),
        ("Raw material cost spike", "Medium", "~30%", "Margin erosion for non-integrated players"),
        ("Export tariff increases", "Medium", "~25%", "Volume impact on export-dependent brands"),
        ("Autonomous driving regulatory shift", "Low", "~15%", "ADAS leaders benefit, laggards disadvantaged"),
    ]
    risk_rows = ""
    for factor, sev, prob, impact in risk_items:
        cls = "r" if sev == "High" else ("y" if sev == "Medium" else "g")
        risk_rows += row([factor, f'<span class="{cls}">{sev}</span>', prob, impact])

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>China NEV Industry — H1 2026 Research Report · AutoInsight</title>
<style>
  :root{{--text:#1a1a1a;--muted:#555;--accent:#1e40af;--border:#ddd;--max-w:960px}}
  body{{font-family:"Times New Roman",Georgia,"Noto Serif SC",serif;font-size:17px;line-height:1.75;color:var(--text);background:#fff;-webkit-font-smoothing:antialiased}}
  .report{{max-width:var(--max-w);margin:0 auto;padding:64px 24px 48px}}
  a{{color:var(--accent);text-decoration:none}}
  .cover{{text-align:center;padding:80px 0 60px;border-bottom:3px double #1a1a1a;margin-bottom:48px}}
  .cover h1{{font-size:36px;font-weight:800;letter-spacing:0.02em;margin-bottom:12px;line-height:1.3}}
  .cover .sub{{font-size:18px;color:var(--muted)}}
  .cover .meta{{margin-top:32px;font-size:14px;color:var(--muted)}}
  .cover .disclaimer{{margin-top:20px;font-size:12px;color:#999;max-width:640px;margin-left:auto;margin-right:auto;line-height:1.6}}

  h2{{font-size:22px;font-weight:700;margin:48px 0 16px;padding-bottom:8px;border-bottom:2px solid #1a1a1a;letter-spacing:0.02em}}
  h3{{font-size:18px;font-weight:700;margin:32px 0 12px}}
  p{{margin-bottom:14px;text-align:justify}}
  .lead{{font-size:19px;line-height:1.9;margin-bottom:24px}}

  table{{width:100%;border-collapse:collapse;margin:20px 0;font-size:15px}}
  th{{background:#1a1a1a;color:#fff;font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:0.05em}}
  th,td{{border:1px solid var(--border);padding:10px 14px;text-align:left}}
  tr:nth-child(even){{background:#f8f8f6}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}

  .tag{{display:inline-block;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:700}}
  .tag.g{{background:#e8f5e9;color:#2e7d32}}.tag.y{{background:#fff8e1;color:#f57f17}}.tag.r{{background:#ffebee;color:#c62828}}
  .g{{color:#2e7d32}}.y{{color:#f57f17}}.r{{color:#c62828}}

  .kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:24px 0}}
  .kpi{{border:1px solid var(--border);padding:20px 24px;text-align:center}}
  .kpi .v{{font-size:32px;font-weight:800;margin:6px 0}}
  .kpi .l{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:0.05em}}
  .kpi .note{{font-size:12px;color:var(--muted)}}

  .callout{{background:#f8f8f6;border-left:3px solid var(--accent);padding:20px 24px;margin:24px 0;font-size:16px}}
  .callout strong{{color:var(--accent)}}

  footer{{margin-top:64px;padding-top:24px;border-top:1px solid var(--border);font-size:13px;color:#999}}
  .back{{font-size:14px;color:var(--muted);margin-bottom:8px}}
  @media(max-width:640px){{.cover h1{{font-size:24px}}.kpi-row{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="report">

<p class="back"><a href="/auto">&larr; AutoInsight</a></p>

<div class="cover">
  <h1>China Passenger Vehicle Market:<br>NEV Transition &amp; Industry Consolidation</h1>
  <div class="sub">H1 2026 Industry Research Report</div>
  <div class="meta">
    AutoInsight Research · June 15, 2026<br>
    Data as of May 2026 reporting period
  </div>
  <div class="disclaimer">
    This report is produced by an AI multi-agent research system. It is for informational purposes only and does not constitute investment advice. All ratings and scores are algorithmically generated based on publicly available data. See Appendix for full methodology.
  </div>
</div>

<!-- Executive Summary -->
<h2>1. Executive Summary</h2>

<p class="lead"><strong>We initiate coverage of the Chinese passenger vehicle market with a CAUTIOUS view.</strong> While NEV penetration continues to accelerate, industry profitability has deteriorated to 2.9% — a level consistent with pre-consolidation cycles in comparable industries. Market concentration (top-5 share: 27.3%) remains well below mature industry benchmarks (>60%), indicating significant excess capacity and a high probability of consolidation over the next 12-24 months.</p>

<div class="kpi-row">
  <div class="kpi"><div class="l">Industry Profit Margin</div><div class="v r">2.9%</div><div class="note">vs 8.0% in 2017</div></div>
  <div class="kpi"><div class="l">Top-5 Concentration</div><div class="v y">27.3%</div><div class="note">Mature industries >60%</div></div>
  <div class="kpi"><div class="l">NEV Penetration (Top 50)</div><div class="v g">{nev_top50}/50</div><div class="note">Top 10: {top10_nev}/10 NEV</div></div>
  <div class="kpi"><div class="l">Brands at Risk (BVS &le; BB)</div><div class="v r">1</div><div class="note">of 9 rated</div></div>
</div>

<div class="callout">
  <strong>Key Findings:</strong><br>
  1. The top 10 best-selling models are 100% NEV. No ICE model ranks above #17.<br>
  2. Industry profit margin has declined from 8.0% (2017) to 2.9% (Q1 2026), tracking the 2008 Shanzhai phone cycle.<br>
  3. Supplier concentration mirrors the MTK Turnkey era — CATL alone serves 13 brands.<br>
  4. Our Brand Viability Score identifies NIO (BB, score 35) as the highest near-term survival risk among rated brands.<br>
  5. BYD (AA, score 82) remains the best-positioned player, driven by vertical integration and scale.
</div>

<!-- Industry Structure -->
<h2>2. Industry Structure &amp; Competitive Dynamics</h2>

<h3>2.1 Market Share Analysis</h3>

<p>The market remains highly fragmented. BYD leads with 10.5% share, but no other player exceeds 7%. The top 12 brands collectively account for only 43.6% of volume — the remaining ~57% is distributed across 90+ brands, most of which are unprofitable and reliant on external financing.</p>

<table><thead>{ms_header}</thead><tbody>{ms_rows}</tbody></table>

<p><strong>Implication:</strong> The current market structure is unsustainable. We expect 30-50 brands to exit within 2-3 years through bankruptcy, acquisition, or voluntary withdrawal. This consolidation will create significant alpha opportunities for investors who correctly identify survivors vs. casualties.</p>

<h3>2.2 Top Models: NEV Dominance</h3>

<table><thead>{model_header}</thead><tbody>{model_rows}</tbody></table>

<p>The top 15 models are entirely NEV. This is not merely a trend — it represents a structural shift in consumer preference. The first ICE vehicle (Geely Boyue L) ranks #17. Traditional volume leaders — Volkswagen Lavida (#18), Nissan Sylphy (#20) — have been displaced.</p>

<h3>2.3 Supplier Concentration: The New MTK</h3>

<p>The supply chain for NEVs exhibits a striking parallel to the 2006-2008 Shanzhai phone era. In that cycle, MediaTek's MTK Turnkey solution — a bundled chip + software package — eliminated technical barriers to entry, enabling ~4,000 manufacturers to enter the market. Profit margins collapsed from >15% to <3% within 24 months as competition shifted entirely to price.</p>

<table><thead>{sc_header}</thead><tbody>{sc_rows}</tbody></table>

<p><strong>Structural observation:</strong> When 13 brands share the same battery supplier and 6 brands use the same ADAS stack, the scope for product differentiation narrows to industrial design, brand marketing, and software tuning. This dynamic is inherently margin-compressive for all but the most scaled or vertically integrated players.</p>

<!-- Financial Analysis -->
<h2>3. Financial Analysis: Peer Comparison</h2>

<table><thead>{peer_header}</thead><tbody>{peer_rows}</tbody></table>

<p><strong>BYD</strong> (AA, 82) remains the benchmark for financial health in the sector. Q1 2026 revenue of RMB 150.2bn with net profit of RMB 4.1bn, gross margin of 18.8%. Its vertical integration — in-house battery (FinDreams), chip design, and manufacturing — provides a structural cost advantage that pure-play assemblers cannot replicate.</p>

<p><strong>NIO</strong> (BB, 35) is the most concerning name in our coverage. Cumulative net loss of RMB 15.7bn through Q3 2025, gross margin of only 11.1% — the lowest among rated NEV brands — and a debt-to-equity ratio of 89.2%. The battery-swap infrastructure, while a theoretical moat, represents a significant fixed-cost burden. Without a capital infusion or dramatic improvement in unit economics, NIO faces a liquidity squeeze within 12-18 months.</p>

<p><strong>Li Auto</strong> (BBB, 55) and <strong>AITO</strong> (BBB, 55) represent the middle tier — profitable but with thin margins and high dependence on specific product cycles (Li Auto's EREV lineup, AITO's Huawei partnership).</p>

<!-- Brand Viability Score -->
<h2>4. Brand Viability Score: Methodology &amp; Results</h2>

<p>The BVS is a composite score (0-100) derived from a proprietary multi-agent analytical framework. Each brand rating is the output of a structured debate between two independent AI analysts — one arguing the bear case, one the bull case — with a third agent serving as judge. All three agents have access to the same underlying database: monthly sales, quarterly financials, supply chain relationships, news sentiment, and social media metrics.</p>

<p><strong>Scoring dimensions</strong> (equal-weighted):</p>
<ul>
  <li><strong>Sales Momentum (25%):</strong> MoM and YoY volume trends, rank stability, model diversification</li>
  <li><strong>Financial Runway (25%):</strong> Profitability, cash position, debt levels, funding history</li>
  <li><strong>Product Pipeline (20%):</strong> New model cadence, technology competitiveness, segment coverage</li>
  <li><strong>Supply Chain Resilience (15%):</strong> Supplier diversification, vertical integration, single-source risk</li>
  <li><strong>External Sentiment (15%):</strong> News tone, social media sentiment, brand perception trends</li>
</ul>

<div class="callout">
  <strong>Current BVS Distribution:</strong> AA: 1 brand · A: 4 brands · BBB: 3 brands · BB: 1 brand<br>
  The distribution is skewed toward the middle, reflecting the early stage of our data accumulation. As time series extend beyond 3-6 months, rating discrimination is expected to increase.
</div>

<!-- Risk Matrix -->
<h2>5. Risk Matrix</h2>

<table><thead>{risk_header}</thead><tbody>{risk_rows}</tbody></table>

<p><strong>Primary risk scenario (30-40% probability):</strong> A cascading failure in which 2-3 mid-tier brands simultaneously face liquidity crises, triggering supplier payment delays that propagate through the shared supply chain. The most exposed suppliers are those serving 8+ brands with limited bargaining power.</p>

<!-- Conclusion -->
<h2>6. Investment Implications</h2>

<p><strong>Near-term (0-6 months):</strong> We are cautious on the sector. Margin compression is likely to continue as price competition intensifies ahead of potential consolidation. We would avoid names with BVS scores below 50 and debt ratios above 70%.</p>

<p><strong>Medium-term (6-18 months):</strong> The consolidation phase will create buying opportunities in survivors. Historical parallels (Chinese appliance industry 2000-2005, smartphone industry 2012-2016) suggest that the top 3-5 players at the end of consolidation capture 60-70% of industry profits.</p>

<p><strong>Key catalysts to monitor:</strong></p>
<ul>
  <li>Quarterly financial reports (next: Q2 2026 in August)</li>
  <li>Brand bankruptcies or distressed M&A</li>
  <li>Government policy shifts on NEV subsidies or consolidation</li>
  <li>Raw material price movements (lithium carbonate, rare earths)</li>
</ul>

<p><strong>Top picks:</strong> BYD (vertical integration, scale, profitability) · CATL (supplier to 13 brands — the "shovel seller" in a gold rush)</p>

<p><strong>Names to avoid:</strong> Brands with BVS &le; BB, gross margin &lt; 12%, debt ratio &gt; 80%, or no clear path to profitability within 4 quarters.</p>

<!-- Appendix -->
<h2>7. Appendix: Methodology &amp; Data Sources</h2>

<p><strong>Data Sources:</strong> Sales rankings (xl.16888.com, updated monthly), Financial reports (akshare, via Shenzhen/Shanghai Stock Exchange and SEC filings), Stock prices (Sina Finance API), News sentiment (Sina Finance, Autohome, Dongchedi), Supply chain relationships (publicly disclosed supplier agreements).</p>

<p><strong>Agent Configuration:</strong> BVS ratings are produced by a Multi-Agent system running on DeepSeek V4 Pro (analyst/critic) and DeepSeek V4 Flash (investigator/writer). Each brand evaluation consumes approximately 30K-50K tokens across the debate and judgment phases. Full system code is open-source at <a href="https://github.com/ChenyuHeee/chinese-car-watch">github.com/ChenyuHeee/chinese-car-watch</a>.</p>

<p><strong>Limitations:</strong> This analysis is based on approximately 30 days of accumulated data. BVS ratings should be interpreted with appropriate caution. Ratings are expected to stabilize and gain predictive power as the underlying time series extend. Past performance of similar industry consolidation patterns does not guarantee future outcomes.</p>

<footer>
  <p><strong>AutoInsight Research</strong> · Published June 15, 2026 · <a href="https://github.com/ChenyuHeee/chinese-car-watch">Open-source methodology</a></p>
  <p>This report is algorithmically generated by an AI multi-agent system. It does not constitute investment advice, a solicitation, or a recommendation to buy or sell any security. All data is sourced from publicly available information and may contain errors or omissions. The authors may hold positions in securities discussed.</p>
  <p>&copy; 2026 AutoInsight. All rights reserved.</p>
</footer>

</div>
</body>
</html>""")


@app.get("/auto/analysis/shanzhai")
async def analysis_shanzhai():
    """Redirect old analysis to new research report."""
    return HTMLResponse("""<html><head><meta http-equiv="refresh" content="0;url=/auto/research/nev-industry-2026h1"></head>
    <body><p>Redirecting to <a href="/auto/research/nev-industry-2026h1">research report</a>...</p></body></html>""")


# ── Brand detail ──
@app.get("/auto/brand/{brand_name}")
async def brand_page(brand_name: str):
    db = _get_db()
    bvs = db.query_one("SELECT score_label, score, run_date FROM agent_results WHERE product='bvs' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    scem = db.query_one("SELECT score_label, score FROM agent_results WHERE product='scem' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    tdg = db.query_one("SELECT score_label, score FROM agent_results WHERE product='tdg' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    stock = db.query_one("SELECT close, trade_date FROM stock_prices WHERE brand=? ORDER BY trade_date DESC", (brand_name,))
    fin = db.query_one("SELECT * FROM financial_reports WHERE brand=? ORDER BY report_date DESC LIMIT 1", (brand_name,))
    news = db.query("SELECT title, source, published_at, sentiment FROM news_articles WHERE related_brands LIKE ? ORDER BY published_at DESC LIMIT 5", (f"%{brand_name}%",))
    sales_r = db.query("SELECT month, model_name, sales_volume, rank FROM sales_monthly WHERE brand_name LIKE ? ORDER BY month DESC, rank ASC LIMIT 50", (f"%{brand_name}%",))

    monthly_totals = defaultdict(int)
    monthly_models = defaultdict(list)
    for r in sales_r:
        monthly_totals[r["month"]] += r["sales_volume"]
        monthly_models[r["month"]].append(r)
    sales_trend = [{"month": m, "total": monthly_totals[m], "models": monthly_models[m][:5]} for m in sorted(monthly_totals.keys(), reverse=True)[:6]]

    def tag(l, c): return f'<span class="tag {c}">{l}</span>'
    def sent_tag(s): return f'<span class="sent {s}">{s}</span>'

    rating_desc = {"AAA":"Industry Leader","AA":"Strong","A":"Stable","BBB":"Adequate","BB":"High Risk","B":"Critical","C":"Non-viable"}
    rating_cls = {"AAA":"g","AA":"g","A":"y","BBB":"y","BB":"r","B":"r","C":"r"}
    risk_cls = {"critical":"r","high":"y","moderate":"g","low":"g"}

    sub_parts = []
    if bvs: sub_parts.append(f'BVS: {tag(bvs["score_label"], rating_cls.get(bvs["score_label"],""))} ({bvs["score"]:.0f})')
    if stock: sub_parts.append(f'Stock: {stock["close"]:.2f}')
    latest_total = sales_trend[0]["total"] if sales_trend else 0
    sub_parts.append(f'Monthly sales: {latest_total:,}')
    subtitle = " · ".join(sub_parts)

    kpis = []
    if bvs:
        kpis.append(("BVS Rating", bvs["score_label"], rating_cls.get(bvs["score_label"],""), f'Score: {bvs["score"]:.0f}'))
    kpis.append(("Monthly Sales", f"{latest_total:,}", "", "units"))
    if fin:
        kpis.append(("Revenue", f'{fin["revenue"]:.0f}亿', "", fin["report_date"][:10] if fin.get("report_date") else ""))
        kpis.append(("Gross Margin", f'{fin["gross_margin"]:.1f}%', "g" if fin["gross_margin"] > 15 else ("y" if fin["gross_margin"] > 5 else "r"), ""))
        pr = fin["net_profit"] or 0
        kpis.append(("Net Profit", f'{pr:.0f}亿', "g" if pr >= 0 else "r", f'ROE: {fin["roe"]:.1f}%'))
    if scem:
        kpis.append(("Supply Risk", f'{scem["score"]:.0f}', risk_cls.get(scem["score_label"],""), scem["score_label"]))
    if tdg:
        kpis.append(("Tech Delivery", f'{tdg["score"]:.0f}', "g" if tdg["score"] > 70 else ("y" if tdg["score"] > 50 else "r"), f'{tdg["score_label"]}% gap'))

    kpi_html = "\n".join(f'<div class="kpi"><label>{l}</label><div class="v {c}">{v}</div><div class="subv">{sv}</div></div>' for l, v, c, sv in kpis)

    analysis = ""
    if bvs:
        analysis += f'<p><strong>BVS {bvs["score_label"]}</strong> — {rating_desc.get(bvs["score_label"], "")}.</p>'
    if fin:
        analysis += f'<p>Latest quarter: revenue {fin["revenue"]:.0f}B, net profit {fin["net_profit"]:.0f}B, gross margin {fin["gross_margin"]:.1f}%, debt ratio {fin["debt_ratio"]:.1f}%.</p>'
    if scem:
        analysis += f'<p>Supply chain exposure: {scem["score"]:.0f}/100 ({scem["score_label"]}).</p>'
    if bvs and bvs["score"] < 50:
        analysis += '<p style="color:#c62828">&#9888; This brand is in the danger zone. Key risk factors: low profitability, high debt, or declining sales.</p>'
    if not analysis:
        analysis = "<p>No analysis data available yet.</p>"

    sales_html = ""
    for m in sales_trend:
        models_str = ", ".join(f'{r["model_name"]} ({r["sales_volume"]:,})' for r in m["models"])
        sales_html += f'<tr><td>{m["month"]}</td><td class="num">{m["total"]:,}</td><td>{models_str}</td></tr>'

    fin_html = ""
    if fin:
        pr_cls = "g" if (fin["net_profit"] or 0) >= 0 else "r"
        fin_html = (f'<tr><td>{fin.get("report_date","")[:10]}</td><td class="num">{fin["revenue"]:.0f}</td>'
                    f'<td class="num {pr_cls}">{fin["net_profit"]:.0f}</td>'
                    f'<td class="num">{fin["gross_margin"]:.1f}%</td><td class="num">{fin["net_margin"]:.1f}%</td>'
                    f'<td class="num">{fin["roe"]:.1f}%</td><td class="num">{fin["debt_ratio"]:.1f}%</td></tr>')

    news_html = "".join(f'<tr><td>{n.get("published_at","")[:10]}</td><td>{n["title"]}</td><td>{sent_tag(n.get("sentiment",""))}</td></tr>' for n in (news or [])) or '<tr><td colspan="3">No recent news</td></tr>'

    extra = '<tr>'
    extra += f'<td>Risk: {tag(scem["score_label"], risk_cls.get(scem["score_label"],""))} ({scem["score"]:.0f}/100)</td>' if scem else '<td>—</td>'
    extra += f'<td>Delivery: {tdg["score"]:.0f}/100 (gap: {tdg["score_label"]}%)</td>' if tdg else '<td>—</td>'
    extra += f'<td>{stock["close"]:.2f} ({stock.get("trade_date","")})</td>' if stock else '<td>—</td>'
    extra += '</tr>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{brand_name} · AutoInsight</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  :root{{--text:#1a1a1a;--muted:#555;--accent:#1e40af;--border:#e5e5e5;--max-w:880px}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;font-size:15px;line-height:1.7;color:var(--text);background:#fff;-webkit-font-smoothing:antialiased}}
  main{{max-width:var(--max-w);width:90%;margin:0 auto;padding:56px 0 48px}}
  a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
  .back{{font-size:14px;color:var(--muted)}}.back a{{color:var(--muted)}}
  h1{{font-size:30px;font-weight:700;letter-spacing:-0.02em;margin-bottom:4px}}
  .sub{{color:var(--muted);font-size:15px;margin-bottom:28px}}
  section{{margin-bottom:36px}}
  section h2{{font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted);margin-bottom:14px;padding-bottom:5px;border-bottom:1px solid var(--border)}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
  .kpi{{border:1px solid var(--border);border-radius:8px;padding:14px 18px}}
  .kpi label{{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.03em}}
  .kpi .v{{font-size:26px;font-weight:700;margin:3px 0}}
  .kpi .subv{{font-size:13px;color:var(--muted)}}
  .g{{color:#2e7d32}}.y{{color:#f57f17}}.r{{color:#c62828}}
  table{{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:12px}}
  th,td{{border:1px solid var(--border);padding:7px 10px}}
  th{{background:#f8f8f6;font-weight:600;font-size:13px}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}
  .tag{{display:inline-block;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:700}}
  .tag.AAA,.tag.AA{{background:#e8f5e9;color:#2e7d32}}.tag.A,.tag.BBB{{background:#fff8e1;color:#f57f17}}.tag.BB,.tag.B,.tag.C{{background:#ffebee;color:#c62828}}
  .tag.critical{{background:#ffebee;color:#c62828}}.tag.high{{background:#fff8e1;color:#f57f17}}.tag.moderate,.tag.low{{background:#e8f5e9;color:#2e7d32}}
  .sent{{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;font-weight:600}}
  .sent.positive{{background:#e8f5e9;color:#2e7d32}}.sent.negative{{background:#ffebee;color:#c62828}}.sent.neutral{{background:#f5f5f5;color:var(--muted)}}
  .insight{{background:#f8f8f6;border-left:3px solid var(--accent);padding:16px 20px;margin:16px 0;font-size:14px;line-height:1.8}}
  footer{{margin-top:40px;padding-top:16px;border-top:1px solid var(--border);font-size:13px;color:#aaa}}
</style></head>
<body><main>
<p class="back"><a href="/auto">&larr; AutoInsight</a></p>
<h1>{brand_name}</h1><p class="sub">{subtitle}</p>
<div class="kpis">{kpi_html}</div>
<section><h2>Analysis</h2><div class="insight">{analysis}</div></section>
<section><h2>Sales Trend</h2><table><thead><tr><th>Month</th><th>Total</th><th>Top Models</th></tr></thead><tbody>{sales_html}</tbody></table></section>
<section><h2>Financials</h2><table><thead><tr><th>Report Date</th><th>Revenue (B)</th><th>Net Profit (B)</th><th>Gross Margin</th><th>Net Margin</th><th>ROE</th><th>D/E</th></tr></thead><tbody>{fin_html}</tbody></table></section>
<section><h2>Recent News</h2><table><thead><tr><th>Date</th><th>Title</th><th>Sentiment</th></tr></thead><tbody>{news_html}</tbody></table></section>
<section><h2>Supply Chain &amp; Tech</h2><table><thead><tr><th>Supply Chain</th><th>Tech Delivery</th><th>Stock</th></tr></thead><tbody>{extra}</tbody></table></section>
<footer><p>AutoInsight · <a href="https://github.com/ChenyuHeee/chinese-car-watch">GitHub</a> · For research purposes only</p></footer>
</main></body></html>""")


# ── API Endpoints ──────────────────────────────────────────

def _simple_md(md: str) -> str:
    """Minimal markdown→HTML converter."""
    import re
    lines = md.split("\n")
    out = []
    in_list = False
    for line in lines:
        if line.strip() in ("---", "***", "___"):
            if in_list: out.append("</ul>"); in_list = False
            out.append("<hr>")
            continue
        if line.startswith("# "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h1>{line[2:]}</h1>")
            continue
        if line.startswith("## "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h2>{line[3:]}</h2>")
            continue
        if line.startswith("### "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<h3>{line[4:]}</h3>")
            continue
        if line.startswith("> "):
            if in_list: out.append("</ul>"); in_list = False
            out.append(f"<blockquote>{_inline_md(line[2:])}</blockquote>")
            continue
        if "|" in line and line.count("|") >= 2:
            if in_list: out.append("</ul>"); in_list = False
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(c.replace("-","").replace(":","").strip() == "" for c in cells):
                continue
            tag = "th" if not out or not out[-1].startswith("<tr>") else "td"
            row_html = "".join(f"<{tag}>{_inline_md(c)}</{tag}>" for c in cells)
            if not out or not out[-1].startswith("<tr"):
                out.append("<table>")
            out.append(f"<tr>{row_html}</tr>")
            continue
        if line.startswith("- "):
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline_md(line[2:])}</li>")
            continue
        if in_list: out.append("</ul>"); in_list = False
        if line.strip():
            out.append(f"<p>{_inline_md(line)}</p>")
        elif out and not out[-1].startswith("<table"):
            out.append("<br>")
    if in_list: out.append("</ul>")
    return "\n".join(out)


def _inline_md(text: str) -> str:
    """Handle inline: bold, italic, code, links, images."""
    import re
    text = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<img src="\2" alt="\1" style="max-width:100%">', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)
    return text


@app.get("/auto/api/health")
async def health_check():
    db = _get_db()
    latest = db.query_one("SELECT month FROM sales_monthly ORDER BY month DESC LIMIT 1")
    return {"status": "ok", "version": "0.2.0", "latest_data_month": latest["month"] if latest else None, "server_time": datetime.now().isoformat()}


@app.get("/auto/api/bvs/{brand}")
async def get_bvs(brand: str):
    db = _get_db()
    result = db.get_latest_agent_result("bvs", brand)
    if not result:
        raise HTTPException(status_code=404, detail=f"No BVS rating for '{brand}'")
    return {"brand": result["target_name"], "rating": result["score_label"], "score": result["score"], "date": result["run_date"], "details": json.loads(result["details"]) if result["details"] else {}}


@app.get("/auto/api/bvs")
async def list_bvs(limit: int = Query(default=20, le=100), min_score: float = Query(default=None)):
    db = _get_db()
    rows = db.query("SELECT target_name, score_label, score, run_date FROM agent_results WHERE product='bvs' ORDER BY run_date DESC, score ASC LIMIT ?", (limit,))
    results = [{"brand": r["target_name"], "rating": r["score_label"], "score": r["score"], "date": r["run_date"]} for r in rows]
    if min_score is not None:
        results = [r for r in results if r["score"] >= min_score]
    return {"count": len(results), "results": results}


@app.get("/auto/api/scem")
async def list_scem(limit: int = Query(default=20, le=100)):
    db = _get_db()
    rows = db.query("SELECT target_name, score_label, score, run_date FROM agent_results WHERE product='scem' ORDER BY run_date DESC, score DESC LIMIT ?", (limit,))
    return {"count": len(rows), "results": [{"brand": r["target_name"], "risk": r["score_label"], "score": r["score"], "date": r["run_date"]} for r in rows]}


@app.get("/auto/api/tdg")
async def list_tdg(limit: int = Query(default=20, le=100)):
    db = _get_db()
    rows = db.query("SELECT target_name, score_label, score, run_date FROM agent_results WHERE product='tdg' ORDER BY run_date DESC, score DESC LIMIT ?", (limit,))
    return {"count": len(rows), "results": [{"brand": r["target_name"], "gap": r["score_label"], "delivery": r["score"], "date": r["run_date"]} for r in rows]}


@app.get("/auto/api/sales/ranking")
async def sales_ranking(top_n: int = Query(default=20, le=100), month: str = Query(default=None)):
    db = _get_db()
    rows = db.get_latest_sales() if not month else db.query("SELECT * FROM sales_monthly WHERE month=? ORDER BY rank LIMIT ?", (month, top_n))
    return {"month": rows[0]["month"] if rows else None, "results": [{"rank": r["rank"], "model": r["model_name"], "brand": r["brand_name"], "sales": r["sales_volume"], "is_nev": bool(r["is_nev"]), "price": r["price_range"]} for r in rows[:top_n]]}


@app.get("/auto/api/all-products")
async def all_products():
    db = _get_db()
    bvs = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='bvs' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='bvs') ORDER BY score DESC")
    scem = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='scem' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='scem') ORDER BY score DESC")
    tdg = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='tdg' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='tdg') ORDER BY score DESC")
    return {"bvs": [{"brand": r["target_name"], "rating": r["score_label"], "score": r["score"]} for r in bvs], "scem": [{"brand": r["target_name"], "risk": r["score_label"], "exposure": r["score"]} for r in scem], "tdg": [{"brand": r["target_name"], "gap": r["score_label"], "delivery": r["score"]} for r in tdg]}


@app.get("/auto/api/brand/{brand_name}")
async def brand_api(brand_name: str):
    db = _get_db()
    bvs = db.query_one("SELECT score_label, score, run_date FROM agent_results WHERE product='bvs' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    scem = db.query_one("SELECT score_label, score FROM agent_results WHERE product='scem' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    tdg = db.query_one("SELECT score_label, score FROM agent_results WHERE product='tdg' AND target_name=? ORDER BY run_date DESC", (brand_name,))
    stock = db.query_one("SELECT close, trade_date FROM stock_prices WHERE brand=? ORDER BY trade_date DESC", (brand_name,))
    fin = db.query_one("SELECT * FROM financial_reports WHERE brand=? ORDER BY report_date DESC LIMIT 1", (brand_name,))
    news = db.query("SELECT title, source, published_at, sentiment FROM news_articles WHERE related_brands LIKE ? ORDER BY published_at DESC LIMIT 5", (f"%{brand_name}%",))
    sales_r = db.query("SELECT month, model_name, sales_volume, rank FROM sales_monthly WHERE brand_name LIKE ? ORDER BY month DESC, rank ASC LIMIT 50", (f"%{brand_name}%",))
    monthly_totals = defaultdict(int)
    monthly_models = defaultdict(list)
    for r in sales_r:
        monthly_totals[r["month"]] += r["sales_volume"]
        monthly_models[r["month"]].append({"model": r["model_name"], "sales": r["sales_volume"], "rank": r["rank"]})
    sales_trend = [{"month": m, "total": monthly_totals[m], "models": monthly_models[m][:5]} for m in sorted(monthly_totals.keys(), reverse=True)[:6]]
    latest_sales = sum(r["sales_volume"] for r in sales_r if r["month"] == (sales_r[0]["month"] if sales_r else ""))
    sentiment = db.query("SELECT * FROM social_sentiment WHERE brand_name=? ORDER BY period DESC LIMIT 2", (brand_name,))
    return {
        "brand": brand_name,
        "bvs": {"rating": bvs["score_label"], "score": bvs["score"], "date": bvs["run_date"]} if bvs else None,
        "scem": {"risk": scem["score_label"], "exposure": scem["score"]} if scem else None,
        "tdg": {"gap": tdg["score_label"], "delivery": tdg["score"]} if tdg else None,
        "sales": {"latest_month_total": latest_sales, "trend": sales_trend},
        "financial": {"report_date": fin["report_date"][:10] if fin and fin["report_date"] else None, "revenue": fin["revenue"] if fin else None, "net_profit": fin["net_profit"] if fin else None, "gross_margin": fin["gross_margin"] if fin else None, "net_margin": fin["net_margin"] if fin else None, "roe": fin["roe"] if fin else None, "debt_ratio": fin["debt_ratio"] if fin else None} if fin else None,
        "stock": {"price": stock["close"], "date": stock["trade_date"]} if stock else None,
        "news": [{"title": n["title"], "source": n["source"], "date": n["published_at"], "sentiment": n["sentiment"]} for n in (news or [])],
        "sentiment": [{"period": s["period"], "positive": s["positive_ratio"], "negative": s["negative_ratio"], "mentions": s["total_mentions"]} for s in (sentiment or [])],
    }


@app.get("/auto/api/stats")
async def overview_stats():
    db = _get_db()
    latest = db.get_latest_sales()
    if not latest:
        raise HTTPException(status_code=404, detail="No sales data")
    total_sales = sum(r["sales_volume"] for r in latest)
    nev_sales = sum(r["sales_volume"] for r in latest if r["is_nev"])
    nev_pct = round(nev_sales / total_sales * 100, 1) if total_sales else 0
    from collections import Counter
    brands = Counter(r["brand_name"] for r in latest)
    return {"month": latest[0]["month"], "total_sales": total_sales, "nev_share_pct": nev_pct, "top_brands": brands.most_common(10), "model_count": len(latest)}


@app.get("/auto/api/report/latest")
async def latest_report():
    db = _get_db()
    row = db.query_one("SELECT * FROM agent_results WHERE product='weekly_report' ORDER BY run_date DESC LIMIT 1")
    if not row:
        raise HTTPException(status_code=404, detail="No reports yet")
    return {"date": row["run_date"], "report_md": row["report_md"]}
