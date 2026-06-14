"""
Generate charts and summary stats from scraped sales data.

Usage:
  python scripts/generate_charts.py                # latest month
  python scripts/generate_charts.py --month 202605 # specific month
  python scripts/generate_charts.py --all           # all available months
"""

import argparse
import csv
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
CHARTS_DIR = PROJECT_ROOT / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    log.warning("matplotlib not installed — charts disabled")


def load_latest(prefix: str, subdir: str = "sales") -> list[dict]:
    """Load the most recent CSV for a given page type prefix."""
    data_dir = DATA_DIR / subdir
    if not data_dir.exists():
        return []

    candidates = []
    for year_dir in sorted(data_dir.iterdir(), reverse=True):
        if not year_dir.is_dir():
            continue
        for fp in sorted(year_dir.glob(f"*_{prefix}.csv"), reverse=True):
            candidates.append(fp)
            break
        if candidates:
            break
    if not candidates:
        return []

    fp = candidates[0]
    log.info("loading %s", fp)
    with open(fp, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_stats(rows: list[dict], ev_names: set | None = None) -> dict:
    """Compute summary statistics from sales rows.

    If ev_names is provided, use it as the definitive set of NEV model names.
    """
    total = 0
    nev_count = 0
    nev_sales = 0
    ice_sales = 0
    brands = defaultdict(int)

    nev_keywords = [
        "EV", "ev", "电动", "新能源", "DM", "EREV", "PHEV", "纯电", "混动",
        "增程", "Pro新能源", "PLUS新能源", "DM-i", "DM-p",
    ]
    nev_brands = {
        "特斯拉", "Tesla", "Model", "理想", "蔚来", "小鹏", "零跑", "极氪",
        "问界", "AITO", "深蓝", "方程豹", "腾势", "阿维塔", "岚图", "智己",
        "小米", "鸿蒙智行", "银河", "乐道", "iCar", "星愿", "别克至境",
        "铂智", "奔腾小马", "QQ3",
    }
    nev_nameplates = {
        "星愿", "钛7", "钛3", "海狮", "海豹", "海豚", "海鸥", "元UP",
        "宋Pro", "宋Ultra", "秦L", "秦PLUS", "缤果", "宏光MINIEV",
        "MG4", "长安启源", "AION", "逸动", "哈弗猛龙",
    }

    for r in rows:
        name = r.get("name", "")
        sales_str = r.get("sales", "0")
        try:
            s = int(sales_str)
        except (ValueError, TypeError):
            continue
        total += s
        brands[name.split()[0] if " " not in name else name] += s

        is_nev = False

        # 1) check against EV page ground truth
        if ev_names and name in ev_names:
            is_nev = True

        # 2) keyword match
        if not is_nev:
            for kw in nev_keywords:
                if kw.lower() in name.lower():
                    is_nev = True
                    break

        # 3) brand prefix match
        if not is_nev:
            for b in nev_brands:
                if name.startswith(b):
                    is_nev = True
                    break

        # 4) nameplate prefix match
        if not is_nev:
            for n in nev_nameplates:
                if name.startswith(n):
                    is_nev = True
                    break

        if is_nev:
            nev_sales += s
            nev_count += 1
        else:
            ice_sales += s

    top10 = sorted(rows, key=lambda r: int(r.get("sales", "0") or "0"), reverse=True)[:10]

    return {
        "total_rows": len(rows),
        "total_sales": total,
        "nev_sales": nev_sales,
        "nev_pct": round(nev_sales / total * 100, 1) if total else 0,
        "ice_sales": ice_sales,
        "top10": [{"rank": r["rank"], "name": r["name"], "sales": r["sales"]} for r in top10],
        "top_brands": sorted(brands.items(), key=lambda x: x[1], reverse=True)[:10],
    }


def generate_markdown_report(style_rows: list[dict], ev_rows: list[dict],
                             brand_rows: list[dict], month: str) -> str:
    """Generate a bilingual markdown report."""
    ev_names = {r["name"] for r in ev_rows}
    style_stats = compute_stats(style_rows, ev_names)
    brand_stats = compute_stats(brand_rows)
    # EV-specific stats don't need ev_names (all are EV by definition)
    ev_stats_raw = compute_stats(ev_rows)

    # format month
    y, m = month[:4], month[4:]
    display_month = f"{y}-{m}"

    lines = []
    lines.append(f"# China Auto Market Monthly — {display_month} / 中国汽车市场月报")
    lines.append("")
    lines.append(f"> Auto-generated report · Data source: xl.16888.com · Scraped: {datetime.now().isoformat()[:10]}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── NEV penetration ──
    lines.append("## NEV Penetration / 新能源渗透率")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| NEV sales among top-ranked models | **{style_stats['nev_pct']}%** |")
    lines.append(f"| Total sales captured (top models) | {style_stats['total_sales']:,} |")
    lines.append("")

    # ── Top 20 models ──
    lines.append("## Top 20 Models / 车型销量 TOP20")
    lines.append("")
    lines.append("| Rank | Model | Sales |")
    lines.append("|------|-------|------:|")
    for r in style_rows[:20]:
        lines.append(f"| {r['rank']} | {r['name']} | {r['sales']} |")
    lines.append("")

    # ── Top 10 EVs ──
    lines.append("## Top 10 EV Models / 电动车销量 TOP10")
    lines.append("")
    lines.append("| Rank | Model | Sales | Price Range |")
    lines.append("|------|-------|------:|-------------|")
    for r in ev_rows[:10]:
        price = r.get("price_range", "-")
        lines.append(f"| {r['rank']} | {r['name']} | {r['sales']} | {price} |")
    lines.append("")

    # ── Top 15 brands ──
    lines.append("## Top 15 Brands / 品牌销量 TOP15")
    lines.append("")
    lines.append("| Rank | Brand | Sales | Share |")
    lines.append("|------|-------|------:|------:|")
    for r in brand_rows[:15]:
        lines.append(f"| {r['rank']} | {r['name']} | {r['sales']} | {r.get('price_range', '-')} |")
    lines.append("")

    # ── NEV vs ICE comparison ──
    lines.append("## NEV vs ICE Breakdown / 新能源 vs 燃油")
    lines.append("")
    lines.append(f"- NEV share of top-50 models: **{style_stats['nev_pct']}%**")
    lines.append(f"- ICE share of top-50 models: **{round(100 - style_stats['nev_pct'], 1)}%**")
    lines.append("")

    # ── Key observations ──
    lines.append("## Key Observations / 关键发现")
    lines.append("")
    top5 = style_rows[:5]
    nev_in_top10 = sum(
        1 for r in style_rows[:10]
        if any(kw.lower() in r.get("name", "").lower()
               for kw in ["ev", "电动", "新能源", "dm", "erev", "phev", "纯电", "混动", "增程", "model", "星愿", "小米", "理想", "零跑", "问界", "钛"])
        or any(r.get("name", "").startswith(b) for b in ["Model", "星愿", "小米", "理想", "零跑", "问界", "钛", "海", "元", "深蓝"])
    )
    lines.append(f"1. **{nev_in_top10}/10** of the top 10 models are NEVs.")
    lines.append(f"2. The top-selling model (**{top5[0]['name']}**) sold **{top5[0]['sales']}** units.")
    lines.append(f"3. Brand leader: **{brand_rows[0]['name']}** with **{brand_rows[0]['sales']}** units.")
    lines.append("")

    lines.append("---")
    lines.append("*This report is auto-generated. See `data/` for raw CSV files.*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate charts and reports")
    parser.add_argument("--month", help="Month in YYYYMM format (default: latest)")
    parser.add_argument("--all", action="store_true", help="Process all available months")
    args = parser.parse_args()

    # load data
    style_rows = load_latest("style")
    ev_rows = load_latest("ev")
    brand_rows = load_latest("brand", subdir="brands")

    if not style_rows:
        log.error("no sales data found. Run scrape_sales.py first.")
        return

    month = args.month or style_rows[0].get("month", datetime.now().strftime("%Y%m"))

    # generate markdown report
    report = generate_markdown_report(style_rows, ev_rows, brand_rows, month)
    report_path = CHARTS_DIR / f"report-{month}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    log.info("report saved → %s", report_path)

    # generate JSON summary for programmatic use
    summary = {
        "month": month,
        "generated_at": datetime.now().isoformat(),
        "model_stats": compute_stats(style_rows),
        "ev_stats": compute_stats(ev_rows),
        "brand_stats": compute_stats(brand_rows),
    }
    summary_path = CHARTS_DIR / f"summary-{month}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info("summary saved → %s", summary_path)

    # print quick summary
    stats = compute_stats(style_rows)
    print(f"\n{month} Quick Stats:")
    print(f"  NEV penetration (top models): {stats['nev_pct']}%")
    print(f"  Total sales captured: {stats['total_sales']:,}")
    print(f"  Top model: {stats['top10'][0]['name']} ({stats['top10'][0]['sales']})")


if __name__ == "__main__":
    main()
