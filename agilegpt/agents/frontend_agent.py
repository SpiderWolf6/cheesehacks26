"""Frontend development agent scaffold."""

from __future__ import annotations

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class FrontendAgent(BaseAgent):
    """Represents the frontend-focused developer agent.

    Responsibility (conceptual): implement UI tasks, component behavior,
    and frontend acceptance criteria from sprint stories.
    """

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = "You are the frontend developer agent for AgileGPT."
        super().__init__(name="frontend_agent", system_prompt=system_prompt, llm_service=llm_service)
