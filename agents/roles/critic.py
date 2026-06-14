"""Critic agent — logical review and blind spot detection."""

from autogen import ConversableAgent, register_function

from agents.config import make_agent, load_prompt
from agents.tools.db_query import DB_TOOLS


def make_critic(name: str = "critic") -> ConversableAgent:
    system_prompt = load_prompt("critic")
    agent = make_agent(name=name, role="critic", system_prompt=system_prompt)

    for tool in DB_TOOLS:
        register_function(
            tool,
            caller=agent,
            executor=agent,
            name=tool.__name__,
            description=tool.__doc__ or "",
        )

    return agent
