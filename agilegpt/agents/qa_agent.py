"""Quality assurance agent scaffold."""

from __future__ import annotations

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class QAAgent(BaseAgent):
    """Represents the QA-focused developer agent.

    Responsibility (conceptual): validate stories, verify acceptance criteria,
    and track quality risks during sprint execution.
    """

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = "You are the QA developer agent for AgileGPT."
        super().__init__(
            name="qa_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="azure_gpt41",
        )
