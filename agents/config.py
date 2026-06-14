"""
AG2 configuration with DeepSeek provider.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

log = logging.getLogger(__name__)

# ── DeepSeek API setup ──────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

if not DEEPSEEK_API_KEY:
    log.warning("DEEPSEEK_API_KEY not set — agent calls will fail")
    log.warning("Set it via: export DEEPSEEK_API_KEY=sk-... or create a .env file")

# Model mapping for different agent roles
# deepseek-v4-pro: flagship model with thinking (for Analyst, Critic, Orchestrator)
# deepseek-v4-flash: fast model with thinking (for Investigator, Writer)
MODEL_CONFIG = {
    "orchestrator": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.3,
        "max_tokens": 32768,
        "extra_body": {"thinking": {"type": "enabled"}},
    },
    "analyst": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.3,
        "max_tokens": 32768,
        "extra_body": {"thinking": {"type": "enabled"}},
    },
    "critic": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.2,
        "max_tokens": 16384,
        "extra_body": {"thinking": {"type": "enabled"}},
    },
    "investigator": {
        "model": "deepseek-v4-flash",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.7,
        "max_tokens": 16384,
        "extra_body": {"thinking": {"type": "enabled"}},
    },
    "writer": {
        "model": "deepseek-v4-flash",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.5,
        "max_tokens": 16384,
    },
}

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt from agents/prompts/{name}.md"""
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def make_agent(
    name: str,
    role: str,
    system_prompt: str = "",
    tools: list = None,
) -> "ConversableAgent":
    """Create an AG2 ConversableAgent with the given role config."""
    from autogen import ConversableAgent

    cfg = MODEL_CONFIG.get(role, MODEL_CONFIG["investigator"])
    llm_config = {
        "config_list": [
            {
                "model": cfg["model"],
                "api_key": cfg["api_key"],
                "base_url": cfg["base_url"],
                "api_type": "openai",
            }
        ],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if "extra_body" in cfg:
        llm_config["config_list"][0]["extra_body"] = cfg["extra_body"]

    return ConversableAgent(
        name=name,
        system_message=system_prompt,
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=8,
    )
