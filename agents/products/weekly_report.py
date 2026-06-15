"""
Weekly/Monthly report generator.
Compiles latest data + agent results into a structured report.
Saves to DB and outputs Markdown.
"""

import json
import logging
from datetime import datetime
from collections import defaultdict

from agents.config import make_agent, load_prompt

log = logging.getLogger(__name__)


def generate_report(dry_run: bool = False) -> str:
    """Generate a structured report from current DB state."""
    from pipeline.db import get_db
    db = get_db()

    # ── Gather data ──
    sales = db.get_latest_sales()
    if not sales:
        return "# AutoInsight Report\n\nNo sales data available."

    month = sales[0]["month"]
    y, m = month[:4], month[4:]
    display = f"{y}-{m}"

    total = sum(r["sales_volume"] for r in sales)
    nev_count = sum(1 for r in sales[:50] if r["is_nev"])
    nev_top10 = sum(1 for r in sales[:10] if r["is_nev"])

    brand_sales = defaultdict(int)
    for r in sales:
        brand_sales[r["brand_name"]] += r["sales_volume"]
    top_brands = sorted(brand_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    top5_share = sum(s for _, s in top_brands[:5]) / total * 100

    bvs_rows = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='bvs' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='bvs') ORDER BY score DESC")
    scem_rows = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='scem' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='scem') ORDER BY score DESC LIMIT 10")
    tdg_rows = db.query("SELECT target_name, score_label, score FROM agent_results WHERE product='tdg' AND run_date=(SELECT MAX(run_date) FROM agent_results WHERE product='tdg') ORDER BY score DESC LIMIT 10")

    news_count = db.query_one("SELECT COUNT(*) as n FROM news_articles")
    news_sent = db.query("SELECT sentiment, COUNT(*) as n FROM news_articles GROUP BY sentiment")
    sent_map = {r["sentiment"]: r["n"] for r in news_sent}

    fin = db.query("SELECT brand, gross_margin, net_profit, debt_ratio FROM financial_reports ORDER BY brand, report_date DESC")
    fin_latest = {}
    seen = set()
    for r in fin:
        if r["brand"] not in seen:
            seen.add(r["brand"])
            fin_latest[r["brand"]] = r

    # ── Build markdown ──
    lines = []
    lines.append(f"# AutoInsight Monthly — {display}")
    lines.append(f"> Generated: {datetime.now().isoformat()[:16]}")
    lines.append("")

    lines.append("## 1. Market Overview")
    lines.append(f"- Total sales captured: **{total:,}** units across {len(sales)} models")
    lines.append(f"- NEV share (top 50): **{nev_count}/50** ({nev_count/50*100:.0f}%)")
    lines.append(f"- NEV share (top 10): **{nev_top10}/10**")
    lines.append(f"- Top-5 brand concentration: **{top5_share:.1f}%**")
    lines.append("")

    lines.append("### Top 15 Models")
    lines.append("| # | Model | Brand | Sales |")
    lines.append("|---|-------|-------|------:|")
    for r in sales[:15]:
        lines.append(f"| {r['rank']} | {r['model_name']} | {r['brand_name']} | {r['sales_volume']:,} |")
    lines.append("")

    lines.append("### Top 10 Brands")
    lines.append("| # | Brand | Sales | Share |")
    lines.append("|---|-------|------:|------:|")
    for i, (b, s) in enumerate(top_brands):
        lines.append(f"| {i+1} | {b} | {s:,} | {s/total*100:.1f}% |")
    lines.append("")

    lines.append("## 2. Brand Viability Score (BVS)")
    if bvs_rows:
        lines.append("| Brand | Rating | Score |")
        lines.append("|-------|--------|------:|")
        for r in bvs_rows:
            lines.append(f"| {r['target_name']} | **{r['score_label']}** | {r['score']:.0f} |")
    else:
        lines.append("No BVS ratings yet.")
    lines.append("")

    lines.append("## 3. Financial Health Summary")
    if fin_latest:
        lines.append("| Brand | Gross Margin | Net Profit (B) | D/E Ratio |")
        lines.append("|-------|-------------|----------------|-----------|")
        for b in ["比亚迪", "特斯拉", "理想", "蔚来", "小鹏", "问界"]:
            f = fin_latest.get(b, {})
            if f:
                gm = f.get("gross_margin", 0) or 0
                pr = f.get("net_profit", 0) or 0
                dr = f.get("debt_ratio", 0) or 0
                lines.append(f"| {b} | {gm:.1f}% | {pr:.0f} | {dr:.1f}% |")
    lines.append("")

    lines.append("## 4. Supply Chain Risk (SCEM)")
    if scem_rows:
        lines.append("| Brand | Risk | Exposure |")
        lines.append("|-------|------|---------:|")
        for r in scem_rows[:8]:
            lines.append(f"| {r['target_name']} | **{r['score_label']}** | {r['score']:.0f} |")
    lines.append("")

    lines.append("## 5. Data Status")
    lines.append(f"- Sales records: {len(sales)}")
    lines.append(f"- News articles (cumulative): {news_count['n'] if news_count else 0}")
    lines.append(f"- News sentiment: {sent_map}")
    lines.append(f"- Agent results: BVS ({len(bvs_rows)}), SCEM ({len(scem_rows)}), TDG ({len(tdg_rows)})")
    lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by AutoInsight. For research purposes only.*")

    report_md = "\n".join(lines)

    # ── Save to DB ──
    db.save_agent_result(
        product="weekly_report",
        target_name=f"monthly_{month}",
        run_date=datetime.now().isoformat()[:10],
        score=0,
        score_label=month,
        details={"month": month, "generated_at": datetime.now().isoformat()},
        report_md=report_md,
        agent_config="data-compilation",
    )
    log.info("Report saved: monthly_%s", month)

    return report_md


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    report = generate_report()
    print(report)
