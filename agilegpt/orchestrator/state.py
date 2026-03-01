"""Project state model used by the orchestrator.

Tracks the full sprint plan, JIRA artifact IDs, shared contract,
and per-agent persistent memory so agents can build iteratively.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentMemory(BaseModel):
    """Per-agent persistent context across sprints.

    Stores what files the agent has written and a summary of its prior work
    so it does not rewrite from scratch each sprint.
    """
    files_written: Dict[str, str] = Field(default_factory=dict)
    work_log: List[str] = Field(default_factory=list)


class SprintRecord(BaseModel):
    """Tracks one sprint's JIRA IDs and task outcomes."""
    sprint_number: int
    jira_sprint_id: Optional[int] = None
    jira_task_ids: Dict[str, str] = Field(default_factory=dict)
    task_results: Dict[str, str] = Field(default_factory=dict)
    status: str = "pending"


class ProjectState(BaseModel):
    """Full orchestrator state for one project run."""

    project_id: str
    clarified_user_story: str

    # The raw JSON plan from PM planning mode.
    sprint_plan: Optional[Dict[str, Any]] = None

    # Shared API contract (single source of truth for all agents).
    shared_contract: Optional[Dict[str, Any]] = None

    # Handoff contract from PM.
    handoff_contract: Optional[Dict[str, Any]] = None

    # Sprint tracking.
    current_sprint: int = 1
    total_sprints: int = 0
    sprint_records: List[SprintRecord] = Field(default_factory=list)

    # Per-agent persistent memory keyed by agent name.
    agent_memory: Dict[str, AgentMemory] = Field(default_factory=dict)

    # Workspace path for isolated code execution.
    workspace_path: str = ""

    # Requirements written to workspace.
    requirements_written: bool = False
