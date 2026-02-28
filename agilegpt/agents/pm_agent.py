"""PM agent scaffold (Product Owner + Scrum Master responsibilities)."""

from __future__ import annotations

from typing import Dict

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class PMAgent(BaseAgent):
    """Coordinates planning, sprint control, and retrospectives.

    This class is intentionally simple. Each mode only tags context with a mode
    and delegates to BaseAgent.run(). More detailed behavior will be added later.
    """

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = (
            "You are the PM agent for AgileGPT. "
            "You combine Product Owner and Scrum Master responsibilities."
        )
        super().__init__(name="pm_agent", system_prompt=system_prompt, llm_service=llm_service)

    def planning_mode(self, context: Dict[str, object]) -> str:
        """Planning mode.

        Conceptual responsibility:
        - turn clarified user stories into an initial backlog
        - define sprint goals
        - propose the initial sprint scope
        """
        planning_context = dict(context)
        planning_context["mode"] = "planning"
        return self.run(planning_context)

    def sprint_control_mode(self, context: Dict[str, object]) -> str:
        """Sprint control mode.

        Conceptual responsibility:
        - monitor active sprint progress
        - enforce sprint boundaries and commitments
        - reduce scope churn during sprint execution
        """
        sprint_context = dict(context)
        sprint_context["mode"] = "sprint_control"
        return self.run(sprint_context)

    def retrospective_mode(self, context: Dict[str, object]) -> str:
        """Retrospective mode.

        Conceptual responsibility:
        - review outcomes after sprint completion
        - capture lessons learned
        - adapt backlog and priorities for the next sprint
        """
        retro_context = dict(context)
        retro_context["mode"] = "retrospective"
        return self.run(retro_context)
