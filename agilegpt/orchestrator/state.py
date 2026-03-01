"""Project state model used by the orchestrator.

This module defines the data structures that track everything about a running project:
- The sprint plan (what work is planned across all sprints)
- JIRA integration IDs (so we can update tickets as work progresses)
- The shared API contract (the single source of truth for how frontend and backend communicate)
- Per-agent memory (what each AI agent has built so far, so they don't lose context between sprints)

These are Pydantic models, which means they automatically validate data types and
provide sensible defaults. The orchestrator creates one ProjectState per project run
and updates it as sprints execute.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentMemory(BaseModel):
    """Per-agent persistent context that carries over across sprints.

    Without this, each agent would start every sprint with zero memory of what
    it built before. AgentMemory solves this by tracking:

    - files_written: A dict of {file_path: file_content} for every file
      the agent has produced. This lets the orchestrator show the agent
      its own previous code so it can build on top of it rather than rewriting.

    - work_log: A list of human-readable summaries of what the agent did
      each sprint (e.g., "Sprint 2: Built donation routes - wrote [routes/donations.py]").
      This gives the agent a high-level memory of its own history.
    """
    files_written: Dict[str, str] = Field(default_factory=dict)  # {path: content} of all files this agent created
    work_log: List[str] = Field(default_factory=list)            # Summary of work done each sprint


class SprintRecord(BaseModel):
    """Tracks one sprint's execution state and outcomes.

    Each sprint gets a SprintRecord that links the internal plan to JIRA
    and records whether each task passed or failed. This information feeds
    into the PM's review step so it can adjust future sprints if something broke.

    - sprint_number: Which sprint this is (1-indexed, e.g., 1, 2, 3...).
    - jira_sprint_id: The JIRA sprint ID so we can start/stop it via the API.
    - jira_task_ids: Maps internal plan task IDs to JIRA task IDs for status updates.
    - task_results: Maps task IDs to "DONE" or "FAILED" after execution.
    - status: Overall sprint status — "pending", "in_progress", or "completed".
    """
    sprint_number: int
    jira_sprint_id: Optional[int] = None                         # JIRA sprint ID (None if JIRA creation failed)
    jira_task_ids: Dict[str, str] = Field(default_factory=dict)  # {plan_task_id: jira_task_id}
    task_results: Dict[str, str] = Field(default_factory=dict)   # {task_id: "DONE" or "FAILED"}
    status: str = "pending"                                      # "pending" | "in_progress" | "completed"


class ProjectState(BaseModel):
    """Full orchestrator state for one project run.

    This is the central data object that the orchestrator reads and writes
    throughout the entire SCRUM cycle. It holds:

    - The original user story (what the client wants built)
    - The PM's sprint plan (the full roadmap of sprints and tasks)
    - The shared API contract (defines every endpoint so frontend and backend agree)
    - Sprint execution records (tracks JIRA IDs and pass/fail for each task)
    - Agent memory (what each agent has built, so they can iterate on their own work)
    - The workspace path (the isolated directory where all generated code lives)
    """

    project_id: str                  # Unique identifier for this project run
    clarified_user_story: str        # The client's requirements after manager review

    # The raw JSON plan produced by the PM agent in planning mode.
    # Contains the full sprint breakdown, shared contract, and handoff contract.
    sprint_plan: Optional[Dict[str, Any]] = None

    # Shared API contract — the single source of truth defining every backend endpoint,
    # its HTTP method, request/response schemas, and expected status codes.
    # All agents (backend, frontend, QA) reference this to stay in sync.
    shared_contract: Optional[Dict[str, Any]] = None

    # Handoff contract from PM — maps files, functions, and tests to shared_contract endpoints.
    # Ensures every planned endpoint has a backend function, frontend call, and integration test.
    handoff_contract: Optional[Dict[str, Any]] = None

    # Sprint tracking — where we are in the overall SCRUM cycle.
    current_sprint: int = 1    # Which sprint is currently executing (1-indexed)
    total_sprints: int = 0     # Total number of sprints planned (may increase if PM inserts a sprint)
    sprint_records: List[SprintRecord] = Field(default_factory=list)  # Execution records per sprint

    # Per-agent persistent memory keyed by agent name (e.g., "backend_agent", "frontend_agent").
    # This is how agents "remember" what they built in previous sprints.
    agent_memory: Dict[str, AgentMemory] = Field(default_factory=dict)

    # Workspace path — the isolated directory on disk where all generated project code lives.
    # Each project gets its own folder with its own Python venv, source files, and test files.
    workspace_path: str = ""

    # Whether requirements.txt has been written and pip-installed in the workspace venv.
    requirements_written: bool = False
