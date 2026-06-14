"""
Brand Viability Score (BVS) — 品牌生存力评级

Uses AG2 Nested Chat for Red-Blue Debate pattern:
  Red Analyst: argues the brand WILL fail within 12 months
  Blue Analyst: argues the brand will SURVIVE
  Judge: evaluates both arguments, produces final rating + confidence
"""

import json
import logging
from datetime import datetime
from typing import Optional

import yaml
from autogen import ConversableAgent, initiate_chats

from agents.config import PROJECT_ROOT, make_agent, load_prompt
from agents.tools.db_query import DB_TOOLS

log = logging.getLogger(__name__)

# Load brand registry
BRANDS_YAML = PROJECT_ROOT / "config" / "brands.yaml"
with open(BRANDS_YAML, encoding="utf-8") as f:
    BRAND_DATA = yaml.safe_load(f)
KNOWN_BRANDS = [b["name"] for b in BRAND_DATA["brands"]]

# BVS Rating Scale
RATING_SCALE = {
    "AAA": "行业领导者，现金流充裕，无短期生存风险",
    "AA": "强势品牌，具备护城河，但面临特定挑战",
    "A": "稳健运营，有差异化优势，外部融资通畅",
    "BBB": "经营正常，但过度依赖外部融资或单一车型",
    "BB": "高风险，销量持续下滑，融资端承压",
    "B": "极度危险，12个月内可能退出市场或被并购",
    "C": "已实质性停摆，破产/清算/被接管",
}


def _rating_to_number(rating: str) -> float:
    """Convert rating to numeric score for comparison: AAA=100, C=0."""
    mapping = {"AAA": 95, "AA": 82, "A": 68, "BBB": 55, "BB": 35, "B": 15, "C": 5}
    return mapping.get(rating, 0)


def _build_debate_prompt(brand: str, brand_info: Optional[dict] = None) -> str:
    """Build the initial debate prompt with brand context."""
    context_lines = [f"## Brand: {brand}"]
    if brand_info:
        context_lines.append(f"Parent: {brand_info.get('parent', 'N/A')}")
        context_lines.append(f"Founded: {brand_info.get('founded', 'N/A')}")
        context_lines.append(f"Type: {brand_info.get('type', 'N/A')}")
        context_lines.append(f"Listed: {brand_info.get('is_listed', False)}")
        if brand_info.get("stock_codes"):
            context_lines.append(f"Stock: {', '.join(brand_info['stock_codes'])}")
        if brand_info.get("notes"):
            context_lines.append(f"Notes: {brand_info['notes']}")

    context_lines.append("")
    context_lines.append("## Task")
    context_lines.append(f"Conduct a rigorous Red-Blue debate on whether **{brand}** will survive the next 12 months.")
    context_lines.append("")
    context_lines.append("Red Analyst: Argue that the brand WILL fail. Focus on negative signals.")
    context_lines.append("Blue Analyst: Argue that the brand will SURVIVE. Focus on resilience factors.")
    context_lines.append("")
    context_lines.append("Use the available database tools to gather evidence before making arguments.")
    context_lines.append("Both analysts must cite specific data (sales numbers, trends, funding facts).")
    context_lines.append("")
    context_lines.append("After both sides present, the Judge will:")
    context_lines.append("1. Evaluate the quality of each side's evidence")
    context_lines.append("2. Assign a BVS rating (AAA/AA/A/BBB/BB/B/C)")
    context_lines.append("3. State confidence level (high/medium/low)")
    context_lines.append("4. Provide a one-paragraph justification")
    context_lines.append("")
    context_lines.append("## BVS Rating Scale")
    for rating, desc in RATING_SCALE.items():
        context_lines.append(f"- **{rating}**: {desc}")

    return "\n".join(context_lines)


def _register_tools(agent: ConversableAgent):
    """Register database query tools on an agent."""
    from autogen import register_function
    for tool in DB_TOOLS:
        register_function(
            tool, caller=agent, executor=agent,
            name=tool.__name__, description=tool.__doc__ or "",
        )


def evaluate_brand(brand: str, dry_run: bool = False) -> dict:
    """Run the BVS debate for a single brand.

    Args:
        brand: brand name (must be in brands.yaml)
        dry_run: if True, simulate without LLM calls

    Returns:
        dict with rating, confidence, justification, debate_transcript
    """
    brand_info = next((b for b in BRAND_DATA["brands"] if b["name"] == brand), None)
    if not brand_info:
        log.warning("Brand '%s' not found in registry, using generic analysis", brand)
        brand_info = {"name": brand}

    debate_prompt = _build_debate_prompt(brand, brand_info)
    judge_prompt = load_prompt("analyst") + "\n\nYou are acting as a JUDGE. Evaluate the debate and produce a final rating."

    if dry_run:
        return {
            "brand": brand,
            "rating": "A",
            "confidence": "low",
            "score": 68.0,
            "justification": f"[DRY RUN] Simulated rating for {brand}. No LLM calls made.",
            "run_date": datetime.now().isoformat()[:10],
        }

    # Create agents
    red = make_agent(
        name=f"red_{brand}",
        role="analyst",
        system_prompt=load_prompt("analyst") + f"\n\nYou are the RED TEAM analyst. Your job is to find and argue the case that **{brand}** WILL FAIL within 12 months. Be aggressive but factual. Cite data.",
    )
    blue = make_agent(
        name=f"blue_{brand}",
        role="analyst",
        system_prompt=load_prompt("analyst") + f"\n\nYou are the BLUE TEAM analyst. Your job is to argue that **{brand}** will SURVIVE and remain viable. Highlight strengths and resilience factors. Cite data.",
    )
    judge = make_agent(
        name=f"judge_{brand}",
        role="critic",
        system_prompt=judge_prompt,
    )

    _register_tools(red)
    _register_tools(blue)
    _register_tools(judge)

    # Run the debate via sequential chats
    try:
        chat_results = initiate_chats([
            {
                "sender": red,
                "recipient": blue,
                "message": debate_prompt,
                "max_turns": 4,  # red → blue → red → blue
                "clear_history": True,
            },
            {
                "sender": judge,
                "recipient": red,
                "message": "Review the debate above. Based on the evidence presented by both sides, produce your final judgment: BVS rating + confidence + justification.",
                "max_turns": 1,
                "clear_history": False,
                "summary_method": "last_msg",
            },
        ])

        # Extract judge's verdict from last message
        verdict = str(chat_results[-1].summary) if chat_results[-1].summary else ""
        if not verdict and chat_results[-1].chat_history:
            verdict = str(chat_results[-1].chat_history[-1].get("content", ""))

    except Exception as e:
        log.error("BVS debate for %s failed: %s", brand, e)
        return {
            "brand": brand,
            "rating": "N/A",
            "confidence": "low",
            "score": 0,
            "justification": f"Error: {e}",
            "run_date": datetime.now().isoformat()[:10],
        }

    # Parse rating from verdict
    rating = "BBB"  # default
    for r in ["AAA", "AA", "A", "BBB", "BB", "B", "C"]:
        if r in verdict:
            rating = r
            break

    # Parse confidence
    confidence = "medium"
    for level in ["high", "medium", "low"]:
        if level in verdict.lower():
            confidence = level
            break

    return {
        "brand": brand,
        "rating": rating,
        "confidence": confidence,
        "score": _rating_to_number(rating),
        "justification": verdict[:500] if verdict else "No justification produced",
        "run_date": datetime.now().isoformat()[:10],
    }


def evaluate_all_brands(brands: Optional[list[str]] = None, dry_run: bool = False) -> list[dict]:
    """Run BVS evaluation for multiple brands.

    Args:
        brands: list of brand names. If None, uses top 20 from registry.
        dry_run: if True, simulate without LLM

    Returns:
        list of rating dicts, sorted by score (worst first)
    """
    targets = brands or KNOWN_BRANDS[:20]
    results = []
    for brand in targets:
        log.info("BVS: evaluating %s...", brand)
        result = evaluate_brand(brand, dry_run=dry_run)
        results.append(result)
        log.info("  → %s (%s, confidence: %s)", result["rating"], result["score"], result["confidence"])

    results.sort(key=lambda r: r["score"])
    return results


def save_bvs_results(results: list[dict]):
    """Save BVS results to the database."""
    from pipeline.db import get_db
    db = get_db()
    for r in results:
        db.save_agent_result(
            product="bvs",
            target_name=r["brand"],
            run_date=r["run_date"],
            score=r["score"],
            score_label=r["rating"],
            details=r,
            report_md="",  # will be filled by writer
            agent_config="debate: red+blue+judge, deepseek-v4-pro",
        )


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Brand Viability Score evaluation")
    parser.add_argument("--brand", help="evaluate a specific brand")
    parser.add_argument("--all", action="store_true", help="evaluate all registered brands")
    parser.add_argument("--dry-run", action="store_true", help="simulate without LLM calls")
    parser.add_argument("--save", action="store_true", help="save results to database")
    args = parser.parse_args()

    if args.brand:
        result = evaluate_brand(args.brand, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.save:
            save_bvs_results([result])
    elif args.all:
        results = evaluate_all_brands(dry_run=args.dry_run)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if args.save:
            save_bvs_results(results)
    else:
        print("Usage: python -m agents.products.bvs --brand 蔚来 | --all")
