"""
Brand Viability Score (BVS) — 品牌生存力评级

Uses AG2 Nested Chat for Red-Blue Debate pattern:
  Red Analyst: argues the brand WILL fail within 12 months
  Blue Analyst: argues the brand will SURVIVE
  Judge (Critic): evaluates both arguments, produces final rating + confidence
"""

import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from typing import Optional

import yaml
from autogen import register_function, initiate_chats

from agents.config import PROJECT_ROOT, make_agent, load_prompt
from agents.tools.db_query import DB_TOOLS

log = logging.getLogger(__name__)

# ── Lazy-load brand registry (not at import time) ───────
BRANDS_YAML = PROJECT_ROOT / "config" / "brands.yaml"


def _load_brand_data() -> dict:
    """Load brand registry from YAML. Cached after first call."""
    with open(BRANDS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_known_brands() -> list[str]:
    return [b["name"] for b in _load_brand_data()["brands"]]


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

# Rating → numeric score
RATING_TO_SCORE = {"AAA": 95, "AA": 82, "A": 68, "BBB": 55, "BB": 35, "B": 15, "C": 5}

# Rating parser: match FULL rating label with word boundaries
# Must check longer labels first to avoid "A" matching inside "AAA"
RATING_PATTERN = re.compile(r'\b(AAA|AA|BBB|BB|A|B|C)\b')


def _parse_rating(text: str) -> str:
    """Parse BVS rating from text. Returns 'BBB' if no rating found."""
    matches = RATING_PATTERN.findall(text)
    if not matches:
        return "BBB"
    # Filter out single-letter false positives:
    # 'A' should only match as a standalone word, not in 'DATA', 'AND', etc.
    # Prefer multi-char ratings if present
    for preferred in ["AAA", "AA", "BBB", "BB"]:
        if preferred in matches:
            return preferred
    for single in ["A", "B", "C"]:
        if single in matches:
            return single
    return "BBB"


def _parse_confidence(text: str) -> str:
    """Parse confidence level from text."""
    text_lower = text.lower()
    if "high" in text_lower:
        return "high"
    if "low" in text_lower:
        return "low"
    return "medium"


def _call_judge(brand: str, debate_transcript: str) -> str:
    """Make a standalone LLM call for the judge verdict.
    Avoids AG2 multi-chat context issues by calling DeepSeek directly.
    """
    from openai import OpenAI
    import os

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    judge_prompt = load_prompt("critic")
    system_msg = (
        f"{judge_prompt}\n\n"
        f"You are the JUDGE for a debate on whether **{brand}** will survive the next 12 months. "
        f"Review the debate transcript below. Then produce your FINAL VERDICT.\n\n"
        f"Output format:\n"
        f"FINAL RATING: [AAA/AA/A/BBB/BB/B/C]\n"
        f"CONFIDENCE: [high/medium/low]\n"
        f"JUSTIFICATION: [one paragraph with specific evidence cited]\n\n"
        f"## BVS Rating Scale\n"
        f"- AAA: 行业领导者，现金流充裕，无短期生存风险\n"
        f"- AA: 强势品牌，具备护城河，但面临特定挑战\n"
        f"- A: 稳健运营，有差异化优势，外部融资通畅\n"
        f"- BBB: 经营正常，但过度依赖外部融资或单一车型\n"
        f"- BB: 高风险，销量持续下滑，融资端承压\n"
        f"- B: 极度危险，12个月内可能退出市场或被并购\n"
        f"- C: 已实质性停摆，破产/清算/被接管"
    )

    try:
        resp = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"## Debate Transcript\n{debate_transcript}\n\n## Instructions\nBased on the debate, render your FINAL VERDICT in the specified format."},
            ],
            temperature=0.2,
            max_tokens=2048,
            extra_body={"thinking": {"type": "enabled"}},
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("Judge API call failed: %s", e)
        return ""


def _build_debate_prompt(brand: str, brand_info: Optional[dict] = None) -> str:
    """Build the initial debate prompt with brand context."""
    lines = [f"## Brand: {brand}"]
    if brand_info:
        lines.append(f"Parent: {brand_info.get('parent', 'N/A')}")
        lines.append(f"Founded: {brand_info.get('founded', 'N/A')}")
        lines.append(f"Type: {brand_info.get('type', 'N/A')}")
        lines.append(f"Listed: {brand_info.get('is_listed', False)}")
        if brand_info.get("stock_codes"):
            lines.append(f"Stock: {', '.join(brand_info['stock_codes'])}")
        if brand_info.get("notes"):
            lines.append(f"Notes: {brand_info['notes']}")

    lines.append("")
    lines.append("## Task")
    lines.append(f"Conduct a rigorous Red-Blue debate on whether **{brand}** will survive the next 12 months.")
    lines.append("")
    lines.append("Red Analyst: Argue that the brand WILL fail. Focus on negative signals.")
    lines.append("Blue Analyst: Argue that the brand will SURVIVE. Focus on resilience factors.")
    lines.append("")
    lines.append("Use the available database tools to gather evidence before making arguments.")
    lines.append("Both analysts must cite specific data (sales numbers, trends, funding facts).")
    lines.append("")
    lines.append("After the debate, the Judge (Critic) will assign a final BVS rating.")
    lines.append("")
    lines.append("## BVS Rating Scale")
    for rating, desc in RATING_SCALE.items():
        lines.append(f"- **{rating}**: {desc}")

    return "\n".join(lines)


def _register_tools(agent):
    """Register database query tools on an agent."""
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
        dict with rating, confidence, justification
    """
    brand_data = _load_brand_data()
    brand_info = next((b for b in brand_data["brands"] if b["name"] == brand), None)
    if not brand_info:
        log.warning("Brand '%s' not in registry, using generic analysis", brand)
        brand_info = {"name": brand}

    debate_prompt = _build_debate_prompt(brand, brand_info)

    if dry_run:
        return {
            "brand": brand,
            "rating": "A",
            "confidence": "low",
            "score": RATING_TO_SCORE["A"],
            "justification": f"[DRY RUN] Simulated rating for {brand}. No LLM calls made.",
            "run_date": datetime.now().isoformat()[:10],
        }

    # Create agents
    red = make_agent(
        name=f"red_{brand}",
        role="analyst",
        system_prompt=load_prompt("analyst") + f"\n\nYou are RED TEAM. Argue that **{brand}** WILL FAIL within 12 months. Be aggressive but factual. Cite specific data.",
    )
    blue = make_agent(
        name=f"blue_{brand}",
        role="analyst",
        system_prompt=load_prompt("analyst") + f"\n\nYou are BLUE TEAM. Argue that **{brand}** will SURVIVE. Highlight strengths and resilience. Cite specific data.",
    )
    judge = make_agent(
        name=f"judge_{brand}",
        role="critic",
        system_prompt=load_prompt("critic") + f"\n\nYou are the JUDGE for the debate on {brand}. After reviewing both sides, produce your FINAL VERDICT in this exact format:\n\nFINAL RATING: [AAA/AA/A/BBB/BB/B/C]\nCONFIDENCE: [high/medium/low]\nJUSTIFICATION: [one paragraph with specific evidence cited]",
    )

    _register_tools(red)
    _register_tools(blue)
    _register_tools(judge)

    try:
        # Chat 1: Red vs Blue debate
        chat_results = initiate_chats([
            {
                "sender": red,
                "recipient": blue,
                "message": debate_prompt,
                "max_turns": 4,
                "clear_history": True,
            },
        ])

        # Extract debate transcript
        debate_transcript = ""
        if chat_results and chat_results[0].chat_history:
            messages = chat_results[0].chat_history
            for msg in messages[-6:]:  # last 6 messages (3 full exchanges)
                role = msg.get("name", msg.get("role", "unknown"))
                content = str(msg.get("content", ""))[:2000]
                debate_transcript += f"\n--- {role} ---\n{content}\n"

        # Step 2: Judge renders verdict via standalone LLM call
        verdict = _call_judge(brand, debate_transcript)

    except Exception as e:
        log.error("BVS debate for %s failed: %s", brand, e)
        return {
            "brand": brand,
            "rating": "N/A",
            "confidence": "low",
            "score": 0,
            "justification": f"Agent error: {e}",
            "run_date": datetime.now().isoformat()[:10],
        }

    rating = _parse_rating(verdict)
    confidence = _parse_confidence(verdict)

    log.info("BVS %s → %s (confidence: %s)", brand, rating, confidence)

    return {
        "brand": brand,
        "rating": rating,
        "confidence": confidence,
        "score": RATING_TO_SCORE.get(rating, 55),
        "justification": verdict[:800] if verdict else "No justification produced",
        "run_date": datetime.now().isoformat()[:10],
    }


def evaluate_all_brands(brands: Optional[list[str]] = None, dry_run: bool = False) -> list[dict]:
    """Run BVS evaluation for multiple brands.

    Args:
        brands: list of brand names. If None, uses registered brands.
        dry_run: if True, simulate without LLM

    Returns:
        list of rating dicts, sorted by score (worst first)
    """
    targets = brands or _get_known_brands()
    results = []
    for brand in targets:
        log.info("BVS: evaluating %s...", brand)
        result = evaluate_brand(brand, dry_run=dry_run)
        results.append(result)

    results.sort(key=lambda r: r["score"])
    return results


def save_bvs_results(results: list[dict]):
    """Save BVS results to the database in a single transaction."""
    from pipeline.db import get_db, DB_PATH
    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        for r in results:
            conn.execute(
                """INSERT INTO agent_results (product, target_name, run_date, score, score_label, details, report_md, agent_config)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("bvs", r["brand"], r["run_date"], r["score"], r["rating"],
                 json.dumps(r, ensure_ascii=False), "", "debate: red+blue+judge, deepseek-v4-pro"),
            )
        conn.commit()
        log.info("Saved %d BVS results to DB", len(results))
    except Exception as e:
        conn.rollback()
        log.error("Failed to save BVS results: %s", e)
        raise
    finally:
        conn.close()


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
