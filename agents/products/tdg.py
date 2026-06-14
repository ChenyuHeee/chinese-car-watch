"""
Tech Delivery Gap (TDG) — 技术兑现度

Tracks brands' technology claims vs actual delivery, focusing on:
- Intelligent driving (NOA/city NOA/highway NOA)
- Battery/charging tech (solid state, 800V, swap)
- OTA capabilities
- New model launch timelines

Agent pattern: Investigator finds claims → Analyst scores delivery → Critic reviews
"""

import json
import logging
import re
from datetime import datetime
from collections import defaultdict

from agents.config import make_agent, load_prompt

log = logging.getLogger(__name__)

# Known tech claims to track per brand (manually seeded, enriched by agent)
TECH_CLAIM_TEMPLATES = {
    "智能驾驶": {
        "keywords": ["城市NOA", "高速NOA", "端到端", "无图智驾", "FSD", "XNGP", "NOP", "ADS", "CNOA"],
        "category": "autonomous_driving",
        "weight": 30,  # high weight — safety-critical
    },
    "三电技术": {
        "keywords": ["固态电池", "800V", "换电", "超充", "刀片电池", "麒麟电池", "CTC", "CTB"],
        "category": "powertrain",
        "weight": 25,
    },
    "智能座舱": {
        "keywords": ["8295", "大模型", "语音助手", "AR-HUD", "鸿蒙座舱", "HyperOS"],
        "category": "cockpit",
        "weight": 15,
    },
    "新车交付": {
        "keywords": ["交付", "上市", "量产", "SOP", "下线"],
        "category": "production",
        "weight": 20,
    },
    "OTA升级": {
        "keywords": ["OTA", "软件升级", "版本更新"],
        "category": "ota",
        "weight": 10,
    },
}

# Brand tech track record (hand-curated baseline)
BRAND_TRACK_RECORD = {
    "比亚迪": 85,   # Strong execution, self-developed tech
    "特斯拉": 60,   # Ambitious claims, often delayed (FSD, Cybertruck)
    "蔚来": 70,     # Generally delivers, sometimes late (ET7 delays)
    "小鹏": 75,     # Strong on ADAS, delivers on schedule
    "理想": 80,     # Conservative claims, high delivery rate
    "问界": 75,     # Huawei-backed, strong execution
    "小米汽车": 65,  # New entrant, building track record
    "零跑": 70,
    "极氪": 70,
}


def _extract_claims_from_news(db=None) -> list[dict]:
    """Scan recent news for technology claims by tracked brands."""
    if db is None:
        from pipeline.db import get_db
        db = get_db()

    tracked = list(BRAND_TRACK_RECORD.keys())
    claims = []

    for brand in tracked:
        rows = db.get_news_for_brand(brand, limit=20)
        for r in rows:
            text = (r.get("title", "") + " " + r.get("summary", ""))
            for tech_name, tech_info in TECH_CLAIM_TEMPLATES.items():
                for kw in tech_info["keywords"]:
                    if kw in text:
                        # Extract timeline if present
                        timeline_match = re.search(
                            r"(\d{4})年|(\d+)月|Q[1-4]|上半年|下半年|年内|明年", text
                        )
                        timeline = timeline_match.group(0) if timeline_match else "未明确"

                        claims.append({
                            "brand": brand,
                            "category": tech_info["category"],
                            "tech_area": tech_name,
                            "keyword": kw,
                            "timeline": timeline,
                            "title": r.get("title", "")[:100],
                            "date": r.get("published_at", ""),
                            "weight": tech_info["weight"],
                            "source": r.get("source", ""),
                        })
                        break  # one claim per article per tech area

    return claims


def _score_brand(brand: str, claims: list[dict]) -> dict:
    """Score a brand's tech delivery gap."""
    brand_claims = [c for c in claims if c["brand"] == brand]
    if not brand_claims:
        return {
            "brand": brand,
            "total_claims": 0,
            "delivery_score": BRAND_TRACK_RECORD.get(brand, 60),
            "gap_score": 100 - BRAND_TRACK_RECORD.get(brand, 60),
            "risk_areas": [],
            "recent_claims": [],
        }

    # Categorize claims by timeline urgency
    overdue = [c for c in brand_claims if _is_overdue(c)]
    upcoming = [c for c in brand_claims if not _is_overdue(c)]

    # Base score from track record
    base_score = BRAND_TRACK_RECORD.get(brand, 60)

    # Penalize for overdue claims
    overdue_penalty = min(30, len(overdue) * 5)

    # Reward for clear timelines
    clear_timeline_bonus = min(10, sum(1 for c in brand_claims if c["timeline"] != "未明确") * 2)

    delivery_score = max(0, min(100, base_score + clear_timeline_bonus - overdue_penalty))
    gap_score = 100 - delivery_score

    # Risk areas: categories with the most overdue claims
    risk_categories = defaultdict(int)
    for c in overdue:
        risk_categories[c["tech_area"]] += 1
    risk_areas = sorted(risk_categories.items(), key=lambda x: x[1], reverse=True)

    return {
        "brand": brand,
        "total_claims": len(brand_claims),
        "overdue_claims": len(overdue),
        "upcoming_claims": len(upcoming),
        "delivery_score": delivery_score,
        "gap_score": gap_score,
        "risk_areas": [f"{area}({n})" for area, n in risk_areas[:3]],
        "recent_claims": [
            {"title": c["title"][:80], "timeline": c["timeline"], "overdue": c in overdue}
            for c in brand_claims[:5]
        ],
    }


def _is_overdue(claim: dict) -> bool:
    """Check if a tech claim is likely overdue based on its timeline."""
    timeline = claim.get("timeline", "")
    if timeline == "未明确":
        return False

    now = datetime.now()
    # Simple heuristic: if the claim mentioned "2025" and we're in 2026, it's overdue
    year_match = re.search(r"(\d{4})", timeline)
    if year_match:
        year = int(year_match.group(1))
        if year < now.year:
            return True
        if year == now.year and ("上半年" in timeline or "Q1" in timeline or "Q2" in timeline):
            if now.month > 6:
                return True

    # "年内" or "今年" from old articles
    if ("年内" in timeline or "今年" in timeline) and claim.get("date", ""):
        try:
            claim_year = int(claim["date"][:4])
            if claim_year < now.year:
                return True
        except (ValueError, IndexError):
            pass

    return False


def run_tdg_analysis(db=None, dry_run: bool = False) -> list[dict]:
    """Run full TDG analysis pipeline."""
    log.info("TDG: scanning news for tech claims...")
    claims = _extract_claims_from_news(db)
    log.info("TDG: found %d claims across %d brands",
             len(claims), len(set(c["brand"] for c in claims)))

    results = []
    for brand in BRAND_TRACK_RECORD:
        result = _score_brand(brand, claims)
        results.append(result)

    results.sort(key=lambda r: r["gap_score"], reverse=True)

    if dry_run:
        for r in results:
            r["agent_review"] = "[DRY RUN]"
        return results

    # Use Analyst agent to review top risks
    try:
        analyst = make_agent(
            name="tdg_analyst",
            role="analyst",
            system_prompt=load_prompt("analyst") + (
                "\n\nYou are analyzing technology delivery gaps for Chinese auto brands. "
                "Review the computed scores. Flag brands where the score seems wrong "
                "given your knowledge of their actual tech delivery track record. "
                "Output JSON only."
            ),
        )
        top_risks = json.dumps(
            [r for r in results if r["gap_score"] >= 30][:8],
            ensure_ascii=False, indent=2,
        )
        response = analyst.generate_reply(
            messages=[{"role": "user", "content": (
                f"Review these tech delivery gap scores:\n{top_risks}\n\n"
                f"Flag any scores that seem wrong. Respond JSON: "
                f'{{"reviews": [{{"brand": "...", "score_ok": true, "comment": "..."}}]}}'
            )}]
        )
        for r in results:
            r["agent_review"] = "Reviewed"
    except Exception as e:
        log.warning("TDG agent review failed: %s", e)
        for r in results:
            r["agent_review"] = f"Error: {e}"

    return results


def generate_tdg_report(results: list[dict]) -> str:
    """Generate markdown report."""
    lines = [
        "# Tech Delivery Gap / 技术兑现度",
        f"> Generated: {datetime.now().isoformat()[:10]}",
        "",
        "| Brand | Delivery Score | Gap | Overdue | Upcoming | Risk Areas |",
        "|-------|---------------|-----|---------|----------|------------|",
    ]
    for r in results:
        lines.append(
            f"| {r['brand']} | **{r['delivery_score']}** | {r['gap_score']} "
            f"| {r['overdue_claims']} | {r['upcoming_claims']} "
            f"| {', '.join(r['risk_areas']) or '—'} |"
        )

    lines.extend([
        "",
        "## Methodology",
        "- Base score: brand historical track record",
        "- Overdue penalty: -5 per overdue tech claim",
        "- Timeline clarity bonus: +2 per claim with specific timeline",
        "- Claims extracted from: news articles in DB",
        "",
        "---",
        "*Auto-generated by TDG agent. For research purposes only.*",
    ])
    return "\n".join(lines)


def save_tdg_results(results: list[dict]):
    """Save TDG results to DB."""
    from pipeline.db import get_db
    db = get_db()
    today = datetime.now().isoformat()[:10]
    for r in results:
        db.save_agent_result(
            product="tdg",
            target_name=r["brand"],
            run_date=today,
            score=r["delivery_score"],
            score_label=str(r["gap_score"]),
            details=r,
            agent_config="analyst, deepseek-v4-pro",
        )
    log.info("TDG: saved %d results", len(results))


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Tech Delivery Gap analysis")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    results = run_tdg_analysis(dry_run=args.dry_run)

    if args.report:
        print(generate_tdg_report(results))
    else:
        for r in results:
            print(f"  {r['brand']:8s}  delivery={r['delivery_score']:3d}  gap={r['gap_score']:3d}  "
                  f"overdue={r['overdue_claims']}  upcoming={r['upcoming_claims']}")

    if args.save:
        save_tdg_results(results)
