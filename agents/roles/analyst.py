"""Analyst agent — quantitative scoring and trend analysis."""

from autogen import ConversableAgent, register_function

from agents.config import make_agent, load_prompt
from agents.tools.db_query import DB_TOOLS


def make_analyst(name: str = "analyst") -> ConversableAgent:
    system_prompt = load_prompt("analyst")
    agent = make_agent(name=name, role="analyst", system_prompt=system_prompt)

    for tool in DB_TOOLS:
        register_function(
            tool,
            caller=agent,
            executor=agent,
            name=tool.__name__,
            description=tool.__doc__ or "",
        )

    return agent
