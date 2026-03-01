"""Base agent abstraction used by PM and Dev agents.

In AgileGPT, an "agent" is a wrapper around a Large Language Model (LLM) call.
Each agent has a specific role (PM, Backend Dev, Frontend Dev, QA) defined by its
system prompt — a set of instructions that tells the AI how to behave.

When the orchestrator needs an agent to do work, it sends the agent a JSON context
(containing the task description, existing code, API contracts, etc.), and the agent
returns text output (usually JSON with code files to write and commands to run).

Think of each agent as a specialized AI employee: they all share the same "brain"
(the LLM), but each has different instructions (system prompt) that make them
behave like a backend engineer, frontend engineer, PM, or QA tester.
"""

from __future__ import annotations

import json
from typing import Dict

from services.llm_service import LLMService


class BaseAgent:
    """Shared agent behavior — the parent class that all specialized agents inherit from.

    Each agent has:
    - A name (e.g., "pm_agent", "backend_agent") for identification and logging.
    - A system prompt — the detailed instructions that shape how the AI responds.
      This is where the agent's "personality" and expertise are defined.
    - Access to the LLM service — the connection to the AI model (e.g., GPT-4).
    - A model target — which specific AI model to use for this agent's tasks.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm_service: LLMService,
        model_target: str = "azure_gpt41",
    ) -> None:
        self.name = name                    # Human-readable agent identifier (e.g., "backend_agent")
        self.system_prompt = system_prompt  # The AI's instructions — defines how this agent behaves
        self.llm_service = llm_service      # Connection to the LLM API (handles the actual AI call)
        self.model_target = model_target    # Which AI model to use (e.g., "azure_gpt41" for GPT-4.1)

    def run(self, context: Dict[str, object]) -> str:
        """Send a task to the AI and get back its response.

        This is the core method that makes an agent "do work":
        1. Takes the context dict (task details, existing code, contracts, etc.)
        2. Converts it to a JSON string so the AI can read it
        3. Sends it to the AI along with this agent's system prompt (instructions)
        4. Returns the AI's raw text response (usually JSON with files to write)

        The system_prompt tells the AI WHO it is and HOW to respond.
        The user_content (serialized context) tells the AI WHAT to do right now.
        """
        # Convert the context dictionary to a formatted JSON string.
        # This becomes the "user message" that the AI reads alongside its system prompt.
        user_content = json.dumps(context, indent=2)

        # Call the LLM (AI model) and return its response as raw text.
        # The LLM service handles the actual HTTP call to the AI provider (e.g., Azure OpenAI).
        return self.llm_service.generate(
            system_prompt=self.system_prompt,
            user_content=user_content,
            model_target=self.model_target,
        )
