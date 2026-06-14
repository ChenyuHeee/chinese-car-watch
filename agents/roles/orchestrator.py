"""Orchestrator agent — task decomposition and agent coordination."""

from autogen import ConversableAgent

from agents.config import make_agent, load_prompt


def make_orchestrator(name: str = "orchestrator") -> ConversableAgent:
    system_prompt = load_prompt("orchestrator")
    return make_agent(name=name, role="orchestrator", system_prompt=system_prompt)
