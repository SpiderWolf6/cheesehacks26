"""Context Builder for AgileGPT — assembles agent prompt context per architecture.md.

Injection order (per dev or QA agent call):
  1. design_doc_{agent}.md — full architecture for the agent's domain
  2. interface_contract.md — shared API contract
  3. sprint_plan.md — full plan with task statuses
  4. project_state.md — anti-drift registry
  5. {agent}_log.md — agent mid-term memory
  6. Task brief (current sprint) — specific task + existing code files

Falls back to in-memory state when artifact files don't exist yet.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from orchestrator.artifact_writer import (
    read_design_doc,
    read_interface_contract,
    read_sprint_plan,
    read_project_state,
    read_agent_log,
)


def build_agent_context(
    workspace_path: str,
    agent_name: str,
    task_description: str,
    sprint_data: Dict[str, Any],
    shared_contract: Dict[str, Any] | None = None,
    agent_memory: Dict[str, str] | None = None,
) -> str:
    """Build the context string for a dev/QA agent call.

    Follows the 6-file injection order from architecture.md.
    Falls back to in-memory data when artifact files don't exist.
    """
    parts: list[str] = []

    # 1. Design doc for this agent's domain
    design_doc = read_design_doc(workspace_path, agent_name)
    if design_doc:
        parts.append(f"=== Design Document ({agent_name}) ===\n{design_doc}")

    # 2. Interface contract — shared API contract
    interface_contract = read_interface_contract(workspace_path)
    if interface_contract:
        parts.append(f"=== Interface Contract ===\n{interface_contract}")
    elif shared_contract:
        # Fallback: use in-memory shared contract
        parts.append(f"=== Shared API Contract ===\n{json.dumps(shared_contract, indent=2)}")

    # 3. Current sprint status (not the full plan — too large for context)
    if sprint_data:
        sprint_status = _format_sprint_status(sprint_data)
        if sprint_status:
            parts.append(f"=== Current Sprint ===\n{sprint_status}")

    # 4. Project state — anti-drift registry
    project_state = read_project_state(workspace_path)
    if project_state:
        parts.append(f"=== Project State ===\n{project_state}")

    # 5. Agent log — mid-term memory
    agent_log = read_agent_log(workspace_path, agent_name)
    if agent_log:
        parts.append(f"=== Your Previous Work ===\n{agent_log}")
    elif agent_memory:
        # Fallback: use in-memory agent memory
        files_written = agent_memory.get("files_written", {})
        work_log = agent_memory.get("work_log", [])
        if files_written or work_log:
            memory_parts = []
            if work_log:
                memory_parts.append("Work log:\n" + "\n".join(f"  - {w}" for w in work_log))
            if files_written:
                memory_parts.append("Files you have written:\n" + "\n".join(f"  - {f}" for f in files_written))
            parts.append("=== Your Previous Work ===\n" + "\n".join(memory_parts))

    # 6. Task brief
    if task_description:
        parts.append(f"=== Your Task ===\n{task_description}")

    return "\n\n".join(parts)


def _format_sprint_status(sprint_data: Dict[str, Any]) -> str:
    """Format current sprint data as readable status."""
    parts = []
    sprint_name = sprint_data.get("name", sprint_data.get("id", "Current Sprint"))
    goal = sprint_data.get("goal", "")
    parts.append(f"Sprint: {sprint_name}")
    if goal:
        parts.append(f"Goal: {goal}")

    tasks = sprint_data.get("tasks", [])
    for task in tasks:
        name = task.get("name", "")
        status = task.get("status", "TODO")
        parts.append(f"  [{status}] {name}")

    return "\n".join(parts)
