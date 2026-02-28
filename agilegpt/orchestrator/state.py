"""Project state model used by the orchestrator.

This is temporary in-memory state for the MVP scaffold.
No database is used yet.
"""

from __future__ import annotations

from pydantic import BaseModel


class ProjectState(BaseModel):
    """Represents a single active project's orchestrator state."""

    project_id: str
    clarified_user_story: str
    current_sprint: int = 1
    sprint_status: str = "planning"
    backlog_summary: str = ""
