"""Main orchestrator engine for AgileGPT backend scaffold."""

from __future__ import annotations

from typing import Dict

from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.pm_agent import PMAgent
from agents.qa_agent import QAAgent
from config import Config
from orchestrator.state import ProjectState
from services.jira_service import JiraService
from services.llm_service import LLMService


class Orchestrator:
    """Coordinates services, agents, and in-memory project state.

    This implementation is intentionally lightweight for hackathon speed and
    educational clarity.
    """

    def __init__(self) -> None:
        self.config = Config()

        self.llm_service = LLMService(self.config)
        self.jira_service = JiraService(self.config)

        self.pm_agent = PMAgent(self.llm_service)
        self.frontend_agent = FrontendAgent(self.llm_service)
        self.backend_agent = BackendAgent(self.llm_service)
        self.qa_agent = QAAgent(self.llm_service)

        # Temporary in-memory storage for active projects.
        self.active_projects: Dict[str, ProjectState] = {}

    def start_project(self, project_id: str, clarified_story: str) -> ProjectState:
        """Create and register a new in-memory project state."""
        state = ProjectState(project_id=project_id, clarified_user_story=clarified_story)
        self.active_projects[project_id] = state

        # TODO: Create project and initial board/sprint in JIRA.
        # TODO: Create isolated Docker sandbox for this project.
        return state

    def run_planning(self, project_id: str) -> str:
        """Run PM planning mode for a project and store returned backlog summary."""
        state = self.active_projects[project_id]

        planning_context = {
            "project_id": state.project_id,
            "clarified_user_story": state.clarified_user_story,
            "current_sprint": state.current_sprint,
            "sprint_status": state.sprint_status,
        }

        output = self.pm_agent.planning_mode(planning_context)
        state.backlog_summary = output
        state.sprint_status = "planned"

        # TODO: Convert planning output into JIRA epics/stories.
        # TODO: Map planned stories into first sprint.
        return output

    def run_sprint_cycle(self, project_id: str) -> str:
        """Run a basic sprint cycle scaffold across PM and dev agents."""
        state = self.active_projects[project_id]

        sprint_context = {
            "project_id": state.project_id,
            "current_sprint": state.current_sprint,
            "sprint_status": state.sprint_status,
            "backlog_summary": state.backlog_summary,
        }

        pm_output = self.pm_agent.sprint_control_mode(sprint_context)
        frontend_output = self.frontend_agent.run(sprint_context)
        backend_output = self.backend_agent.run(sprint_context)
        qa_output = self.qa_agent.run(sprint_context)

        state.sprint_status = "in_progress"

        # TODO: Enforce sprint loop boundaries and timeboxes.
        # TODO: Sync task state transitions to JIRA each cycle.
        # TODO: Create and run Docker sandboxes for isolated dev execution.
        return "\n\n".join([pm_output, frontend_output, backend_output, qa_output])
