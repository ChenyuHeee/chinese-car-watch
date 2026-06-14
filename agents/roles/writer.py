"""Writer agent — report synthesis and formatting."""

from autogen import ConversableAgent

from agents.config import make_agent, load_prompt


def make_writer(name: str = "writer") -> ConversableAgent:
    system_prompt = load_prompt("writer")
    return make_agent(name=name, role="writer", system_prompt=system_prompt)
