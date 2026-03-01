"""Main orchestrator engine for AgileGPT.

Implements the full PM -> Dev Team SCRUM loop:
1. PM creates sprint plan + writes scrum_plan.json and requirements.txt to workspace
2. For each sprint: create JIRA sprint + tasks, run agents, PM reviews & adjusts
3. Agents get task-specific context with persistent memory across sprints
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.pm_agent import PMAgent
from agents.qa_agent import QAAgent
from config import Config
from orchestrator.state import AgentMemory, ProjectState, SprintRecord
from services.jira_package.client import JiraClient, create_client_from_env
from services.jira_package.issues import Issues, JiraTask
from services.jira_package.sprints import Sprints
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


DEFAULT_WWF_EARTH_DAY_BRIEF = """
The client is World Wildlife Fund (WWF-US), a global conservation organization working across 100 countries to protect wildlife, natural systems, and human communities.

Mission: To ensure a planet where people and nature thrive by creating linked and holistic solutions to environmental challenges.
Vision: A future where nature and people flourish, with conservation that is humane, durable, and science-based.

About WWF-US: WWF focuses on integrated approaches to conservation, sustainable development, and climate resilience, partnering with governments, communities, businesses, and nonprofits to protect endangered species, safeguard oceans, forests, and freshwater systems, and promote sustainable infrastructure and food systems. Headquarters: 1250 24th Street NW, Washington, DC 20037, USA. They primarily serve global communities, Indigenous peoples, governments, businesses, conservation leaders, and supporters committed to environmental sustainability and wildlife conservation.

Core Values: Holistic and integrated conservation, science-based solutions, durability and sustainability, community leadership and participation, equity and inclusion, partnership and collaboration, innovation and creativity, integrity and transparency.

Brand Tone: Professional, hopeful, urgent, community-focused, and collaborative with strong emphasis on science-based and durable conservation solutions.

Key Programs & Services include tiger conservation, oceans futures, plastics treaty advocacy, GRID, 30x30, Tribal Buffalo Lifeways, ManglarIA, education and financing initiatives.

Build Requirements:
- Build a visually stunning, modern website using React for the frontend and Flask for the backend API.
- Communicate mission, vision, programs, impact, leadership, events, and financial transparency clearly.
- Feature rich visual storytelling with hero sections, image galleries, and interactive elements.
- Emphasize urgent yet hopeful messaging throughout the design.
- Make pathways for donations, volunteering, advocacy, and partnerships obvious and accessible.
- Support global and Indigenous audiences with inclusive design.
- Easy to navigate with a professional navigation system and smooth scrolling.
- Integrate interactive tools for donations, email subscriptions, and contact forms.
- Use a nature-inspired color palette with greens, earth tones, and clean whites.
- Include smooth animations, transitions, and micro-interactions for a polished feel.
- Ensure responsive design that works beautifully on mobile, tablet, and desktop.
- The result should look like a professionally designed website, not a student project.
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """Try to parse JSON from LLM output, stripping markdown fences if present.

    Also attempts to repair truncated JSON by closing open brackets/braces.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Attempt to repair truncated JSON by closing open brackets/braces.
    if start != -1:
        fragment = text[start:]
        # Close any open string literal.
        in_string = False
        escape = False
        for ch in fragment:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
        if in_string:
            fragment += '"'
        # Count open brackets/braces and close them.
        opens = []
        in_str = False
        esc = False
        for ch in fragment:
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in ('{', '['):
                opens.append(ch)
            elif ch == '}' and opens and opens[-1] == '{':
                opens.pop()
            elif ch == ']' and opens and opens[-1] == '[':
                opens.pop()
        # Close in reverse order.
        for bracket in reversed(opens):
            fragment += ']' if bracket == '[' else '}'
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass

    return None


def _setup_workspace(project_id: str, base_dir: str = "") -> str:
    """Create an isolated project workspace directory with a venv."""
    if not base_dir:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspaces")
    workspace = os.path.join(base_dir, project_id)
    os.makedirs(workspace, exist_ok=True)

    venv_path = os.path.join(workspace, ".venv")
    if not os.path.exists(venv_path):
        logger.info("Creating venv at %s", venv_path)
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)

    return workspace


def _pip_install(workspace: str, requirements: List[str]) -> None:
    """Install requirements into the workspace venv."""
    if not requirements:
        return
    venv_path = os.path.join(workspace, ".venv")
    if os.name == "nt":
        pip_bin = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        pip_bin = os.path.join(venv_path, "bin", "pip")
    subprocess.run([pip_bin, "install", *requirements], capture_output=True, check=False)


def _write_file(workspace: str, relative_path: str, content: str) -> str:
    """Write a file into the workspace and return the absolute path."""
    full_path = os.path.join(workspace, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return full_path


def _run_command(workspace: str, cmd: str, timeout: int = 60) -> Dict[str, Any]:
    """Run a shell command inside the workspace using the workspace venv."""
    venv_path = os.path.join(workspace, ".venv")
    env = os.environ.copy()
    if os.name == "nt":
        env["PATH"] = os.path.join(venv_path, "Scripts") + os.pathsep + env.get("PATH", "")
    else:
        env["PATH"] = os.path.join(venv_path, "bin") + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = venv_path

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=workspace, capture_output=True,
            text=True, timeout=timeout, env=env,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def _scan_workspace_files(workspace: str) -> Dict[str, str]:
    """Scan workspace directory for source files. Returns relative_path -> content."""
    files: Dict[str, str] = {}
    skip_dirs = {'.venv', '__pycache__', 'node_modules', '.git'}
    source_exts = {'.py', '.js', '.jsx', '.html', '.css', '.json', '.txt', '.md'}
    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in source_exts:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, workspace).replace("\\", "/")
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if len(content) < 50000:  # Skip overly large files
                        files[rel_path] = content
                except Exception:
                    pass
    return files


def _start_backend(workspace: str) -> Optional[subprocess.Popen]:
    """Start the Flask backend in the workspace. Returns the process or None."""
    app_path = os.path.join(workspace, "app.py")
    if not os.path.exists(app_path):
        logger.warning("No app.py found in workspace, cannot start backend")
        return None

    venv_path = os.path.join(workspace, ".venv")
    env = os.environ.copy()
    if os.name == "nt":
        python_bin = os.path.join(venv_path, "Scripts", "python.exe")
        env["PATH"] = os.path.join(venv_path, "Scripts") + os.pathsep + env.get("PATH", "")
    else:
        python_bin = os.path.join(venv_path, "bin", "python")
        env["PATH"] = os.path.join(venv_path, "bin") + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = venv_path

    try:
        proc = subprocess.Popen(
            [python_bin, "app.py"],
            cwd=workspace, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        # Give Flask a moment to start.
        time.sleep(3)
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            logger.error("Backend exited immediately: %s", stderr[-500:])
            return None
        logger.info("Backend started (pid=%d)", proc.pid)
        return proc
    except Exception as e:
        logger.error("Failed to start backend: %s", e)
        return None


def _stop_backend(proc: Optional[subprocess.Popen]) -> None:
    """Stop a running backend process."""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
    except Exception:
        pass
    logger.info("Backend stopped")


def _classify_task(description: str) -> str:
    """Return 'backend', 'frontend', or 'qa' based on task description prefix.

    The PM agent is instructed to start every task description with exactly
    'backend', 'frontend', or 'integration'. We check the first word and
    fall back to keyword scanning if the prefix is missing.
    """
    first_word = description.strip().split()[0].lower() if description.strip() else ""
    if first_word == "backend":
        return "backend"
    if first_word == "frontend":
        return "frontend"
    if first_word in ("integration", "qa", "test"):
        return "qa"
    # Fallback: scan the description for keywords in case PM formatting drifted.
    desc_lower = description.lower()
    if "backend" in desc_lower or "flask" in desc_lower or "app.py" in desc_lower:
        return "backend"
    if "frontend" in desc_lower or "react" in desc_lower or "index.html" in desc_lower:
        return "frontend"
    if "test" in desc_lower or "integration" in desc_lower or "pytest" in desc_lower or "validate" in desc_lower:
        return "qa"
    return "unknown"


def _jira_role(agent_type: str) -> str:
    """Map agent type to JIRA role prefix."""
    return {"backend": "backend", "frontend": "frontend", "qa": "tester"}.get(agent_type, "")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Coordinates the full PM -> Agent SCRUM cycle.

    Flow:
    1. start_project()      - set up workspace, initialize state
    2. run_planning()        - PM creates full sprint plan, writes to workspace, creates Sprint 1 on JIRA
    3. run_all_sprints()     - main loop: for each sprint, run agents, PM reviews, create next sprint
    """

    def __init__(self) -> None:
        self.config = Config()
        self.llm_service = LLMService(self.config)

        # JIRA
        self.jira_client: JiraClient = create_client_from_env()
        self.jira_issues = Issues(self.jira_client)
        self.jira_sprints = Sprints(self.jira_client)

        # Agents
        self.pm_agent = PMAgent(self.llm_service)
        self.frontend_agent = FrontendAgent(self.llm_service)
        self.backend_agent = BackendAgent(self.llm_service)
        self.qa_agent = QAAgent(self.llm_service)

        self.active_projects: Dict[str, ProjectState] = {}
        self._site_processes: Dict[str, subprocess.Popen] = {}

    # ------------------------------------------------------------------
    # 1. Project initialization
    # ------------------------------------------------------------------

    def start_project(self, project_id: str, clarified_story: str) -> ProjectState:
        """Create workspace, venv, and initial project state."""
        workspace = _setup_workspace(project_id)
        state = ProjectState(
            project_id=project_id,
            clarified_user_story=clarified_story,
            workspace_path=workspace,
        )
        self.active_projects[project_id] = state
        logger.info("Project %s started, workspace: %s", project_id, workspace)
        return state

    # ------------------------------------------------------------------
    # 2. Planning phase
    # ------------------------------------------------------------------

    def run_planning(self, project_id: str) -> Dict[str, Any]:
        """PM creates the full sprint plan.

        - Writes scrum_plan.json to workspace
        - Writes requirements.txt to workspace
        - Creates Sprint 1 tasks + sprint on JIRA
        - Returns the parsed plan dict
        """
        state = self.active_projects[project_id]

        planning_context = {
            "project_id": state.project_id,
            "clarified_user_story": state.clarified_user_story,
            "current_sprint": 1,
            "sprint_status": "planning",
        }

        raw_output = self.pm_agent.planning_mode(planning_context)
        plan = _parse_json(raw_output)
        if not plan:
            logger.error("PM planning returned invalid JSON:\n%s", raw_output[:500])
            raise ValueError("PM planning did not return valid JSON. Raw output saved to state.")

        # Persist plan to state.
        state.sprint_plan = plan
        state.shared_contract = plan.get("shared_contract")
        state.handoff_contract = plan.get("handoff_contract")
        state.total_sprints = len(plan.get("sprints", []))

        # Write plan file to workspace.
        _write_file(state.workspace_path, "scrum_plan.json", json.dumps(plan, indent=2))

        # Write requirements.txt from plan if present, otherwise default Flask.
        baseline = ["flask", "flask-cors", "requests", "pytest"]
        requirements = plan.get("requirements")
        if isinstance(requirements, list):
            req_lines = list(set(baseline + requirements))
        else:
            req_lines = baseline
        _write_file(state.workspace_path, "requirements.txt", "\n".join(req_lines) + "\n")
        state.requirements_written = True

        # Install requirements into workspace venv.
        _pip_install(state.workspace_path, req_lines)

        # Create Sprint 1 on JIRA.
        sprints_data = plan.get("sprints", [])
        if sprints_data:
            self._create_jira_sprint(state, sprint_index=0, sprint_data=sprints_data[0])

        logger.info("Planning complete: %d sprints planned", state.total_sprints)
        return plan

    # ------------------------------------------------------------------
    # 3. Main sprint loop
    # ------------------------------------------------------------------

    def run_all_sprints(self, project_id: str) -> List[Dict[str, Any]]:
        """Execute all sprints sequentially. Returns results per sprint.

        Uses a while loop instead of for-range because the PM review step
        may insert additional sprints, changing state.total_sprints mid-run.
        """
        state = self.active_projects[project_id]
        all_results = []

        sprint_idx = 0
        while sprint_idx < state.total_sprints:
            sprint_num = sprint_idx + 1
            state.current_sprint = sprint_num
            logger.info("=== Starting Sprint %d/%d ===", sprint_num, state.total_sprints)

            sprint_result = self._run_single_sprint(state, sprint_idx)
            all_results.append(sprint_result)

            # PM reviews completed sprint and adjusts future tasks.
            if sprint_idx < state.total_sprints - 1:
                self._pm_review_and_adjust(state, sprint_idx)
                # total_sprints may have changed if PM inserted a sprint.
                next_sprint_data = state.sprint_plan["sprints"][sprint_idx + 1]
                self._create_jira_sprint(state, sprint_index=sprint_idx + 1, sprint_data=next_sprint_data)

            logger.info("=== Sprint %d complete ===", sprint_num)
            sprint_idx += 1

        return all_results

    def run_single_sprint(self, project_id: str, sprint_index: int) -> Dict[str, Any]:
        """Run just one sprint (useful for step-by-step control from UI)."""
        state = self.active_projects[project_id]
        state.current_sprint = sprint_index + 1
        return self._run_single_sprint(state, sprint_index)

    # ------------------------------------------------------------------
    # Internal: single sprint execution
    # ------------------------------------------------------------------

    def _run_single_sprint(self, state: ProjectState, sprint_index: int) -> Dict[str, Any]:
        """Execute one sprint: call each agent for their task, collect results."""
        sprints = state.sprint_plan.get("sprints", [])
        if sprint_index >= len(sprints):
            return {"error": f"Sprint index {sprint_index} out of range"}

        sprint_data = sprints[sprint_index]
        tasks = sprint_data.get("tasks", [])
        sprint_record = self._get_or_create_record(state, sprint_index)
        sprint_record.status = "in_progress"

        # Start the JIRA sprint if it exists.
        if sprint_record.jira_sprint_id:
            started = self.jira_sprints.start_sprint(sprint_record.jira_sprint_id)
            if not started:
                logger.warning("Could not start JIRA sprint %s: %s",
                               sprint_record.jira_sprint_id, self.jira_sprints.last_sprint_error)

        results: Dict[str, Any] = {"sprint": sprint_index + 1, "tasks": {}}

        # Execute tasks in order: backend -> frontend -> qa.
        ordered_tasks = sorted(tasks, key=lambda t: {
            "backend": 0, "frontend": 1, "integration": 2, "qa": 2
        }.get(_classify_task(t.get("description", "")), 3))

        backend_proc = None
        for task in ordered_tasks:
            task_type = _classify_task(task.get("description", ""))
            task_id = task.get("id", "")
            task_name = task.get("name", "")

            # Start backend server before QA tasks so integration tests can hit it.
            if task_type == "qa" and backend_proc is None:
                backend_proc = _start_backend(state.workspace_path)

            logger.info("  Running %s task: %s", task_type, task_name)

            agent_result = self._run_agent_for_task(state, task, task_type)
            results["tasks"][task_id] = agent_result

            # Update JIRA task with result summary.
            jira_id = sprint_record.jira_task_ids.get(task_id)
            if jira_id:
                status_text = "DONE" if agent_result.get("success") else "FAILED"
                update_text = f"{status_text}: {agent_result.get('summary', 'No summary')}"
                self.jira_issues.update(jira_id, update_text)

            sprint_record.task_results[task_id] = (
                "DONE" if agent_result.get("success") else "FAILED"
            )

        # Stop backend server after all tasks complete.
        _stop_backend(backend_proc)

        # Close the JIRA sprint.
        if sprint_record.jira_sprint_id:
            stopped = self.jira_sprints.stop_sprint(sprint_record.jira_sprint_id)
            if stopped:
                logger.info("JIRA sprint %d closed", sprint_record.jira_sprint_id)
            else:
                logger.warning("Could not close JIRA sprint %d: %s",
                               sprint_record.jira_sprint_id, self.jira_sprints.last_sprint_error)

        sprint_record.status = "completed"

        # Update scrum_plan.json on disk with task statuses.
        _write_file(state.workspace_path, "scrum_plan.json",
                     json.dumps(state.sprint_plan, indent=2))

        return results

    # ------------------------------------------------------------------
    # Internal: agent execution
    # ------------------------------------------------------------------

    def _run_agent_for_task(self, state: ProjectState, task: Dict, task_type: str) -> Dict[str, Any]:
        """Call the appropriate agent with full context including memory."""
        agent_map = {
            "backend": self.backend_agent,
            "frontend": self.frontend_agent,
            "qa": self.qa_agent,
        }
        agent = agent_map.get(task_type)
        if not agent:
            return {"success": False, "summary": f"Unknown task type: {task_type}"}

        # Build agent-specific memory.
        memory = state.agent_memory.get(agent.name, AgentMemory())

        # Scan actual workspace files for accurate, up-to-date context.
        workspace_files = _scan_workspace_files(state.workspace_path)

        # Filter files relevant to this agent type to reduce context size.
        if task_type == "backend":
            relevant_files = {p: c for p, c in workspace_files.items()
                              if p.endswith('.py') and not p.startswith('tests/')}
        elif task_type == "frontend":
            relevant_files = {p: c for p, c in workspace_files.items()
                              if p.endswith(('.html', '.css', '.js')) and not p.startswith('tests/')}
        elif task_type == "qa":
            relevant_files = workspace_files
        else:
            relevant_files = workspace_files

        # Build context the agent receives.
        context = {
            "project_id": state.project_id,
            "current_sprint": state.current_sprint,
            "total_sprints": state.total_sprints,
            "task": task,
            "shared_contract": state.shared_contract,
            "handoff_contract": state.handoff_contract,
            # Workspace files: actual content from disk, filtered by agent role.
            "project_state_summary": {
                "current_files": relevant_files,
                "workspace_file_listing": sorted(workspace_files.keys()),
                "previous_work": memory.work_log[-5:] if memory.work_log else [],
            },
        }

        try:
            raw_output = agent.run(context)
        except Exception as e:
            logger.error("Agent %s failed with error: %s", agent.name, e)
            return {"success": False, "summary": f"Agent error: {e}"}

        parsed = _parse_json(raw_output)
        if not parsed:
            logger.error("Agent %s returned invalid JSON:\n%s", agent.name, raw_output[:500])
            return {"success": False, "summary": "Agent returned invalid JSON", "raw": raw_output[:500]}

        # Write files to workspace.
        files_written = {}
        for file_entry in parsed.get("files_to_write", []):
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if path and content:
                _write_file(state.workspace_path, path, content)
                files_written[path] = content
                logger.info("    Wrote: %s", path)

        # Run commands in workspace (skip server-start commands that would block).
        server_patterns = ["python app.py", "flask run", "python -m flask", "uvicorn", "gunicorn"]
        cmd_results = []
        for cmd in parsed.get("commands_to_run", []):
            cmd_stripped = cmd.strip()
            if not cmd_stripped:
                continue
            if any(pat in cmd_stripped.lower() for pat in server_patterns):
                logger.info("    Skipping server-start command: %s", cmd_stripped)
                continue
            logger.info("    Running: %s", cmd_stripped)
            result = _run_command(state.workspace_path, cmd_stripped)
            cmd_results.append({"cmd": cmd_stripped, **result})

        # Update agent memory.
        memory.files_written.update(files_written)
        work_summary = f"Sprint {state.current_sprint}: {task.get('name', 'unknown')} - wrote {list(files_written.keys())}"
        memory.work_log.append(work_summary)
        state.agent_memory[agent.name] = memory

        # Determine success from command results (if any commands ran).
        success = True
        if cmd_results:
            success = all(r["returncode"] == 0 for r in cmd_results)
            # Log test output for debugging.
            for cr in cmd_results:
                if cr.get("returncode") != 0:
                    logger.warning("Command failed: %s\nSTDOUT:\n%s\nSTDERR:\n%s",
                                   cr.get("cmd", ""), cr.get("stdout", "")[:1000], cr.get("stderr", "")[:1000])

        return {
            "success": success,
            "summary": parsed.get("explanation", ""),
            "files_written": list(files_written.keys()),
            "command_results": cmd_results,
        }

    # ------------------------------------------------------------------
    # Internal: PM review between sprints
    # ------------------------------------------------------------------

    def _pm_review_and_adjust(self, state: ProjectState, completed_sprint_index: int) -> None:
        """PM reviews sprint results and adjusts future sprint tasks if needed."""
        completed_sprint = state.sprint_plan["sprints"][completed_sprint_index]
        sprint_record = state.sprint_records[completed_sprint_index]

        # Build task statuses for PM review.
        task_statuses = []
        for task in completed_sprint.get("tasks", []):
            tid = task.get("id", "")
            task_statuses.append({
                "id": tid,
                "name": task.get("name", ""),
                "description": task.get("description", ""),
                "status": sprint_record.task_results.get(tid, "UNKNOWN"),
            })

        # Build context for PM review.
        review_context = {
            "project_id": state.project_id,
            "current_sprint": completed_sprint_index + 1,
            "sprint_status": "completed",
            "completed_sprint": {
                "sprint_number": completed_sprint_index + 1,
                "name": completed_sprint.get("name", ""),
                "task_statuses": task_statuses,
            },
            "full_plan": state.sprint_plan,
            "shared_contract": state.shared_contract,
            # Show PM what each agent has built so far.
            "agent_state": {
                name: {
                    "files": list(mem.files_written.keys()),
                    "recent_work": mem.work_log[-3:],
                }
                for name, mem in state.agent_memory.items()
            },
        }

        raw_output = self.pm_agent.review_mode(review_context)
        review = _parse_json(raw_output)

        if not review:
            logger.warning("PM review returned invalid JSON, skipping adjustments")
            return

        action = review.get("action", "unchanged")
        if action == "modified_future_sprints" and "updated_plan" in review:
            updated_plan = review["updated_plan"]
            # Only update future sprints, preserve completed ones.
            new_sprints = updated_plan.get("sprints", [])
            for i in range(completed_sprint_index + 1, len(new_sprints)):
                if i < len(state.sprint_plan["sprints"]):
                    state.sprint_plan["sprints"][i] = new_sprints[i]

            # Update shared_contract if PM changed it.
            if "shared_contract" in updated_plan:
                state.shared_contract = updated_plan["shared_contract"]
                state.sprint_plan["shared_contract"] = updated_plan["shared_contract"]

            logger.info("PM adjusted future sprints after Sprint %d", completed_sprint_index + 1)

        elif action == "insert_sprint" and state.total_sprints < 5:
            new_sprint = review.get("new_sprint")
            if new_sprint and isinstance(new_sprint, dict):
                insert_at = completed_sprint_index + 1
                state.sprint_plan["sprints"].insert(insert_at, new_sprint)
                state.total_sprints += 1
                # Renumber sprint names for consistency.
                for i, s in enumerate(state.sprint_plan["sprints"]):
                    s["name"] = f"Sprint {i + 1}"
                logger.info("PM inserted new sprint after Sprint %d (total now %d)",
                            completed_sprint_index + 1, state.total_sprints)
            else:
                logger.warning("PM requested insert_sprint but provided no valid new_sprint data")

        elif action == "insert_sprint" and state.total_sprints >= 5:
            logger.warning("PM requested insert_sprint but already at max 5 sprints, ignoring")

        # Write updated plan to disk.
        _write_file(state.workspace_path, "scrum_plan.json",
                     json.dumps(state.sprint_plan, indent=2))

    # ------------------------------------------------------------------
    # Internal: JIRA operations
    # ------------------------------------------------------------------

    def _create_jira_sprint(self, state: ProjectState, sprint_index: int,
                            sprint_data: Dict[str, Any]) -> None:
        """Create a JIRA sprint with its 3 tasks."""
        tasks = sprint_data.get("tasks", [])
        sprint_name = sprint_data.get("name", f"Sprint {sprint_index + 1}")

        # Create JIRA tasks.
        jira_tasks = []
        for task in tasks:
            task_type = _classify_task(task.get("description", ""))
            role = _jira_role(task_type)
            jira_tasks.append(JiraTask(
                id="0",
                title=task.get("name", "Unnamed"),
                description=task.get("description", ""),
                status="To Do",
                role=role,
            ))

        created = self.jira_issues.create_bulk(jira_tasks)
        if not created:
            logger.error("Failed to create JIRA tasks: %s", self.jira_issues.last_bulk_error)
            # Continue without JIRA - don't block the sprint.
            record = self._get_or_create_record(state, sprint_index)
            return

        # Map plan task IDs to JIRA IDs.
        record = self._get_or_create_record(state, sprint_index)
        task_ids_for_sprint = []
        for plan_task, jira_task in zip(tasks, created):
            record.jira_task_ids[plan_task.get("id", "")] = jira_task.id
            task_ids_for_sprint.append(jira_task.id)

        # Create JIRA sprint and add tasks.
        sprint_id = self.jira_sprints.create_sprint(
            name=sprint_name,
            task_ids=task_ids_for_sprint,
        )
        if sprint_id:
            record.jira_sprint_id = sprint_id
            logger.info("Created JIRA sprint '%s' (id=%d) with %d tasks",
                        sprint_name, sprint_id, len(task_ids_for_sprint))
        else:
            logger.error("Failed to create JIRA sprint: %s", self.jira_sprints.last_sprint_error)

    def _get_or_create_record(self, state: ProjectState, sprint_index: int) -> SprintRecord:
        """Get existing sprint record or create a new one."""
        for rec in state.sprint_records:
            if rec.sprint_number == sprint_index + 1:
                return rec
        record = SprintRecord(sprint_number=sprint_index + 1)
        state.sprint_records.append(record)
        return record

    # ------------------------------------------------------------------
    # Convenience: run the full pipeline
    # ------------------------------------------------------------------

    def run_full_pipeline(self, project_id: str, clarified_story: str) -> Dict[str, Any]:
        """One-shot: start project -> plan -> execute all sprints -> launch site."""
        self.start_project(project_id, clarified_story)
        plan = self.run_planning(project_id)
        sprint_results = self.run_all_sprints(project_id)
        state = self.active_projects[project_id]
        result = {
            "project_id": project_id,
            "workspace": state.workspace_path,
            "total_sprints": state.total_sprints,
            "plan": plan,
            "sprint_results": sprint_results,
        }
        # Automatically launch the site for the user to browse.
        self.launch_site(project_id)
        return result

    # ------------------------------------------------------------------
    # End-of-SCRUM: launch site on localhost
    # ------------------------------------------------------------------

    def launch_site(self, project_id: str) -> Optional[subprocess.Popen]:
        """Start the completed site on localhost:5000 for the user to browse.

        Called automatically at the end of run_full_pipeline. Can also be
        called standalone after run_all_sprints. The Flask process runs in
        the background and stays alive until stop_site() is called or the
        Orchestrator is garbage-collected.
        """
        state = self.active_projects[project_id]
        workspace = state.workspace_path

        # Ensure requirements are installed.
        req_path = os.path.join(workspace, "requirements.txt")
        if os.path.exists(req_path):
            with open(req_path, "r", encoding="utf-8") as f:
                reqs = [line.strip() for line in f if line.strip()]
            _pip_install(workspace, reqs)

        proc = _start_backend(workspace)
        if not proc:
            logger.error("Could not launch site — no running backend.")
            return None

        self._site_processes[project_id] = proc

        print("\n" + "=" * 60)
        print("  YOUR SITE IS LIVE!")
        print("  Open http://localhost:5000 in your browser")
        print("  Press Ctrl+C to stop the server")
        print("=" * 60 + "\n")

        return proc

    def stop_site(self, project_id: str) -> None:
        """Stop a previously launched site."""
        proc = self._site_processes.pop(project_id, None)
        _stop_backend(proc)
