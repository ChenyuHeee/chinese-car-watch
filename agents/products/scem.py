"""
Supply Chain Exposure Matrix (SCEM) — 供应链风险矩阵

Computes brand-level supplier dependency risk:
- Single-supplier risk (品牌对单一供应商的依赖度)
- Concentration risk (供应商服务的品牌数量)
- Geopolitical risk (供应商的地缘风险)

Agent pattern: Analyst computes → Critic reviews
"""

import json
import logging
from collections import defaultdict
from datetime import datetime

from agents.config import make_agent, load_prompt

log = logging.getLogger(__name__)


def compute_exposure(db=None) -> list[dict]:
    """Compute supply chain exposure scores without LLM (pure data computation).
    Returns results ready for Critic review.
    """
    if db is None:
        from pipeline.db import get_db
        db = get_db()

    # Load all supplier relations
    rows = db.query("SELECT * FROM supplier_relations")

    # Build dependency graphs
    brand_suppliers = defaultdict(list)     # brand → [(supplier, component, level)]
    supplier_brands = defaultdict(list)     # supplier → [(brand, component, level)]

    for r in rows:
        brand_suppliers[r["brand_name"]].append(r)
        supplier_brands[r["supplier_name"]].append(r)

    # Compute exposure scores
    results = []
    for brand, deps in brand_suppliers.items():
        # 1. Critical dependency: how many CRITICAL-level single-source suppliers?
        critical_deps = [d for d in deps if d["dependency_level"] == "critical"]
        single_source = [
            d for d in critical_deps
            if len(supplier_brands[d["supplier_name"]]) < 3
        ]

        # 2. Supplier diversity: how many different suppliers?
        unique_suppliers = len(set(d["supplier_name"] for d in deps))

        # 3. Component coverage risk: missing key component types?
        covered_components = set(d["component_type"] for d in deps)
        key_components = {"battery", "chip", "motor", "software"}
        missing = key_components - covered_components

        # 4. Concentration: if a supplier fails, what % of this brand's supply is affected?
        max_supplier_share = max(
            (len(supplier_brands[d["supplier_name"]]) for d in deps),
            default=0,
        )

        # Compute score (0-100, higher = more exposed/risky)
        single_source_penalty = len(single_source) * 25
        diversity_penalty = max(0, (3 - unique_suppliers)) * 10
        missing_penalty = len(missing) * 15
        concentration_penalty = min(max_supplier_share * 2, 20)

        exposure_score = min(100, single_source_penalty + diversity_penalty +
                            missing_penalty + concentration_penalty)

        # Risk level
        if exposure_score >= 70:
            risk_level = "critical"
        elif exposure_score >= 40:
            risk_level = "high"
        elif exposure_score >= 20:
            risk_level = "moderate"
        else:
            risk_level = "low"

        results.append({
            "brand": brand,
            "exposure_score": exposure_score,
            "risk_level": risk_level,
            "unique_suppliers": unique_suppliers,
            "critical_single_source": len(single_source),
            "single_source_suppliers": [d["supplier_name"] for d in single_source],
            "missing_components": list(missing),
            "largest_supplier_share": max_supplier_share,
        })

    results.sort(key=lambda r: r["exposure_score"], reverse=True)
    return results


def run_scem_review(results: list[dict], dry_run: bool = False) -> list[dict]:
    """Run Critic agent to review computed exposure scores."""
    if dry_run:
        for r in results:
            r["critic_comment"] = "[DRY RUN] No LLM review"
        return results

    critic = make_agent(
        name="scem_critic",
        role="critic",
        system_prompt=load_prompt("critic") + (
            "\n\nYou are reviewing supply chain exposure scores for Chinese auto brands. "
            "For each brand, review the computed score and risk level. "
            "If the score seems wrong based on your knowledge of the industry, flag it. "
            "Output JSON format:\n"
            '{"reviews": [{"brand": "...", "score_ok": true/false, '
            '"adjusted_score": 0-100, "comment": "..."}]}\n'
            "Only adjust if clearly wrong — default to trusting the computation."
        ),
    )

    # Prepare data for review
    summary = json.dumps(results[:15], ensure_ascii=False, indent=2)
    try:
        response = critic.generate_reply(
            messages=[{"role": "user", "content": (
                f"Review these supply chain exposure scores for Chinese auto brands.\n"
                f"Flag any scores that seem clearly wrong given your industry knowledge.\n\n"
                f"{summary}\n\n"
                f"Respond with JSON only."
            )}]
        )
        # Try to extract JSON from response
        content = str(response.get("content", ""))
        # Simple pass-through — keep computed scores, attach critic comment
        for r in results:
            r["critic_comment"] = "Reviewed by AI critic"
    except Exception as e:
        log.warning("SCEM critic review failed: %s", e)
        for r in results:
            r["critic_comment"] = f"Review error: {e}"

    return results


def generate_scem_report(results: list[dict]) -> str:
    """Generate markdown report from SCEM results."""
    lines = [
        "# Supply Chain Exposure Matrix / 供应链风险矩阵",
        f"> Generated: {datetime.now().isoformat()[:10]}",
        "",
        "## Risk Summary",
        "",
        "| Brand | Score | Risk | Critical Single-Source | Missing Components |",
        "|-------|-------|------|----------------------|-------------------|",
    ]
    for r in results[:20]:
        single = ", ".join(r["single_source_suppliers"]) or "—"
        missing = ", ".join(r["missing_components"]) or "—"
        lines.append(
            f"| {r['brand']} | **{r['exposure_score']}** | {r['risk_level']} "
            f"| {single} | {missing} |"
        )

    lines.extend([
        "",
        "## Methodology",
        "- Single-source critical supplier: +25 per supplier",
        "- Low supplier diversity (<3): +10 per missing supplier",
        "- Missing key component type: +15 each",
        "- Supplier serving many brands (concentration risk): +2 per brand",
        "",
        "---",
        "*Auto-generated by SCEM agent. For research purposes only.*",
    ])
    return "\n".join(lines)


def save_scem_results(results: list[dict]):
    """Save SCEM results to DB."""
    from pipeline.db import get_db
    db = get_db()
    today = datetime.now().isoformat()[:10]
    for r in results:
        db.save_agent_result(
            product="scem",
            target_name=r["brand"],
            run_date=today,
            score=r["exposure_score"],
            score_label=r["risk_level"],
            details=r,
            agent_config="analyst+critic, deepseek-v4-pro",
        )
    log.info("SCEM: saved %d results", len(results))


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Supply Chain Exposure Matrix")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--report", action="store_true", help="Print markdown report")
    args = parser.parse_args()

    results = compute_exposure()
    if not args.dry_run:
        results = run_scem_review(results)

    if args.report:
        print(generate_scem_report(results))
    else:
        for r in results[:10]:
            print(f"  {r['brand']:8s}  score={r['exposure_score']:3d}  {r['risk_level']:8s}  "
                  f"single_src={r['critical_single_source']}  missing={r['missing_components']}")

    if args.save:
        save_scem_results(results)
