"""Main orchestrator engine for AgileGPT.

This is the BRAIN of the entire system. It coordinates the full automated SCRUM cycle:

WHAT IS SCRUM?
  SCRUM is a project management methodology where work is broken into "sprints"
  (short work cycles, typically 1-2 weeks in real life). Each sprint has specific
  tasks, and after each sprint the team reviews what worked and adjusts the plan.

HOW AGILEGPT AUTOMATES THIS:
  Instead of human developers, we have AI agents (LLM-powered bots) that play
  each role on the team. The orchestrator coordinates them like a conductor:

  1. PM AGENT plans the project → produces a JSON sprint plan
  2. For each sprint:
     a. BACKEND AGENT writes Flask/Python API code
     b. FRONTEND AGENT writes React/HTML/CSS/JS UI code
     c. QA AGENT writes and runs tests against the live server
     d. PM AGENT reviews results and adjusts future sprints if needed
  3. After all sprints → launches the completed site on localhost:5000

  Each agent operates independently — they only see their assigned task and
  the shared API contract. The orchestrator handles all the plumbing:
  creating workspaces, writing files, running commands, managing JIRA tickets,
  passing context between agents, and tracking progress.

KEY CONCEPTS:
  - Workspace: An isolated directory with its own Python venv where all generated
    code lives. Each project gets a fresh workspace.
  - Shared Contract: A JSON spec defining every API endpoint (path, method,
    request/response schemas). All agents reference it for consistency.
  - Agent Memory: The orchestrator tracks what each agent has built across sprints
    so they can iterate on their own work without starting from scratch.
  - PM Review: After each sprint, the PM agent examines pass/fail results and
    can modify future sprint tasks or insert new sprints to fix issues.
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
The client is Palestine Children's Relief Fund (PCRF).

Their mission: To provide urgent and long-term medical and humanitarian relief to children in Palestine and the Middle East, ensuring that children receive life-saving medical care regardless of politics or religion.

About them: PCRF is a nonprofit organization dedicated to delivering critical medical care and humanitarian aid to children in Palestine and the broader Middle East. Founded over 30 years ago, PCRF operates through a global network of volunteers, medical professionals, and chapters to provide emergency relief, medical missions, treatment abroad, and infrastructure development. The organization responds to crises such as the 2023 Gaza war by providing food, medical supplies, emergency clinics, and rebuilding healthcare infrastructure, while also supporting ongoing pediatric cardiac and cancer care. PCRF maintains a 4-star Charity Navigator rating and emphasizes community-centered capacity development and long-term healthcare improvements.

Founded: Over 30 years ago (exact year not specified).

Located in Ramallah, West Bank, Palestine; with chapters and offices in the United States, Jordan, Italy, Switzerland, Lebanon, Egypt.

They primarily serve: Children and families in Palestine (Gaza, West Bank), Lebanon, and surrounding regions affected by conflict and humanitarian crises, including displaced, sick, injured, and vulnerable children requiring medical and humanitarian aid..

Core values: Humanity, Integrity, Resilience, Community-centered support, Non-discrimination, Collaboration, Transparency, Commitment to children’s health and wellbeing.

Brand tone: The tone is resolute, compassionate, community-focused, and hopeful, emphasizing resilience, urgent action, and the unyielding commitment to children’s health and wellbeing despite crisis and adversity..

Key programs/services:
  - Urgent Response to the Humanitarian Crisis: Emergency medical missions, field hospitals, mobile clinics, direct aid distribution, food parcels, hygiene kits, winter clothing, and sealing off kits to displaced families in Gaza, West Bank, Lebanon, and beyond.
  - Treatment Abroad Program: Facilitates evacuation and specialized medical care abroad for critically ill children from Gaza and surrounding regions, coordinating care in multiple countries.
  - Medical Missions: Deploys volunteer medical teams to provide specialized surgical and medical care in Gaza, West Bank, Jordan, and Lebanon.
  - Humanitarian Programs: Social work initiatives providing non-surgical medical needs, including Monthly Disabled Sponsorship, One-Time Medical Sponsorship, and Gaza Orphan Sponsorship programs.
  - One-Time Surgical Sponsorship (OTS): Provides urgent, life-saving surgeries across multiple specialties to children facing financial or systemic barriers.
  - Community-Centered Capacity Development and Infrastructure Projects: Supports healthcare infrastructure development, rehabilitation of clinics and hospitals, and community health projects across Gaza, West Bank, Lebanon, and Jordan.
  - Pediatric Cardiac Care Support: Supports the Pediatric ICU and Cardiac Department at Palestine Medical Complex with equipment, training, and supplies for heart surgeries and catheterizations.
  - Pediatric Oncology Care: Sustains pediatric cancer care at Huda Al Masri Pediatric Cancer Department in the West Bank, providing medical treatment and therapeutic support.

Impact stats:
  - Total Aid Provided (Oct 2023 - Dec 2024): $40,487,335.22
  - Food Parcels Distributed in Gaza: 3,774
  - Flour Distributed in Gaza: 385,250 kilograms
  - Water Delivered in Gaza: 14,657,500 liters
  - Emergency Medical Missions Deployed in Gaza (2024): 7
  - Patients Treated in Gaza Medical Points (2024): 11,709
  - Children Evacuated for Treatment Abroad (2024): 169
  - One-Time Surgical Sponsorship Cases (2024): 1,024
  - Monthly Disabled Sponsorship Cases (2024): 815
  - Gaza Orphan Sponsorship Cases (2024): 2,160
  - Pediatric Cardiac Surgeries Performed (2024): 137
  - Pediatric Cardiac Catheterizations (2024): 190
  - Pediatric Cancer Department Patient Visits (2024): 2,791
  - Medical Missions Conducted (2024): 23
  - Surgeries Performed in Medical Missions (2024): 1,505

Leadership:
  - Vivian Khalaf (Chairwoman of the Board)
  - Lubna Musa (Chief Executive Officer)
  - Najib Amer (Director of Finance)
  - Arnan Bashir (Director of Operations)
  - Hussein Karakra (Director of Business Development and Relations)
  - Sarah Alrayyes (Director of Chapter Operations (US))
  - Alexa Fasheh (US Director of Finance)
  - Tareq Hailat (Director of Treatment Abroad)

Events: Youth Dabka Training, Women’s Self Defense Seminar, Global Kite Flight, Teach In On Palestine, Hoops for Palestine, Paint for Palestine, All Girls Dabkeh Fundraiser, Gala for Gaza - Youth Initiative, Teaching Tatreez, Benefit Dinners, Tea Time, Palestinian Art Exhibition, Valentine’s Day Teddy Bear Fundraiser, Flowers for Falastin, Tarneeb Night, Letters of Appreciation, Volleyball Tournament, More Than The Miles – Atlanta Runs For PCRF, Annual Benefit Dinners, Battle of the Clubs Volleyball Tournament, Palestinian Culture Night, Cookies on the Plaza, Movie Nights, Ramadan Iftar Dinners, Charity Bake Sale, Volley For Palestine, Art Inspiring Change, Run For Gaza, Marathon Events, Henna Night, Golf Benefit Outing, Summer Picnics, OUD Night For PCRF, Sweets Run-For-Peace, Sahrat Sabaya, Portos for Palestine, Who Dunnit?, Harvest Season Care Package, Global Remembrance Ride for Gaza, BOA Chicago Marathon, Tote-ally for Palestine, Palestine and the Olympic Dream, Moonlight Corn Maze, Healing in Every Thread, Extending an Olive Branch, Dine & Donate Fundraiser for Gaza, Pull-For-Palestine, Soccer Tournament, Fall Fundraiser, Ball for Gaza, LIVE From Palestine US Speaking Tour.

Partners: World Health Organization (WHO), Emergency Medical Teams Coordination Cell (EMTCC), Palestine Ministry of Health (MOH), Samaritan’s Purse, Beit Liqia Municipality, Social Rehabilitation Association at Al Fawwar Camp, Association of Special Needs Parents - Our Children, Al-Amal Association, Palestine Red Crescent Society, Bait Atfal Alsoumod, Social Support Society, HCS, Huda Alshaalan Center, The Southern Society for Special Education, Dallas Chapter (donor), Houston Chapter (donor), Charlotte Chapter (donor), Cultures of Resistance, Childhood Protection Center/PRCS, General Union of Palestinian Women Center, PCRF Chapters and Student Clubs globally.

Financials note: In 2024, PCRF provided over $40 million in aid across Gaza, West Bank, and Lebanon, including nutrition, medical, hygiene, relief supplies, infrastructure, and emergency clinics. The organization maintains a 4-star Charity Navigator rating and effectively leverages both financial and in-kind contributions to maximize impact.

Current website: www.pcrf.net.

Contact: United States: Phone: 330-678-2645, Fax: 330-678-2661, P.O. Box 861716, Los Angeles, CA 90086; Ramallah, West Bank, Palestine: Phone: (970) 2-298-9293, Fax: (970) 2-296-394; Email for donations: giving@pcrf.net; General inquiries: pcrf1@pcrf.net; Media inquiries: media@pcrf.net; Social media: @thePCRF.

Suggested website pages beyond Home & About Us:
  - Our Programs: To detail the wide range of medical, humanitarian, and infrastructure programs PCRF operates.
  - Get Involved: To provide information on volunteering, joining chapters or student clubs, and participating in events.
  - Emergency Response: To highlight PCRF’s urgent relief efforts in Gaza, West Bank, Lebanon, and other crisis areas.
  - Medical Missions: To showcase the international medical missions and specialized care provided.
  - Treatment Abroad: To explain the process and impact of evacuating children for specialized medical care abroad.
  - Impact & Reports: To share detailed impact statistics, annual reports, and financial transparency.
  - Partners & Supporters: To acknowledge key partners, donors, and collaborators.
""".strip()


# ---------------------------------------------------------------------------
# Helpers — utility functions used by the Orchestrator class below.
# These handle low-level operations: parsing AI output, managing the workspace
# filesystem, running shell commands, and starting/stopping the Flask server.
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """Try to parse JSON from LLM output, stripping markdown fences if present.

    WHY THIS EXISTS: AI models sometimes wrap their JSON output in markdown
    code fences (```json ... ```) or include extra text before/after the JSON.
    They can also produce truncated JSON if they hit token limits. This function
    handles all those cases:

    1. First, try parsing the raw text directly as JSON.
    2. If that fails, strip markdown fences and try again.
    3. If that fails, find the outermost { } and try parsing just that.
    4. If that fails, attempt to "repair" truncated JSON by closing any
       unclosed brackets/braces (e.g., if the AI was cut off mid-output).

    Returns the parsed dict, or None if all parsing attempts fail.
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
    """Create an isolated project workspace directory with its own Python virtual environment.

    Each project gets a completely separate folder (workspaces/<project_id>/) so that
    different projects don't interfere with each other. The venv ensures the project's
    Python dependencies (Flask, pytest, etc.) are installed in isolation.
    """
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
    """Install Python packages into the workspace's virtual environment.

    This runs 'pip install' using the venv's pip, not the system pip.
    Handles both Windows (Scripts/pip.exe) and Unix (bin/pip) paths.
    """
    if not requirements:
        return
    venv_path = os.path.join(workspace, ".venv")
    if os.name == "nt":
        pip_bin = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        pip_bin = os.path.join(venv_path, "bin", "pip")
    subprocess.run([pip_bin, "install", *requirements], capture_output=True, check=False)


def _write_file(workspace: str, relative_path: str, content: str) -> str:
    """Write a file into the workspace and return the absolute path.

    Creates any intermediate directories automatically (e.g., routes/ or src/components/).
    This is how agent-generated code gets written to disk — the orchestrator calls this
    for every file in the agent's files_to_write response.
    """
    full_path = os.path.join(workspace, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return full_path


def _run_command(workspace: str, cmd: str, timeout: int = 60) -> Dict[str, Any]:
    """Run a shell command inside the workspace using the workspace's virtual environment.

    This is how agent-requested commands (like 'pytest tests/') get executed.
    The command runs with the venv activated so it has access to installed packages.
    Returns a dict with returncode, stdout, and stderr for result tracking.
    Output is truncated to last 2000 chars to avoid memory issues with verbose output.
    """
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
    """Scan the workspace directory and read all source files into memory.

    Returns a dict of {relative_path: file_content} for every source file found.
    This is how the orchestrator gives agents up-to-date context about what code
    already exists in the workspace — each agent receives the relevant files
    from this scan so it can build on top of previous work.

    Skips non-source directories (.venv, node_modules, __pycache__) and files
    larger than 50KB to avoid overwhelming agent context windows.
    """
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

import urllib.request

def _wait_for_backend(port: int = 8001, timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def _start_backend(workspace: str, port: int = 8001) -> Optional[subprocess.Popen]:
    """Start the Flask backend server in the workspace as a background process.

    The orchestrator starts the backend BEFORE running QA tasks so that
    integration tests can make HTTP requests to http://localhost:5000.
    Also used at the end to launch the completed site for the user to browse.

    Returns the process handle (so we can stop it later) or None if startup failed.
    Waits 3 seconds after launch to give Flask time to initialize.
    """
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
        if not _wait_for_backend(port=8001):
            logger.error("Backend did not become ready within 15s")
            return None
        
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
    """Gracefully stop a running Flask backend process.

    First tries terminate (SIGTERM), then kills (SIGKILL) if it doesn't stop
    within 5 seconds. Called after QA tests complete and when shutting down the site.
    """
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
    """Determine which agent should handle a task based on its description.

    The PM agent is instructed to start every task description with exactly
    'backend', 'frontend', or 'integration'. This function reads that first
    word to route the task to the correct agent.

    Returns 'backend', 'frontend', 'qa', or 'unknown'.

    Falls back to keyword scanning if the PM's formatting drifted (e.g., if
    it said "Flask API" instead of starting with "backend").
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
    """Map an agent type to the corresponding JIRA role label for ticket assignment."""
    return {"backend": "backend", "frontend": "frontend", "qa": "tester"}.get(agent_type, "")


# ---------------------------------------------------------------------------
# Orchestrator — the main coordinator class that runs the entire SCRUM cycle.
#
# Think of this as the "project manager's manager" — it tells the PM agent
# to plan, tells each dev agent to build their piece, checks results, and
# manages all the infrastructure (files, commands, JIRA) in between.
# ---------------------------------------------------------------------------

class Orchestrator:
    """Coordinates the full PM -> Agent SCRUM cycle.

    This is the main class you interact with. The typical usage is:
      orchestrator = Orchestrator()
      result = orchestrator.run_full_pipeline("my-project", "Build a donation website for...")

    That single call will:
    1. Create an isolated workspace with a Python venv
    2. Ask the PM agent to plan 5 sprints (up to 7 max if PM adds sprints)
    3. Execute each sprint (backend → frontend → QA agents)
    4. Have the PM review results after each sprint and adjust the plan
    5. Launch the completed site on http://localhost:5000

    The class holds references to all four agents, the JIRA client, and
    a dict of active project states (so multiple projects could run in theory).
    """

    def __init__(self) -> None:
        # Initialize state dicts FIRST — before any I/O that could raise —
        # so that app.py's getattr(orch, 'active_projects', {}) always works
        # even if the constructor partially fails (e.g. bad JIRA credentials).
        self.active_projects: Dict[str, ProjectState] = {}
        self._site_processes: Dict[str, subprocess.Popen] = {}

        # Load configuration (API keys, model settings, etc.).
        self.config = Config()
        # Create the LLM service — this is the shared connection to the AI provider
        # (e.g., Azure OpenAI) that all agents use to make their AI calls.
        self.llm_service = LLMService(self.config)

        # JIRA integration — used to create sprints and tasks on the JIRA board
        # so the project's progress is visible in a real project management tool.
        self.jira_client: JiraClient = create_client_from_env()
        self.jira_issues = Issues(self.jira_client)
        self.jira_sprints = Sprints(self.jira_client)

        # Initialize all four AI agents. Each gets the same LLM service but has
        # its own system prompt that defines its role and behavior.
        self.pm_agent = PMAgent(self.llm_service)           # Plans sprints and reviews results
        self.frontend_agent = FrontendAgent(self.llm_service)  # Writes React/HTML/CSS/JS
        self.backend_agent = BackendAgent(self.llm_service)    # Writes Flask/Python API code
        self.qa_agent = QAAgent(self.llm_service)              # Writes and runs tests

    # ------------------------------------------------------------------
    # 1. Project initialization — creates the workspace on disk.
    # This is always the FIRST step: set up a clean directory for the project.
    # ------------------------------------------------------------------

    def start_project(self, project_id: str, clarified_story: str) -> ProjectState:
        """Create the project workspace, venv, and initial state tracking object.

        The clarified_story is the finalized user requirement (from the manager agent's
        review process) that tells the PM agent what website to build.
        """
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
    # 2. Planning phase — the PM agent creates the full sprint roadmap.
    # This happens ONCE at the start, producing the entire plan that
    # guides all subsequent sprint execution.
    # ------------------------------------------------------------------

    def run_planning(self, project_id: str) -> Dict[str, Any]:
        """Ask the PM agent to create the full sprint plan for this project.

        This is the second step in the pipeline. The PM agent receives the
        clarified user story and produces a comprehensive JSON plan containing:
        - 5 sprints with 3 tasks each (backend, frontend, QA)
        - A shared API contract defining every endpoint
        - A handoff contract mapping endpoints to files and tests
        - A list of Python requirements to install

        After the PM returns the plan, this method:
        1. Parses the JSON and stores it in project state
        2. Writes scrum_plan.json and requirements.txt to the workspace
        3. Installs Python packages into the workspace venv
        4. Creates the first sprint on JIRA with its 3 tasks
        """
        state = self.active_projects[project_id]

        planning_context = {
            "project_id": state.project_id,
            "clarified_user_story": state.clarified_user_story,
            "current_sprint": 1,
            "sprint_status": "planning",
            "num_sprints": 5,          # Explicit hint so the PM front-loads all sprints
        }

        raw_output = self.pm_agent.planning_mode(planning_context)
        logger.info("PM raw output length: %d chars", len(raw_output))
        logger.debug("PM raw output (first 2000):\n%s", raw_output[:2000])
        plan = _parse_json(raw_output)
        if not plan:
            logger.error("PM planning returned invalid JSON (raw length=%d):\n%s",
                         len(raw_output), raw_output[:1000])
            raise ValueError("PM planning did not return valid JSON. Raw output saved to state.")

        # Persist plan to state.
        state.sprint_plan = plan
        state.shared_contract = plan.get("shared_contract")
        state.handoff_contract = plan.get("handoff_contract")
        state.total_sprints = len(plan.get("sprints", []))
        logger.info("PM planned %d sprints (expected 5) — raw output was %d chars",
                    state.total_sprints, len(raw_output))

        # Write plan file to workspace.
        _write_file(state.workspace_path, "scrum_plan.json", json.dumps(plan, indent=2))
        _write_file(state.workspace_path, "pytest.ini", "[pytest]\ntestpaths = tests\n")
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
    # 3. Main sprint loop — executes all sprints one by one.
    # This is the core execution engine. For each sprint:
    #   1. Run backend agent → frontend agent → QA agent (in that order)
    #   2. PM reviews results and may adjust future sprints
    #   3. Create the next sprint on JIRA
    #   4. Repeat until all sprints are done
    # ------------------------------------------------------------------

    def run_all_sprints(self, project_id: str) -> List[Dict[str, Any]]:
        """Execute all planned sprints sequentially. Returns results per sprint.

        Uses a while loop (not for-range) because the PM review step may INSERT
        additional sprints mid-run, changing state.total_sprints dynamically.
        This is the adaptive nature of SCRUM — the plan evolves based on results.
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

            # After the sprint completes, the PM reviews results and adjusts future tasks.
            # This is the "inspect and adapt" step in SCRUM — if something broke, the PM
            # can modify upcoming sprint tasks to fix it, or even insert a new sprint.
            # Skip this for the last sprint since there's nothing left to adjust.
            if sprint_idx < state.total_sprints - 1:
                self._pm_review_and_adjust(state, sprint_idx)
                # total_sprints may have changed if PM inserted a sprint during review.
                # Fetch the next sprint's data (which may be a newly inserted sprint)
                # and create it on JIRA.
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
    # Internal: single sprint execution — the heart of the engine.
    # Each sprint runs 3 tasks in order: backend → frontend → QA.
    # The backend server is started before QA so tests can hit it.
    # ------------------------------------------------------------------

    def _run_single_sprint(self, state: ProjectState, sprint_index: int) -> Dict[str, Any]:
        """Execute one sprint: assign each task to its agent, collect results, update JIRA."""
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

        # Sort tasks so they execute in the correct order: backend first (0),
        # then frontend (1), then QA/integration (2). This ensures the backend
        # API is built before the frontend tries to call it, and both are built
        # before QA tests run against them.
        ordered_tasks = sorted(tasks, key=lambda t: {
            "backend": 0, "frontend": 1, "integration": 2, "qa": 2
        }.get(_classify_task(t.get("description", "")), 3))

        backend_proc = None
        for task in ordered_tasks:
            task_type = _classify_task(task.get("description", ""))
            task_id = task.get("id", "")
            task_name = task.get("name", "")

            # Start the Flask backend server BEFORE QA tasks run.
            # QA tests make HTTP requests to localhost:5000, so the server must be live.
            # We only start it once (when we encounter the first QA task).
            if task_type == "qa" and backend_proc is None:
                backend_proc = _start_backend(state.workspace_path)
                # Brief cooldown: backend + frontend calls have just consumed most of
                # the rate-limit bucket. Waiting here gives it time to refill before
                # the QA prompt (the largest of the three) hits the API.
                logger.info("  Cooldown before QA task (15s)…")
                time.sleep(15)

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
    # Internal: agent execution — sends a task to the right AI agent.
    # This is where the magic happens: the orchestrator packages up all
    # the context an agent needs, calls the AI, parses its response,
    # writes files to disk, runs commands, and tracks results.
    # ------------------------------------------------------------------

    def _run_agent_for_task(self, state: ProjectState, task: Dict, task_type: str) -> Dict[str, Any]:
        """Call the appropriate AI agent with full context and process its output.

        The flow:
        1. Select the right agent (backend, frontend, or QA) based on task_type
        2. Load the agent's memory (what it built in previous sprints)
        3. Scan the workspace for current files on disk
        4. Filter files relevant to this agent (backend sees .py, frontend sees .html/.css/.js, QA sees all)
        5. Package everything into a context dict and send it to the AI
        6. Parse the AI's JSON response
        7. Write any files the AI produced to the workspace
        8. Run any commands the AI requested (e.g., pytest)
        9. Update the agent's memory with what it just did
        10. Return success/failure and a summary
        """
        # Look up which agent handles this task type.
        agent_map = {
            "backend": self.backend_agent,
            "frontend": self.frontend_agent,
            "qa": self.qa_agent,
        }
        agent = agent_map.get(task_type)
        if not agent:
            return {"success": False, "summary": f"Unknown task type: {task_type}"}

        # Load this agent's persistent memory — what files it wrote previously
        # and a log of its prior work. This lets the agent "remember" across sprints.
        memory = state.agent_memory.get(agent.name, AgentMemory())

        # Scan the actual workspace directory for the latest file contents.
        # This is more reliable than relying on memory alone, because other agents
        # may have written files too (e.g., backend agent's app.py is needed by QA).
        workspace_files = _scan_workspace_files(state.workspace_path)

        # Filter files to only show this agent what's relevant to its role.
        # This reduces context size and prevents agents from being confused by
        # code outside their expertise (e.g., backend agent doesn't need to see CSS).
        if task_type == "backend":
            relevant_files = {p: c for p, c in workspace_files.items()
                              if p.endswith('.py') and not p.startswith('tests/')}
        elif task_type == "frontend":
            relevant_files = {p: c for p, c in workspace_files.items()
                              if p.endswith(('.html', '.css', '.js')) and not p.startswith('tests/')}
        elif task_type == "qa":
            # QA only needs: existing test files (to preserve/extend them),
            # route files (to know what endpoints exist), app.py (for the app entry),
            # and index.html (for frontend structure checks).
            # Sending ALL workspace files makes QA prompts 3-4x larger and burns
            # rate-limit tokens unnecessarily — QA never needs CSS or full JS components.
            relevant_files = {
                p: c for p, c in workspace_files.items()
                if (p.startswith('tests/')
                    or p.startswith('routes/')
                    or p in ('app.py', 'index.html'))
            }
        else:
            relevant_files = workspace_files

        # Build the full context dict that the agent will receive as input.
        # This is everything the agent needs to do its job: the task description,
        # the API contract to follow, existing code to build on, and its own work history.
        context = {
            "project_id": state.project_id,
            "current_sprint": state.current_sprint,
            "total_sprints": state.total_sprints,
            "task": task,
            "shared_contract": state.shared_contract,
            "handoff_contract": state.handoff_contract,
            # Workspace files: actual content from disk, filtered by agent role.
            # current_files lets the agent see and copy existing code to preserve it.
            # workspace_file_listing shows ALL files so the agent knows what exists.
            # previous_work gives the agent a summary of what it did in past sprints.
            "project_state_summary": {
                "current_files": relevant_files,
                "workspace_file_listing": sorted(workspace_files.keys()),
                "previous_work": memory.work_log[-5:] if memory.work_log else [],
            },
        }

        # Send the context to the AI agent and get its response.
        # Wraps agent.run() with its own retry layer on top of whatever the
        # LLMService does internally. Uses true exponential backoff so that
        # a depleted rate-limit bucket has time to refill between attempts.
        # Waits: 30s, 90s, 210s (doubling + 30s base) — much more effective
        # than fixed increments when the API window is ~60 seconds.
        try:
            raw_output = None
            last_exc = None
            for attempt in range(3):
                try:
                    raw_output = agent.run(context)
                    break
                except Exception as exc:
                    last_exc = exc
                    # Only retry on rate-limit-style errors.
                    err_str = str(exc).lower()
                    if "429" in err_str or "rate" in err_str or "limit" in err_str or "retry" in err_str:
                        wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                        logger.warning("Agent %s rate-limited (attempt %d/3), waiting %ds…",
                                       agent.name, attempt + 1, wait)
                        time.sleep(wait)
                    else:
                        raise  # non-rate-limit error — don't retry
            if raw_output is None:
                raise last_exc
        except Exception as e:
            logger.error("Agent %s failed with error: %s", agent.name, e)
            return {"success": False, "summary": f"Agent error: {e}"}

        # Parse the AI's response from raw text into a Python dict.
        # If the AI returned malformed JSON, we log the error and report failure.
        parsed = _parse_json(raw_output)
        if not parsed:
            logger.error("Agent %s returned invalid JSON:\n%s", agent.name, raw_output[:500])
            return {"success": False, "summary": "Agent returned invalid JSON", "raw": raw_output[:500]}

        # Write every file the agent produced to the workspace on disk.
        # The agent returns complete file contents (not patches), so each write
        # creates or fully replaces the file at that path.
        files_written = {}
        for file_entry in parsed.get("files_to_write", []):
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if path and content:
                _write_file(state.workspace_path, path, content)
                files_written[path] = content
                logger.info("    Wrote: %s", path)

        # Run any commands the agent requested (e.g., "python -m pytest tests/").
        # Skip server-start commands (like "python app.py") because the orchestrator
        # manages the Flask server lifecycle separately — running it here would block.
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

        # Update the agent's persistent memory with what it just did.
        # This ensures the next sprint has an accurate record of this agent's work.
        memory.files_written.update(files_written)
        work_summary = f"Sprint {state.current_sprint}: {task.get('name', 'unknown')} - wrote {list(files_written.keys())}"
        memory.work_log.append(work_summary)
        state.agent_memory[agent.name] = memory

        # Determine if the agent's work was successful based on command exit codes.
        # If pytest returned non-zero, the tests failed and the task is marked FAILED.
        # Tasks with no commands (e.g., frontend agent only writes files) default to success.
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
    # Internal: PM review between sprints — the adaptive feedback loop.
    # After each sprint (except the last), the PM agent examines what
    # passed and failed, and adjusts future sprint tasks accordingly.
    # This is what makes the system "agile" — the plan evolves with results.
    # ------------------------------------------------------------------

    def _pm_review_and_adjust(self, state: ProjectState, completed_sprint_index: int) -> None:
        """Have the PM agent review a completed sprint and adjust the remaining plan.

        The PM can take three actions:
        1. "unchanged" — everything went well, proceed as planned
        2. "modified_future_sprints" — update task descriptions in upcoming sprints
           (e.g., fix a broken endpoint path, add missing preservation instructions)
        3. "insert_sprint" — add a brand new sprint to handle critical issues
           (only allowed if total sprints < 10)
        """
        completed_sprint = state.sprint_plan["sprints"][completed_sprint_index]
        sprint_record = state.sprint_records[completed_sprint_index]

        # Build a summary of how each task in the completed sprint went (DONE/FAILED).
        # This gives the PM agent concrete data to evaluate the sprint's success.
        task_statuses = []
        for task in completed_sprint.get("tasks", []):
            tid = task.get("id", "")
            task_statuses.append({
                "id": tid,
                "name": task.get("name", ""),
                "description": task.get("description", ""),
                "status": sprint_record.task_results.get(tid, "UNKNOWN"),
            })

        # Build the full review context for the PM agent.
        # Includes: what sprint just completed, the full plan, the API contract,
        # and what each agent has built so far (files and recent work summaries).
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
            # Show the PM what each agent has built so far — file names and recent work.
            # This lets the PM reference exact file paths when updating future task descriptions.
            "agent_state": {
                name: {
                    "files": list(mem.files_written.keys()),
                    "recent_work": mem.work_log[-3:],
                }
                for name, mem in state.agent_memory.items()
            },
        }

        # Send the review context to the PM agent and parse its response.
        raw_output = self.pm_agent.review_mode(review_context)
        review = _parse_json(raw_output)

        if not review:
            logger.warning("PM review returned invalid JSON, skipping adjustments")
            return

        # Process the PM's decision.
        action = review.get("action", "unchanged")

        # ACTION: "modified_future_sprints" — PM updated task descriptions for upcoming sprints.
        # We apply these changes to the plan, but ONLY for future sprints (never rewrite history).
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

        # ACTION: "insert_sprint" — PM wants to add a new sprint to fix critical issues.
        # Only allowed if we haven't hit the 7-sprint maximum (5 planned + 2 flexibility).
        elif action == "insert_sprint" and state.total_sprints < 7:
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

        # Guard: reject sprint insertion if we're already at the maximum.
        elif action == "insert_sprint" and state.total_sprints >= 7:
            logger.warning("PM requested insert_sprint but already at max 7 sprints, ignoring")

        # Write updated plan to disk.
        _write_file(state.workspace_path, "scrum_plan.json",
                     json.dumps(state.sprint_plan, indent=2))

    # ------------------------------------------------------------------
    # Internal: JIRA operations — creates sprints and tasks on the JIRA board.
    # This keeps the real JIRA board in sync with the automated SCRUM cycle
    # so stakeholders can see progress in their project management tool.
    # ------------------------------------------------------------------

    def _create_jira_sprint(self, state: ProjectState, sprint_index: int,
                            sprint_data: Dict[str, Any]) -> None:
        """Create a JIRA sprint with its 3 tasks (backend, frontend, QA).

        Steps:
        1. Create individual JIRA task tickets for each of the 3 tasks
        2. Create a JIRA sprint and add all 3 tasks to it
        3. Map the internal plan task IDs to JIRA task IDs for future updates
        If JIRA creation fails, we log the error but continue — JIRA is nice-to-have,
        not a blocker for the actual sprint execution.
        """
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
    # Convenience: run the full pipeline end-to-end in one call.
    # This is the main entry point most users will use.
    # ------------------------------------------------------------------

    def run_full_pipeline(self, project_id: str, clarified_story: str) -> Dict[str, Any]:
        """One-shot: start project -> plan -> execute all sprints -> launch site.

        This method chains together all the steps:
        1. start_project() — create workspace and venv
        2. run_planning() — PM creates the sprint plan
        3. run_all_sprints() — execute every sprint with all agents
        4. launch_site() — start the Flask server for the user to browse

        Returns a dict with the project ID, workspace path, plan, and sprint results.
        """
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
    # End-of-SCRUM: launch the completed site on localhost for the user.
    # After all sprints are done, this starts the Flask server so the user
    # can open http://localhost:5000 and see their finished website.
    # ------------------------------------------------------------------

    def launch_site(self, project_id: str) -> Optional[subprocess.Popen]:
        """Start the completed site on localhost:5000 for the user to browse.

        Called automatically at the end of run_full_pipeline(). Can also be
        called standalone after run_all_sprints(). The Flask process runs in
        the background and stays alive until stop_site() is called or the
        orchestrator is garbage-collected.
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