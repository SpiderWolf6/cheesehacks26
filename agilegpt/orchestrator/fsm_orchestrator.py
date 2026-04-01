"""FSM Orchestrator — wraps the existing Orchestrator with FSM-driven execution.

Per architecture.md, the FSM advances through:
    INIT → EM → PO → ARCHITECT → ENV_SETUP → PL_PLAN
    → SPRINT_N_EXEC → QA_RUN → STATE_UPDATE → PL_REVIEW → DONE

This module:
- Uses the existing Orchestrator's helpers (workspace setup, agent calls, JIRA)
- Adds PO, Architect, and PL (Project Lead) agents per architecture.md
- Writes artifact files (design docs, interface contract, project_state.md)
- Saves FSM checkpoints to state.json for resumption

The existing Orchestrator class in engine.py is NOT modified — this wraps it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Callable

from agents.po_agent import POAgent
from agents.architect_agent import ArchitectAgent
from agents.pl_agent import PLAgent
from config import Config
from orchestrator.engine import (
    Orchestrator,
    _parse_json,
    _setup_workspace,
    _setup_vite_project,
    _write_file,
    _scan_workspace_files,
    _classify_task,
    _run_command,
    _start_backend,
    _stop_backend,
    _pip_install,
    BASELINE_PACKAGES,
)
from orchestrator.fsm import ProjectFSM, FSMState
from orchestrator.state import ProjectState
from orchestrator.artifact_writer import (
    create_artifact_directories,
    write_requirements_doc,
    write_requirements_txt,
    write_specs_doc,
    write_design_doc,
    write_interface_contract,
    write_sprint_plan,
    append_agent_log,
    run_state_update,
    generate_runbook,
)
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class FSMOrchestrator:
    """FSM-driven orchestrator that wraps the existing Orchestrator.

    Usage:
        orch = FSMOrchestrator()
        state = orch.run_pipeline("my-project", "Build a donation website...")

    The pipeline flow:
        1. INIT — create workspace + artifact directories
        2. EM — Manager agent (already completed before pipeline starts)
        3. PO — Product Owner generates specs from requirements
        4. ARCHITECT — Architect designs system, writes design docs + interface contract
        5. ENV_SETUP — Install dependencies (uses existing Orchestrator helpers)
        6. PL_PLAN — Project Lead creates sprint plan
        7-10. Sprint loop:
            SPRINT_N_EXEC → QA_RUN → STATE_UPDATE → PL_REVIEW
        11. DONE — Generate RUNBOOK.md
    """

    def __init__(self) -> None:
        # Use existing Orchestrator for all the heavy lifting
        self._orch = Orchestrator()

        # FSM agents (PO, Architect, PL)
        self.po_agent = POAgent(self._orch.llm_service)
        self.architect_agent = ArchitectAgent(self._orch.llm_service)
        self.pl_agent = PLAgent(self._orch.llm_service)

        # Progress callback (optional, called with (phase, message))
        self.on_progress: Optional[Callable[[str, str], None]] = None

    def _notify(self, phase: str, message: str) -> None:
        """Notify progress callback if set."""
        if self.on_progress:
            self.on_progress(phase, message)
        logger.info("[%s] %s", phase, message)

    # ── Main pipeline entry point ─────────────────────────────────────

    def run_pipeline(
        self,
        project_id: str,
        clarified_story: str,
    ) -> ProjectState:
        """Run the full FSM-driven pipeline.

        Args:
            project_id: Unique project identifier.
            clarified_story: Confirmed requirements from the Manager agent.

        Returns:
            The final ProjectState.
        """
        # Initialize FSM
        fsm = ProjectFSM()

        # INIT: Create workspace
        self._notify("INIT", "Creating workspace")
        workspace = _setup_workspace(project_id)
        create_artifact_directories(workspace)

        state = ProjectState(
            project_id=project_id,
            clarified_user_story=clarified_story,
            workspace_path=workspace,
        )
        self._orch.active_projects[project_id] = state

        fsm.complete_state()  # INIT → EM
        fsm.save(workspace)

        # EM: Manager already completed (clarified_story is the output)
        self._notify("EM", "Requirements confirmed by Manager agent")
        write_requirements_doc(workspace, clarified_story)
        fsm.complete_state()  # EM → PO
        fsm.save(workspace)

        # PO: Generate specs from requirements
        self._notify("PO", "Product Owner generating specs")
        specs = self.po_agent.generate_specs(clarified_story)
        state.specs_doc = specs
        write_specs_doc(workspace, specs)
        fsm.complete_state()  # PO → ARCHITECT
        fsm.save(workspace)

        # ARCHITECT: Design system
        self._notify("ARCHITECT", "Architect designing system")
        architecture = self.architect_agent.design(specs, clarified_story)
        state.architecture_output = architecture
        self._write_architecture_artifacts(workspace, architecture)
        fsm.complete_state()  # ARCHITECT → ENV_SETUP
        fsm.save(workspace)

        # ENV_SETUP: Install architect-specified dependencies + scaffold Vite project
        self._notify("ENV_SETUP", "Installing dependencies and scaffolding frontend")
        req_file = os.path.join(workspace, "infra", "requirements.txt")
        if os.path.exists(req_file):
            with open(req_file, "r") as f:
                extra_pkgs = [
                    line.strip() for line in f
                    if line.strip()
                    and not line.strip().startswith("#")
                    and not line.strip().startswith("`")
                    and not line.strip().startswith("*")
                    and not line.strip().startswith("(")
                    and len(line.strip()) < 80  # skip prose lines
                ]
            if extra_pkgs:
                _pip_install(workspace, extra_pkgs)

        # Scaffold Vite + React project in frontend/
        self._notify("ENV_SETUP", "Scaffolding Vite + React frontend")
        _setup_vite_project(workspace)
        fsm.complete_state()  # ENV_SETUP → PL_PLAN
        fsm.save(workspace)

        # PL_PLAN: Project Lead creates sprint plan
        self._notify("PL_PLAN", "Project Lead planning sprints")
        self._orch.run_planning(project_id)
        state = self._orch.active_projects[project_id]

        # Write sprint plan artifact
        if state.sprint_plan:
            write_sprint_plan(workspace, json.dumps(state.sprint_plan, indent=2))

        fsm.total_sprints = state.total_sprints
        fsm.complete_state()  # PL_PLAN → SPRINT_N_EXEC
        fsm.save(workspace)

        # Sprint loop: drive each sprint through the 4 FSM states individually
        # per architecture.md: SPRINT_N_EXEC → QA_RUN → STATE_UPDATE → PL_REVIEW
        # with state.json checkpointed after each state.
        sprint_idx = 0
        while sprint_idx < state.total_sprints:
            sprint_num = sprint_idx + 1
            state.current_sprint = sprint_num

            # ── SPRINT_N_EXEC: Run backend + frontend agents ──
            self._notify("SPRINT_N_EXEC", f"Sprint {sprint_num}/{state.total_sprints} — dev agents")
            sprint_result = self._orch._run_single_sprint(state, sprint_idx)

            # Write agent logs for this sprint immediately (not batched)
            for agent_name in ["backend_agent", "frontend_agent", "qa_agent"]:
                memory = state.agent_memory.get(agent_name)
                if memory and memory.work_log:
                    # Only write the latest entry (current sprint's work)
                    latest = memory.work_log[-1] if memory.work_log else None
                    if latest and f"Sprint {sprint_num}" in latest:
                        append_agent_log(workspace, agent_name, sprint_num, latest)

            fsm.complete_state()  # SPRINT_N_EXEC → QA_RUN
            fsm.save(workspace)

            # ── QA_RUN: QA results already captured during _run_single_sprint ──
            # Write qa_log_sprint_N.md with test results
            self._notify("QA_RUN", f"Sprint {sprint_num} — QA results logged")
            qa_tasks = sprint_result.get("tasks", {})
            logger.info("QA_RUN debug — sprint_result task IDs: %s", list(qa_tasks.keys()))
            for tid, result in qa_tasks.items():
                cr_list = result.get("command_results", [])
                logger.info("  task %s: command_results count=%d, keys=%s", tid, len(cr_list), list(result.keys()))
            qa_summary_parts = []
            for tid, result in qa_tasks.items():
                if result.get("command_results"):
                    for cr in result["command_results"]:
                        qa_summary_parts.append(
                            f"Command: {cr.get('cmd', '')}\n"
                            f"Exit code: {cr.get('returncode', 'N/A')}\n"
                            f"Stdout: {cr.get('stdout', '')[:500]}\n"
                            f"Stderr: {cr.get('stderr', '')[:500]}"
                        )
            qa_log_content = (
                f"# QA Log — Sprint {sprint_num}\n\n"
                + ("\n---\n".join(qa_summary_parts) if qa_summary_parts else "No test commands executed.")
            )
            qa_log_path = os.path.join(workspace, "qa", f"qa_log_sprint_{sprint_num}.md")
            os.makedirs(os.path.dirname(qa_log_path), exist_ok=True)
            with open(qa_log_path, "w", encoding="utf-8") as f:
                f.write(qa_log_content)

            fsm.complete_state()  # QA_RUN → STATE_UPDATE
            fsm.save(workspace)

            # ── STATE_UPDATE: Update project_state.md (no LLM call) ──
            self._notify("STATE_UPDATE", f"Sprint {sprint_num} — updating project state")
            additions = self._collect_sprint_additions(state, sprint_num)
            run_state_update(workspace, sprint_num, additions)

            # Update sprint plan artifact on disk
            if state.sprint_plan:
                write_sprint_plan(workspace, json.dumps(state.sprint_plan, indent=2))

            fsm.complete_state()  # STATE_UPDATE → PL_REVIEW
            fsm.save(workspace)

            # ── PL_REVIEW: Project Lead reviews and adjusts future sprints ──
            if sprint_idx < state.total_sprints - 1:
                self._notify("PL_REVIEW", f"Sprint {sprint_num} — Project Lead reviewing")
                self._orch._pl_review_and_adjust(state, sprint_idx)
                # PL may have inserted sprints — re-read total
                state = self._orch.active_projects[project_id]
                # Create next sprint on JIRA
                if sprint_idx + 1 < len(state.sprint_plan.get("sprints", [])):
                    next_sprint_data = state.sprint_plan["sprints"][sprint_idx + 1]
                    self._orch._create_jira_sprint(state, sprint_index=sprint_idx + 1, sprint_data=next_sprint_data)
            else:
                self._notify("PL_REVIEW", f"Sprint {sprint_num} — final sprint, skipping review")

            fsm.complete_state()  # PL_REVIEW → SPRINT_N_EXEC (or DONE if last)
            fsm.save(workspace)

            logger.info("=== Sprint %d complete ===", sprint_num)
            sprint_idx += 1

        # DONE: Generate RUNBOOK.md
        self._notify("DONE", "Pipeline complete")
        generate_runbook(
            workspace,
            project_type="website",
            summary=f"Completed {state.total_sprints} sprints.",
            run_instructions=(
                "cd to workspace directory\n"
                "Backend: activate venv, python app.py (port 8001)\n"
                "Frontend: cd frontend && npx vite (port 5173)\n"
                "Open http://localhost:5173"
            ),
        )

        # Launch the completed site (backend + frontend dev server)
        self._notify("DONE", "Launching site on http://localhost:5173")
        self._orch.launch_site(project_id)

        # Update FSM phase in state
        state.fsm_phase = "DONE"
        state.completed_states = list(fsm.completed_states)
        state.site_url = "http://localhost:5173"

        return state

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove markdown code fences (```lang / ```) from text."""
        lines = text.split("\n")
        return "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    def _write_architecture_artifacts(self, workspace: str, raw_output: str) -> None:
        """Parse architect output and write artifact files."""
        # Try to extract labeled sections
        sections = {}
        current_label = None
        current_lines: list[str] = []

        for line in raw_output.split("\n"):
            if line.strip().startswith("### "):
                if current_label and current_lines:
                    sections[current_label] = "\n".join(current_lines).strip()
                current_label = line.strip().lstrip("# ").strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_label and current_lines:
            sections[current_label] = "\n".join(current_lines).strip()

        # Write named sections as artifact files.
        # Strip markdown fences from all sections — the Architect often wraps
        # content in ```markdown or ```python fences that break downstream parsing
        # (e.g., requirements.txt fed to pip install).
        for label, content in sections.items():
            content = self._strip_markdown_fences(content)
            label_upper = label.upper().replace(" ", "_")
            if "INTERFACE" in label_upper or "CONTRACT" in label_upper:
                write_interface_contract(workspace, content)
            elif "REQUIREMENT" in label_upper or "DEPENDENC" in label_upper:
                write_requirements_txt(workspace, content)
            elif "BACKEND" in label_upper:
                write_design_doc(workspace, "backend_agent", content)
            elif "FRONTEND" in label_upper:
                write_design_doc(workspace, "frontend_agent", content)
            elif "QA" in label_upper:
                write_design_doc(workspace, "qa_agent", content)

        # If no sections parsed, write the entire output as a generic design doc
        if not sections:
            write_design_doc(workspace, "architecture", raw_output)

    def _collect_sprint_additions(self, state: ProjectState, sprint_num: int) -> list[str]:
        """Collect file descriptions from a sprint's agent memory."""
        additions = []
        for agent_name, memory in state.agent_memory.items():
            for file_path in memory.files_written:
                additions.append(f"{file_path} — written by {agent_name}")
        return additions

    # ── Proxy methods for app.py compatibility ────────────────────────

    @property
    def active_projects(self) -> Dict[str, ProjectState]:
        return self._orch.active_projects

    @property
    def jira_issues(self):
        return self._orch.jira_issues
