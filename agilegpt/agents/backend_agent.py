"""Backend development agent scaffold."""

from __future__ import annotations

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class BackendAgent(BaseAgent):
    """Represents the backend-focused developer agent.

    Responsibility (conceptual): implement API behavior, service integration,
    and backend task delivery for sprint stories.
    """

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = "You are the backend developer agent for AgileGPT."
        super().__init__(
            name="backend_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="azure_gpt41",
        )
