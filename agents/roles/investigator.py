"""Investigator agent — information gathering and verification."""

from autogen import ConversableAgent, register_function

from agents.config import make_agent, load_prompt
from agents.tools.db_query import DB_TOOLS
from agents.tools.search import SEARCH_TOOLS


def make_investigator(name: str = "investigator") -> ConversableAgent:
    system_prompt = load_prompt("investigator")
    agent = make_agent(name=name, role="investigator", system_prompt=system_prompt)

    # Register all tools
    for tool in DB_TOOLS + SEARCH_TOOLS:
        register_function(
            tool,
            caller=agent,
            executor=agent,
            name=tool.__name__,
            description=tool.__doc__ or "",
        )

    return agent
