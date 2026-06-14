"""
AG2 configuration with DeepSeek provider.
All agent products import from here.
"""

import os
from pathlib import Path

from autogen import ConversableAgent, GroupChat, GroupChatManager

# ── DeepSeek API setup ──────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Model mapping for different agent roles
MODEL_CONFIG = {
    "orchestrator": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.3,
        "max_tokens": 32768,
        "extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
    },
    "analyst": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.3,
        "max_tokens": 32768,
        "extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
    },
    "critic": {
        "model": "deepseek-v4-pro",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "temperature": 0.2,
        "max_tokens": 16384,
        "extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
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

# LLM config list for AG2 — compatible with OpenAI client
LLM_CONFIG_LIST = [
    {
        "model": cfg["model"],
        "api_key": cfg["api_key"],
        "base_url": cfg["base_url"],
        "api_type": "openai",  # DeepSeek is OpenAI-compatible
    }
    for cfg in MODEL_CONFIG.values()
]


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
) -> ConversableAgent:
    """Create an AG2 ConversableAgent with the given role config.

    Args:
        name: unique agent name (e.g. 'analyst_1')
        role: one of 'orchestrator', 'analyst', 'critic', 'investigator', 'writer'
        system_prompt: agent instructions
        tools: list of callable tools
    """
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
    # Pass DeepSeek thinking params via extra_body if available
    if "extra_body" in cfg:
        llm_config["config_list"][0]["extra_body"] = cfg["extra_body"]

    return ConversableAgent(
        name=name,
        system_message=system_prompt,
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=8,
    )


def make_group_chat(
    agents: list[ConversableAgent],
    speaker_selection_method: str = "auto",
    max_round: int = 20,
) -> tuple[GroupChat, GroupChatManager]:
    """Create an AG2 GroupChat with the given agents."""
    group_chat = GroupChat(
        agents=agents,
        messages=[],
        max_round=max_round,
        speaker_selection_method=speaker_selection_method,
    )
    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config={
            "config_list": [
                {
                    "model": MODEL_CONFIG["orchestrator"]["model"],
                    "api_key": MODEL_CONFIG["orchestrator"]["api_key"],
                    "base_url": MODEL_CONFIG["orchestrator"]["base_url"],
                    "api_type": "openai",
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        human_input_mode="NEVER",
    )
    return group_chat, manager
