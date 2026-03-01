"""Base agent abstraction used by PM and Dev agents."""

from __future__ import annotations

import json
from typing import Dict

from services.llm_service import LLMService


class BaseAgent:
    """Shared agent behavior.

    Each agent has a name, a system prompt, and access to the same LLM service.
    For now, run() sends JSON context and returns raw text output.
    Structured response enforcement will be added in a later iteration.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm_service: LLMService,
        model_target: str = "azure_gpt41",
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.llm_service = llm_service
        self.model_target = model_target

    def run(self, context: Dict[str, object]) -> str:
        """Serialize context and send it to the LLM."""
        user_content = json.dumps(context, indent=2)
        return self.llm_service.generate(
            system_prompt=self.system_prompt,
            user_content=user_content,
            model_target=self.model_target,
        )