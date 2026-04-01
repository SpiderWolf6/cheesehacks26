"""Main orchestrator engine for AgileGPT.

This is the BRAIN of the entire system. It coordinates the full automated SCRUM cycle:

WHAT IS SCRUM?
  SCRUM is a project management methodology where work is broken into "sprints"
  (short work cycles, typically 1-2 weeks in real life). Each sprint has specific
  tasks, and after each sprint the team reviews what worked and adjusts the plan.

HOW AGILEGPT AUTOMATES THIS:
  Instead of human developers, we have AI agents (LLM-powered bots) that play
  each role on the team. The orchestrator coordinates them like a conductor:

  1. PL (Project Lead) AGENT plans the project → produces a JSON sprint plan
  2. For each sprint:
     a. BACKEND AGENT writes Flask/Python API code
     b. FRONTEND AGENT writes React/HTML/CSS/JS UI code
     c. QA AGENT writes and runs tests against the live server
     d. PL AGENT reviews results and adjusts future sprints if needed
  3. After all sprints → launches the completed site on localhost:8001

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
  - PL Review: After each sprint, the Project Lead examines pass/fail results and
    can modify future sprint tasks or insert new sprints to fix issues.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from agents.backend_agent import BackendAgent
from agents.frontend_agent import FrontendAgent
from agents.pl_agent import PLAgent
from agents.qa_agent import QAAgent
from config import Config
from orchestrator.artifact_writer import (
    append_agent_log,
    append_proposal,
    read_interface_contract,
    read_project_state,
    read_proposals,
    read_specs_doc,
    run_state_update,
)
from orchestrator.context_builder import build_agent_context
from orchestrator.state import AgentMemory, ProjectState, SprintRecord
from services.jira_package.client import JiraClient, create_client_from_env
from services.jira_package.issues import Issues, JiraTask
from services.jira_package.sprints import Sprints
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


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


# ---- Hardcoded baseline packages ------------------------------------------------
# These are installed into every project venv at creation time.
# The PL does NOT control this list — it's fixed by the orchestrator.
# Covers: Flask backend, testing, HTTP requests, HTML parsing for QA tests.
BASELINE_PACKAGES = [
    "flask",
    "flask-cors",
    "requests",
    "pytest",
    "beautifulsoup4",
    "lxml",
]


def _setup_workspace(project_id: str, base_dir: str = "") -> str:
    """Create an isolated project workspace directory with its own Python virtual environment.

    Each project gets a completely separate folder (workspaces/<project_id>/) so that
    different projects don't interfere with each other. The venv ensures the project's
    Python dependencies (Flask, pytest, etc.) are installed in isolation.

    All required packages are installed immediately at venv creation time so that
    every subsequent step (backend, QA, etc.) can rely on them being present.
    """
    if not base_dir:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspaces")
    workspace = os.path.join(base_dir, project_id)
    os.makedirs(workspace, exist_ok=True)

    venv_path = os.path.join(workspace, ".venv")
    if not os.path.exists(venv_path):
        logger.info("Creating venv at %s", venv_path)
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)
        # Install all baseline packages immediately.
        _pip_install(workspace, BASELINE_PACKAGES)

    return workspace


def _is_valid_package_name(name: str) -> bool:
    """Check if a string looks like a valid pip package name (not prose/comments)."""
    # Valid package names: alphanumeric, hyphens, underscores, dots, version specs
    # e.g. "flask", "flask-cors", "requests>=2.0", "python-dateutil"
    import re as _re
    return bool(_re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*(\[.*\])?([<>=!~]+.*)?$', name))


def _pip_install(workspace: str, requirements: List[str]) -> None:
    """Install Python packages into the workspace's virtual environment.

    This runs 'pip install' using the venv's pip, not the system pip.
    Handles both Windows (Scripts/pip.exe) and Unix (bin/pip) paths.
    Filters out any non-package strings (prose, comments, markdown) that
    the architect LLM may have included in the requirements list.
    """
    if not requirements:
        return
    # Filter out stdlib modules (csv, typing, os, etc.) — the architect LLM
    # sometimes lists them alongside real pip packages.
    stdlib_names = getattr(sys, 'stdlib_module_names', set())
    # Filter to only valid package names that aren't stdlib — the architect
    # sometimes includes prose explanations or stdlib modules.
    clean_reqs = [
        r for r in requirements
        if _is_valid_package_name(r) and r.split(">=")[0].split("==")[0].split("[")[0] not in stdlib_names
    ]
    if not clean_reqs:
        logger.info("No valid packages to install (all filtered as prose)")
        return

    venv_path = os.path.join(workspace, ".venv")
    if os.name == "nt":
        pip_bin = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        pip_bin = os.path.join(venv_path, "bin", "pip")

    if not os.path.exists(pip_bin):
        logger.error("pip not found at %s — venv may be corrupt, recreating", pip_bin)
        import shutil
        shutil.rmtree(venv_path, ignore_errors=True)
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, capture_output=True)
        _pip_install(workspace, BASELINE_PACKAGES)
        # Now retry with the original requirements
        if os.path.exists(pip_bin):
            logger.info("Installing packages: %s", clean_reqs)
            result = subprocess.run([pip_bin, "install", *clean_reqs], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.error("pip install failed (rc=%d): %s", result.returncode, result.stderr[:500])
            else:
                logger.info("pip install succeeded")
        return

    logger.info("Installing packages: %s", clean_reqs)
    result = subprocess.run([pip_bin, "install", *clean_reqs], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("pip install failed (rc=%d): %s", result.returncode, result.stderr[:500])
    else:
        logger.info("pip install succeeded")


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


def _normalize_command(cmd: str) -> str:
    """Translate Unix-style commands to Windows equivalents when running on Windows."""
    if os.name != "nt":
        return cmd
    stripped = cmd.strip()
    # mkdir -p → os.makedirs equivalent via Python one-liner (always safe)
    if stripped.startswith("mkdir -p "):
        dirs = stripped[len("mkdir -p "):]
        return f'python -c "import os; os.makedirs(r\'{dirs}\', exist_ok=True)"'
    # rm -rf → rd /s /q (but prefer Python for safety)
    if stripped.startswith("rm -rf "):
        path = stripped[len("rm -rf "):]
        return f'python -c "import shutil, os; shutil.rmtree(r\'{path}\', ignore_errors=True)"'
    # touch → create empty file
    if stripped.startswith("touch "):
        path = stripped[len("touch "):]
        return f'python -c "open(r\'{path}\', \'a\').close()"'
    return cmd


def _run_command(workspace: str, cmd: str, timeout: int = 60) -> Dict[str, Any]:
    """Run a shell command inside the workspace using the workspace's virtual environment.

    This is how agent-requested commands (like 'pytest tests/') get executed.
    The command runs with the venv activated so it has access to installed packages.
    Returns a dict with returncode, stdout, and stderr for result tracking.
    Output is truncated to last 2000 chars to avoid memory issues with verbose output.
    """
    cmd = _normalize_command(cmd)
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


def _wait_for_backend(port: int = 8001, timeout: int = 8) -> bool:
    """Wait for a server to respond on the given port.

    Any HTTP response (even 404) means the server is up and ready.
    Only connection failures (server not started yet) cause retries.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
            return True
        except urllib.error.HTTPError:
            # Server responded with an error status (e.g. 404) — it's alive
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            # Server not up yet — retry
            time.sleep(0.5)
    return False

def _start_backend(workspace: str, port: int = 8001) -> tuple[Optional[subprocess.Popen], str]:
    """Start the Flask backend server in the workspace as a background process.

    Returns (proc, error_msg). If startup fails, proc is None and error_msg
    contains the crash details (stderr, traceback) so the orchestrator can
    inject it into QA results for the PL to see.
    """
    app_path = os.path.join(workspace, "app.py")
    if not os.path.exists(app_path):
        msg = "No app.py found in workspace, cannot start backend"
        logger.warning(msg)
        return None, msg

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
        if not _wait_for_backend(port=port):
            # Server didn't respond — check if process crashed.
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            else:
                # Process is alive but not responding — grab whatever stderr exists.
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            msg = f"Backend did not become ready within 8s.\nStderr:\n{stderr[-1500:]}"
            logger.error(msg)
            return None, msg

        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            msg = f"Backend exited immediately.\nStderr:\n{stderr[-1500:]}"
            logger.error(msg)
            return None, msg

        logger.info("Backend started (pid=%d)", proc.pid)
        return proc, ""
    except Exception as e:
        msg = f"Failed to start backend: {e}"
        logger.error(msg)
        return None, msg


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


def _setup_vite_project(workspace: str) -> None:
    """Scaffold a Vite + React project in workspace/frontend/ if not already present.

    Creates the frontend directory with:
    - package.json with react, react-dom, react-router-dom
    - vite.config.js with proxy to Flask on port 8001
    - src/main.jsx entry point
    - Runs npm install
    """
    frontend_dir = os.path.join(workspace, "frontend")
    if os.path.exists(os.path.join(frontend_dir, "package.json")):
        logger.info("Vite project already scaffolded, skipping")
        return

    os.makedirs(os.path.join(frontend_dir, "src", "pages"), exist_ok=True)
    os.makedirs(os.path.join(frontend_dir, "src", "components"), exist_ok=True)

    # package.json
    package_json = {
        "name": "frontend",
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "react-router-dom": "^6.28.0"
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.3.4",
            "vite": "^6.0.0"
        }
    }
    with open(os.path.join(frontend_dir, "package.json"), "w") as f:
        json.dump(package_json, f, indent=2)

    # vite.config.js — proxy /api to Flask
    vite_config = """\
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
"""
    with open(os.path.join(frontend_dir, "vite.config.js"), "w") as f:
        f.write(vite_config)

    # index.html (Vite entry point)
    index_html = """\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""
    with open(os.path.join(frontend_dir, "index.html"), "w") as f:
        f.write(index_html)

    # src/main.jsx
    main_jsx = """\
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""
    with open(os.path.join(frontend_dir, "src", "main.jsx"), "w") as f:
        f.write(main_jsx)

    # src/index.css (empty placeholder — frontend agent will populate)
    with open(os.path.join(frontend_dir, "src", "index.css"), "w") as f:
        f.write("/* Base styles — populated by frontend agent */\n")

    # src/App.jsx (minimal placeholder — frontend agent will overwrite in Sprint 1)
    app_jsx = """\
import './App.css'

export default function App() {
  return <div>Loading...</div>
}
"""
    with open(os.path.join(frontend_dir, "src", "App.jsx"), "w") as f:
        f.write(app_jsx)

    # src/App.css (empty)
    with open(os.path.join(frontend_dir, "src", "App.css"), "w") as f:
        f.write("/* App styles — populated by frontend agent */\n")

    # Run npm install
    logger.info("Installing frontend dependencies (npm install)...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=frontend_dir,
        capture_output=True, text=True, check=False,
        shell=(os.name == "nt"),
    )
    if result.returncode != 0:
        logger.error("npm install failed: %s", result.stderr[:500])
    else:
        logger.info("npm install succeeded")


def _start_frontend(workspace: str, port: int = 5173) -> tuple[Optional[subprocess.Popen], str]:
    """Start the Vite dev server for the React frontend.

    Returns (proc, error_msg). Similar to _start_backend.
    """
    frontend_dir = os.path.join(workspace, "frontend")
    if not os.path.exists(os.path.join(frontend_dir, "package.json")):
        msg = "No frontend/package.json found, cannot start frontend dev server"
        logger.warning(msg)
        return None, msg

    try:
        # Use npx vite to run the dev server
        proc = subprocess.Popen(
            ["npx", "vite", "--host"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=(os.name == "nt"),
        )
        # Wait for Vite to be ready
        if not _wait_for_backend(port=port, timeout=15):
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            msg = f"Frontend dev server did not become ready within 15s.\nStderr:\n{stderr[-1500:]}"
            logger.error(msg)
            return None, msg

        logger.info("Frontend dev server started (pid=%d) on port %d", proc.pid, port)
        return proc, ""
    except Exception as e:
        msg = f"Failed to start frontend dev server: {e}"
        logger.error(msg)
        return None, msg


def _stop_frontend(proc: Optional[subprocess.Popen]) -> None:
    """Stop the Vite dev server."""
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
    logger.info("Frontend dev server stopped")


def _retry_call(fn, label: str, max_retries: int = 5) -> Optional[str]:
    """Call fn() with exponential backoff retries. Returns the result or None."""
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt >= max_retries:
                logger.error("%s failed after %d attempts: %s", label, attempt, str(exc)[:200])
                return None
            wait = min(30 * (2 ** (attempt - 1)), 300)
            logger.warning("%s failed (attempt %d/%d): %s — retrying in %ds…",
                           label, attempt, max_retries, str(exc)[:120], wait)
            time.sleep(wait)
    return None


def _sanitize_test_file(content: str) -> str:
    """Remove server-launching code and bad imports from QA test files.

    The QA agent sometimes ignores prompt instructions and writes fixtures that
    start Flask/Vite servers, import project modules, or use subprocess.
    This strips those patterns and keeps only clean requests-based tests.
    """
    banned_imports = [
        "from flask import", "from app import", "import app",
        "from flask ", "import flask",
        "import subprocess", "from subprocess ",
        "import socket", "from socket ",
    ]
    lines = content.split("\n")
    cleaned = []
    in_fixture = False
    fixture_indent = 0

    for line in lines:
        stripped = line.strip()

        # Skip banned imports
        if any(stripped.startswith(bi) for bi in banned_imports):
            continue

        # Skip pytest fixtures (they're used to launch servers)
        if "@pytest.fixture" in stripped:
            in_fixture = True
            continue
        if in_fixture:
            if stripped.startswith("def "):
                fixture_indent = len(line) - len(line.lstrip())
                continue
            if stripped == "" or (len(line) - len(line.lstrip()) > fixture_indent and fixture_indent > 0):
                continue
            if stripped and (len(line) - len(line.lstrip()) <= fixture_indent or not line[0].isspace()):
                in_fixture = False
                # Fall through to process this line normally

        # Skip lines that use subprocess or pytest.exit
        if "subprocess.Popen" in stripped or "subprocess.run" in stripped:
            continue
        if "pytest.exit(" in stripped:
            continue

        # Remove fixture parameters from test functions (e.g., "def test_foo(flask_server):" → "def test_foo():")
        if stripped.startswith("def test_") and "(" in stripped:
            # Remove any fixture params but keep the function
            func_name = stripped.split("(")[0]
            line = line[:len(line) - len(line.lstrip())] + func_name + "():"

        # Replace fixture variable references with constants
        if "flask_server" in line:
            line = line.replace("flask_server", '"http://localhost:8001"')
        if "react_server" in line:
            line = line.replace("react_server", '"http://localhost:5173"')

        if not in_fixture:
            cleaned.append(line)

    result = "\n".join(cleaned)

    # Ensure the file has the required constants at the top
    if "API_BASE" not in result:
        header = 'import requests\nimport pytest\n\nAPI_BASE = "http://localhost:8001"\nFRONTEND_BASE = "http://localhost:5173"\n\n'
        # Remove any existing import lines and prepend clean header
        result = header + result

    return result


def _classify_task(description: str) -> str:
    """Determine which agent should handle a task based on its description.

    The PL agent is instructed to start every task description with exactly
    'backend', 'frontend', or 'integration'. This function reads that first
    word to route the task to the correct agent.

    Returns 'backend', 'frontend', 'qa', or 'unknown'.

    Falls back to keyword scanning if the PL's formatting drifted (e.g., if
    it said "Flask API" instead of starting with "backend").
    """
    first_word = description.strip().split()[0].lower().rstrip(":,;—-") if description.strip() else ""
    if first_word == "backend":
        return "backend"
    if first_word == "frontend":
        return "frontend"
    if first_word in ("integration", "qa", "test"):
        return "qa"
    # Fallback: scan the description for keywords in case PL formatting drifted.
    # Check integration/QA first — these descriptions often mention "backend" or
    # "frontend" as the thing being tested, which would mis-route them.
    desc_lower = description.lower()
    if "integration" in desc_lower or "pytest" in desc_lower or "test_all" in desc_lower or "validate" in desc_lower:
        return "qa"
    if "backend" in desc_lower or "flask" in desc_lower or "app.py" in desc_lower:
        return "backend"
    if "frontend" in desc_lower or "react" in desc_lower or ".jsx" in desc_lower or "vite" in desc_lower:
        return "frontend"
    if "test" in desc_lower:
        return "qa"
    return "unknown"


def _extract_referenced_paths(task_description: str) -> set[str]:
    """Extract file paths mentioned in a task description.

    Looks for patterns like routes/home.py, frontend/src/pages/About.jsx,
    tests/test_all.py, app.py, etc.
    """
    # Match common project file path patterns (including frontend/ prefix)
    pattern = r'(?:(?:frontend/src/(?:pages|components)|routes|tests|utils|data|docs|infra)/)?[\w\-]+\.(?:py|jsx|js|html|css|json|csv)'
    return set(re.findall(pattern, task_description))


def _filter_relevant_files(
    workspace_files: Dict[str, str],
    task_description: str,
    task_type: str,
) -> Dict[str, str]:
    """Filter workspace files to only those relevant to this agent and task.

    Strategy: start with anchor files every agent of this type needs,
    then add files explicitly referenced in the task description.
    This keeps context small in later sprints instead of growing linearly.
    """
    referenced = _extract_referenced_paths(task_description)

    # Anchor files every agent type always gets
    anchors: set[str] = set()
    if task_type == "backend":
        anchors = {"app.py"}
    elif task_type == "frontend":
        anchors = {"frontend/src/App.jsx", "frontend/src/App.css", "frontend/src/index.css"}
    elif task_type == "qa":
        anchors = {"app.py", "frontend/src/App.jsx"}

    # Type-based extension filter
    def _type_match(path: str) -> bool:
        if task_type == "backend":
            return path.endswith('.py') and not path.startswith('tests/') and not path.startswith('frontend/')
        if task_type == "frontend":
            return path.startswith('frontend/') and not path.startswith('frontend/node_modules/')
        if task_type == "qa":
            return (path.startswith('tests/')
                    or path.startswith('routes/')
                    or path.startswith('frontend/src/')
                    or path == 'app.py')
        return True

    result: Dict[str, str] = {}
    for path, content in workspace_files.items():
        if not _type_match(path):
            continue
        # Include if it's an anchor, referenced in task, or a new file from this sprint
        if path in anchors or path in referenced:
            result[path] = content

    # Fall back to all type-matched files when:
    # - Task references no specific files (Sprint 1 / generic descriptions)
    # - None of the referenced files exist in the workspace yet (new files being created)
    referenced_found = any(path in referenced for path in workspace_files)
    if not referenced or not referenced_found:
        for path, content in workspace_files.items():
            if _type_match(path):
                result[path] = content

    return result


def _jira_role(agent_type: str) -> str:
    """Map an agent type to the corresponding JIRA role label for ticket assignment."""
    return {"backend": "backend", "frontend": "frontend", "qa": "tester"}.get(agent_type, "")


# ---------------------------------------------------------------------------
# Orchestrator — the main coordinator class that runs the entire SCRUM cycle.
#
# Think of this as the "project manager's manager" — it tells the PL agent
# to plan, tells each dev agent to build their piece, checks results, and
# manages all the infrastructure (files, commands, JIRA) in between.
# ---------------------------------------------------------------------------

class Orchestrator:
    """Coordinates the full PL -> Agent SCRUM cycle.

    This is the main class you interact with. The typical usage is:
      orchestrator = Orchestrator()
      result = orchestrator.run_full_pipeline("my-project", "Build a donation website for...")

    That single call will:
    1. Create an isolated workspace with a Python venv
    2. Ask the PL agent to plan sprints (3-10 as PL deems appropriate)
    3. Execute each sprint (backend → frontend → QA agents)
    4. Have the PL review results after each sprint and adjust the plan
    5. Launch the completed site on http://localhost:8001

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
        self.pl_agent = PLAgent(self.llm_service)             # Project Lead: plans sprints and reviews results
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
        review process) that tells the PL agent what website to build.
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
    # 2. Planning phase — the PL agent creates the full sprint roadmap.
    # This happens ONCE at the start, producing the entire plan that
    # guides all subsequent sprint execution.
    # ------------------------------------------------------------------

    def run_planning(self, project_id: str) -> Dict[str, Any]:
        """Ask the Project Lead agent to create the full sprint plan.

        The PL agent receives the clarified user story and produces a
        comprehensive JSON plan containing:
        - 3-10 sprints with 3 tasks each (backend, frontend, integration)
        - A shared API contract defining every endpoint
        - A handoff contract mapping endpoints to files and tests

        After the PL returns the plan, this method:
        1. Parses the JSON and stores it in project state
        2. Writes scrum_plan.json and requirements.txt to the workspace
        3. Installs Python packages into the workspace venv
        4. Creates the first sprint on JIRA with its 3 tasks
        """
        state = self.active_projects[project_id]

        # Build planning context with specs and architecture from earlier FSM phases.
        # This gives the PL the full picture from PO and Architect agents.
        planning_context = {
            "project_id": state.project_id,
            "clarified_user_story": state.clarified_user_story,
            "current_sprint": 1,
            "sprint_status": "planning",
        }
        # Inject specs and architecture docs if available (from PO and Architect phases).
        if state.specs_doc:
            planning_context["specs_document"] = state.specs_doc
        if state.architecture_output:
            planning_context["architecture_document"] = state.architecture_output
        # Also read from artifact files if they exist on disk.
        if state.workspace_path:
            specs_file = read_specs_doc(state.workspace_path)
            if specs_file and not state.specs_doc:
                planning_context["specs_document"] = specs_file
            contract_file = read_interface_contract(state.workspace_path)
            if contract_file:
                planning_context["interface_contract"] = contract_file

        raw_output = self.pl_agent.plan(planning_context)
        logger.info("PL raw output length: %d chars", len(raw_output))
        logger.debug("PL raw output (first 2000):\n%s", raw_output[:2000])
        plan = _parse_json(raw_output)
        if not plan:
            logger.error("PL planning returned invalid JSON (raw length=%d):\n%s",
                         len(raw_output), raw_output[:1000])
            raise ValueError("PL planning did not return valid JSON. Raw output saved to state.")

        # Persist plan to state.
        state.sprint_plan = plan
        state.shared_contract = plan.get("shared_contract")
        state.handoff_contract = plan.get("handoff_contract")
        state.total_sprints = len(plan.get("sprints", []))
        logger.info("PL planned %d sprints — raw output was %d chars",
                    state.total_sprints, len(raw_output))

        # Write plan file to workspace.
        _write_file(state.workspace_path, "scrum_plan.json", json.dumps(plan, indent=2))
        _write_file(state.workspace_path, "pytest.ini", "[pytest]\ntestpaths = tests\n")
        # Write requirements.txt (hardcoded baseline — PL does NOT control packages).
        _write_file(state.workspace_path, "requirements.txt",
                     "\n".join(BASELINE_PACKAGES) + "\n")
        state.requirements_written = True
        # Packages were already installed in _setup_workspace, no need to install again.

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
    #   2. PL reviews results and may adjust future sprints
    #   3. Create the next sprint on JIRA
    #   4. Repeat until all sprints are done
    # ------------------------------------------------------------------

    def run_all_sprints(self, project_id: str) -> List[Dict[str, Any]]:
        """Execute all planned sprints sequentially. Returns results per sprint.

        Uses a while loop (not for-range) because the PL review step may INSERT
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

            # After the sprint completes, the PL reviews results and adjusts future tasks.
            # This is the "inspect and adapt" step in SCRUM — if something broke, the PL
            # can modify upcoming sprint tasks to fix it, or even insert a new sprint.
            # Skip this for the last sprint since there's nothing left to adjust.
            if sprint_idx < state.total_sprints - 1:
                self._pl_review_and_adjust(state, sprint_idx)
                # total_sprints may have changed if PL inserted a sprint during review.
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
        """Execute one sprint: assign each task to its agent, collect results, update JIRA.

        Backend and frontend tasks run in parallel (they write to disjoint file sets).
        QA runs after both complete, with the Flask server started beforehand.
        Workspace files are scanned once and cached for all agent calls in this sprint.
        """
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

        # Cache workspace files once for this sprint — all agent calls reuse it.
        state._cached_workspace_files = _scan_workspace_files(state.workspace_path)

        # Classify tasks into parallel groups: backend+frontend run concurrently,
        # then QA runs sequentially after both (needs the live server).
        parallel_tasks = []  # backend + frontend
        sequential_tasks = []  # qa/integration
        for task in tasks:
            task_type = _classify_task(task.get("description", ""))
            if task_type in ("backend", "frontend"):
                parallel_tasks.append((task, task_type))
            else:
                sequential_tasks.append((task, task_type))

        def _run_and_record(task: Dict, task_type: str) -> None:
            """Run a single agent task and record results into sprint_record."""
            task_id = task.get("id", "")
            task_name = task.get("name", "")
            logger.info("  Running %s task: %s", task_type, task_name)

            agent_result = self._run_agent_for_task(state, task, task_type)
            results["tasks"][task_id] = agent_result

            # Update JIRA task with result summary.
            jira_id = sprint_record.jira_task_ids.get(task_id)
            if jira_id:
                status_text = "DONE" if agent_result.get("success") else "FAILED"
                update_text = f"{status_text}: {agent_result.get('summary', 'No summary')}"
                self.jira_issues.update(jira_id, update_text)

            task_status = "DONE" if agent_result.get("success") else "FAILED"
            sprint_record.task_results[task_id] = task_status

            # Build detailed summary from agent output + command results
            summary_parts = [agent_result.get("summary", "")]
            for cr in agent_result.get("command_results", []):
                if cr.get("returncode") != 0:
                    summary_parts.append(
                        f"FAILED cmd: {cr.get('cmd', '')}\n"
                        f"stderr: {cr.get('stderr', '')[:300]}"
                    )
            task_summary = "\n".join(summary_parts)[:800]
            sprint_record.task_summaries[task_id] = task_summary

            # Stamp status + summary directly onto the task in the sprint plan
            # so PL review (and sprint_plan.md on disk) reflect what each agent did.
            task["status"] = task_status
            task["agent_summary"] = task_summary
            task["files_written"] = agent_result.get("files_written", [])

        # Run backend + frontend in parallel (they write disjoint files).
        if parallel_tasks:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(_run_and_record, task, ttype): task
                    for task, ttype in parallel_tasks
                }
                for future in as_completed(futures):
                    future.result()  # Raises if agent crashed

        # Re-scan workspace after parallel writes so QA sees fresh files.
        state._cached_workspace_files = _scan_workspace_files(state.workspace_path)

        # Run QA/integration tasks with both backend and frontend servers running.
        backend_proc = None
        frontend_proc = None
        server_error = ""
        if sequential_tasks:
            # Start backend (Flask on port 8001)
            backend_proc, server_error = _start_backend(state.workspace_path)
            if backend_proc is None:
                # Backend crashed — mark ALL QA tasks as FAILED
                for qtask, qtype in sequential_tasks:
                    tid = qtask["id"]
                    results["tasks"][tid] = {
                        "status": "FAILED",
                        "command_results": [{
                            "cmd": "start_backend",
                            "returncode": 1,
                            "stdout": "",
                            "stderr": server_error,
                        }],
                    }
                    sprint_record.task_results[tid] = "FAILED"
                    sprint_record.task_summaries[tid] = (
                        f"FAILED: Backend server crashed on startup.\n{server_error[:800]}"
                    )
                    qtask["status"] = "FAILED"
                    qtask["agent_summary"] = f"Backend crash: {server_error[:500]}"
            else:
                # Start frontend (Vite dev server on port 5173)
                frontend_proc, fe_error = _start_frontend(state.workspace_path)
                if frontend_proc is None:
                    logger.warning("Frontend dev server failed to start: %s", fe_error[:300])
                    # Not fatal — QA can still test API endpoints. Frontend tests will fail.

                # Run all QA tasks
                for task, task_type in sequential_tasks:
                    _run_and_record(task, task_type)

        # Stop both servers after all tasks complete.
        _stop_frontend(frontend_proc)
        _stop_backend(backend_proc)

        # Clean up cached files.
        state._cached_workspace_files = None

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

        # Use cached workspace scan if provided (avoids re-scanning for each agent
        # within the same sprint), otherwise scan fresh.
        workspace_files = getattr(state, '_cached_workspace_files', None)
        if workspace_files is None:
            workspace_files = _scan_workspace_files(state.workspace_path)

        # Filter to only task-relevant files (anchors + files referenced in task
        # description) instead of sending every file, which grows linearly.
        task_desc = task.get("description", "")
        relevant_files = _filter_relevant_files(workspace_files, task_desc, task_type)

        # Build context using the 6-file injection order from architecture.md:
        # 1. design_doc_{agent}.md  2. interface_contract.md  3. sprint_plan.md
        # 4. project_state.md  5. {agent}_log.md  6. task brief + existing files
        # Get current sprint data for the context builder
        sprint_data = {}
        if state.sprint_plan and state.sprint_plan.get("sprints"):
            sprint_idx = state.current_sprint - 1
            if 0 <= sprint_idx < len(state.sprint_plan["sprints"]):
                sprint_data = state.sprint_plan["sprints"][sprint_idx]

        architecture_context = build_agent_context(
            workspace_path=state.workspace_path,
            agent_name=agent.name,
            task_description=json.dumps(task, indent=2),
            sprint_data=sprint_data,
            shared_contract=state.shared_contract,
            agent_memory={
                "files_written": list(memory.files_written.keys()),
                "work_log": memory.work_log[-5:] if memory.work_log else [],
            } if memory else None,
        )

        context = {
            "project_id": state.project_id,
            "current_sprint": state.current_sprint,
            "total_sprints": state.total_sprints,
            "task": task,
            # Architecture context already contains the interface contract,
            # sprint status, project state, and agent log — no need to
            # duplicate shared_contract or previous_work at the top level.
            "architecture_context": architecture_context,
            "project_state_summary": {
                "current_files": relevant_files,
                "workspace_file_listing": sorted(workspace_files.keys()),
            },
        }

        # Send the context to the AI agent and get its response (with retries).
        raw_output = _retry_call(lambda: agent.run(context), label=agent.name)
        if raw_output is None:
            return {"success": False, "summary": f"Agent {agent.name} failed after retries"}

        # Parse the AI's response from raw text into a Python dict.
        # If the AI returned malformed JSON, we log the error and report failure.
        parsed = _parse_json(raw_output)
        if not parsed:
            logger.error("Agent %s returned invalid JSON:\n%s", agent.name, raw_output[:500])
            return {"success": False, "summary": "Agent returned invalid JSON", "raw": raw_output[:500]}

        # Write every file the agent produced to the workspace on disk.
        # Supports both new format ("files") and legacy format ("files_to_write").
        files_written = {}
        file_entries = parsed.get("files", parsed.get("files_to_write", []))
        for file_entry in file_entries:
            path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if path and content:
                # Guardrail: sanitize QA test files that try to launch servers
                # or import project modules despite the prompt forbidding it.
                if agent.name == "qa_agent" and path == "tests/test_all.py":
                    content = _sanitize_test_file(content)
                _write_file(state.workspace_path, path, content)
                files_written[path] = content
                logger.info("    Wrote: %s", path)

        # Run any commands the agent requested (e.g., "python -m pytest tests/").
        # Skip server-start commands (like "python app.py") because the orchestrator
        # manages the Flask server lifecycle separately — running it here would block.
        server_patterns = ["python app.py", "flask run", "python -m flask", "uvicorn", "gunicorn"]
        skip_patterns = ["pip install", "npm install", "npm run"]  # never let agents install packages
        cmd_results = []
        for cmd in parsed.get("commands_to_run", []):
            cmd_stripped = cmd.strip()
            if not cmd_stripped:
                continue
            if any(pat in cmd_stripped.lower() for pat in server_patterns):
                logger.info("    Skipping server-start command: %s", cmd_stripped)
                continue
            if any(pat in cmd_stripped.lower() for pat in skip_patterns):
                logger.info("    Skipping install command: %s", cmd_stripped)
                continue
            logger.info("    Running: %s", cmd_stripped)
            result = _run_command(state.workspace_path, cmd_stripped)
            cmd_results.append({"cmd": cmd_stripped, **result})

        # Safeguard: if this is the QA agent and it wrote tests/test_all.py but
        # didn't include a pytest command, force-run pytest anyway.
        if agent.name == "qa_agent" and "tests/test_all.py" in files_written:
            has_pytest_run = any("pytest" in cr.get("cmd", "") and "install" not in cr.get("cmd", "") for cr in cmd_results)
            if not has_pytest_run:
                logger.info("    QA wrote test file but no pytest command — force-running pytest")
                pytest_result = _run_command(state.workspace_path, "python -m pytest tests/test_all.py -v --tb=short")
                cmd_results.append({"cmd": "python -m pytest tests/test_all.py -v --tb=short", **pytest_result})
        elif agent.name == "qa_agent":
            logger.info("    QA agent did not write tests/test_all.py (files_written keys: %s)", list(files_written.keys()))
        logger.info("    Agent %s finished — cmd_results count: %d, files_written: %s",
                     agent.name, len(cmd_results), list(files_written.keys()))

        # Write agent log artifact if log_update is present.
        log_update = parsed.get("log_update", "")
        if log_update and state.workspace_path:
            append_agent_log(state.workspace_path, agent.name, state.current_sprint, log_update)

        # Write state additions if present.
        state_additions = parsed.get("state_additions", [])
        if state_additions and state.workspace_path:
            run_state_update(state.workspace_path, state.current_sprint, state_additions)

        # Write proposals if present.
        proposals = parsed.get("proposals", [])
        if proposals and state.workspace_path:
            for prop in proposals:
                if isinstance(prop, dict):
                    append_proposal(
                        state.workspace_path,
                        sprint=state.current_sprint,
                        agent_name=agent.name,
                        proposal_type=prop.get("type", "DEVIATION"),
                        summary=prop.get("summary", ""),
                    )

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
            for cr in cmd_results:
                if cr.get("returncode") != 0:
                    logger.warning("Command failed: %s\nSTDOUT:\n%s\nSTDERR:\n%s",
                                   cr.get("cmd", ""), cr.get("stdout", "")[:1000], cr.get("stderr", "")[:1000])

        # Use sprint_update if available, fall back to legacy explanation field.
        summary = parsed.get("sprint_update", parsed.get("explanation", ""))

        return {
            "success": success,
            "summary": summary,
            "files_written": list(files_written.keys()),
            "command_results": cmd_results,
        }

    # ------------------------------------------------------------------
    # Internal: PL review between sprints — the adaptive feedback loop.
    # After each sprint (except the last), the PL agent examines what
    # passed and failed, and adjusts future sprint tasks accordingly.
    # This is what makes the system "agile" — the plan evolves with results.
    # ------------------------------------------------------------------

    def _pl_review_and_adjust(self, state: ProjectState, completed_sprint_index: int) -> None:
        """Have the Project Lead review a completed sprint and adjust the remaining plan.

        OPTIMIZATION: If all tasks in the sprint passed, skip the LLM call entirely.
        The PL almost always returns {"action": "unchanged"} when everything is green,
        so this saves a full gpt-4.1 round-trip per passing sprint.

        The PL can take three actions:
        1. "unchanged" — everything went well, proceed as planned
        2. "modified_future_sprints" — update task descriptions in upcoming sprints
           (e.g., fix a broken endpoint path, add missing preservation instructions)
        3. "insert_sprint" — add a brand new sprint to handle critical issues
           (only allowed if total sprints < 10)
        """
        completed_sprint = state.sprint_plan["sprints"][completed_sprint_index]
        sprint_record = state.sprint_records[completed_sprint_index]

        # Skip the LLM call entirely if every task in the sprint passed.
        all_passed = all(
            status == "DONE"
            for status in sprint_record.task_results.values()
        ) if sprint_record.task_results else False

        if all_passed:
            logger.info("All tasks DONE in Sprint %d — skipping PL review LLM call",
                        completed_sprint_index + 1)
            return

        # Build a summary of how each task in the completed sprint went (DONE/FAILED).
        # This gives the PL agent concrete data to evaluate the sprint's success.
        task_statuses = []
        for task in completed_sprint.get("tasks", []):
            tid = task.get("id", "")
            task_statuses.append({
                "id": tid,
                "name": task.get("name", ""),
                "description": task.get("description", ""),
                "status": task.get("status", sprint_record.task_results.get(tid, "UNKNOWN")),
                "agent_summary": task.get("agent_summary", ""),
                "files_written": task.get("files_written", []),
            })

        # Build the full review context for the PL agent.
        # Keep it focused — include the completed sprint results, remaining sprint names,
        # and the shared contract. Avoid sending the full plan to reduce prompt size.
        remaining_sprints = []
        for i in range(completed_sprint_index + 1, len(state.sprint_plan.get("sprints", []))):
            s = state.sprint_plan["sprints"][i]
            remaining_sprints.append({
                "sprint_number": i + 1,
                "name": s.get("name", ""),
                "goal": s.get("goal", ""),
            })

        review_context = {
            "project_id": state.project_id,
            "current_sprint": completed_sprint_index + 1,
            "sprint_status": "completed",
            "completed_sprint": {
                "sprint_number": completed_sprint_index + 1,
                "name": completed_sprint.get("name", ""),
                "task_statuses": task_statuses,
            },
            "remaining_sprints": remaining_sprints,
            "shared_contract": state.shared_contract,
            # Show the PL what each agent has built so far — file names and recent work.
            # This lets the PL reference exact file paths when updating future task descriptions.
            "agent_state": {
                name: {
                    "files": list(mem.files_written.keys()),
                    "recent_work": mem.work_log[-3:],
                }
                for name, mem in state.agent_memory.items()
            },
        }
        # Include proposals, project state, and QA log for informed review.
        if state.workspace_path:
            proposals = read_proposals(state.workspace_path)
            if proposals:
                review_context["proposals"] = proposals
            project_state_md = read_project_state(state.workspace_path)
            if project_state_md:
                review_context["project_state_registry"] = project_state_md
            # Include QA test log so PL can see actual test output
            sprint_num = completed_sprint_index + 1
            qa_log_path = os.path.join(state.workspace_path, "qa", f"qa_log_sprint_{sprint_num}.md")
            if os.path.exists(qa_log_path):
                with open(qa_log_path, "r", encoding="utf-8") as f:
                    qa_log = f.read()[:1500]  # Cap to avoid bloating context
                review_context["qa_test_output"] = qa_log

        # Send the review context to the PL agent and parse its response.
        raw_output = _retry_call(lambda: self.pl_agent.review(review_context), label="PL review")
        if raw_output is None:
            return  # Skip review rather than crash pipeline
        review = _parse_json(raw_output)

        if not review:
            logger.warning("PL review returned invalid JSON, skipping adjustments")
            return

        # Process the PL's decision.
        action = review.get("action", "unchanged")

        # ACTION: "modified_future_sprints" — PL updated task descriptions for upcoming sprints.
        # We apply these changes to the plan, but ONLY for future sprints (never rewrite history).
        if action == "modified_future_sprints" and "updated_plan" in review:
            updated_plan = review["updated_plan"]
            # Handle PL returning a list of sprints directly instead of a dict with "sprints" key.
            if isinstance(updated_plan, list):
                new_sprints = updated_plan
            else:
                new_sprints = updated_plan.get("sprints", [])
            for i in range(completed_sprint_index + 1, len(new_sprints)):
                if i < len(state.sprint_plan["sprints"]):
                    state.sprint_plan["sprints"][i] = new_sprints[i]

            # Update shared_contract if PL changed it.
            if isinstance(updated_plan, dict) and "shared_contract" in updated_plan:
                state.shared_contract = updated_plan["shared_contract"]
                state.sprint_plan["shared_contract"] = updated_plan["shared_contract"]

            logger.info("PL adjusted future sprints after Sprint %d", completed_sprint_index + 1)

        # ACTION: "insert_sprint" — PL wants to add a new sprint to fix critical issues.
        # Only allowed if we haven't hit the 10-sprint maximum.
        elif action == "insert_sprint" and state.total_sprints < 10:
            new_sprint = review.get("new_sprint")
            if new_sprint and isinstance(new_sprint, dict):
                insert_at = completed_sprint_index + 1
                state.sprint_plan["sprints"].insert(insert_at, new_sprint)
                state.total_sprints += 1
                # Renumber sprint names for consistency.
                for i, s in enumerate(state.sprint_plan["sprints"]):
                    s["name"] = f"Sprint {i + 1}"
                logger.info("PL inserted new sprint after Sprint %d (total now %d)",
                            completed_sprint_index + 1, state.total_sprints)
            else:
                logger.warning("PL requested insert_sprint but provided no valid new_sprint data")

        # Guard: reject sprint insertion if we're already at the maximum.
        elif action == "insert_sprint" and state.total_sprints >= 10:
            logger.warning("PL requested insert_sprint but already at max 10 sprints, ignoring")

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
        2. run_planning() — PL creates the sprint plan
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
    # can open http://localhost:8001 and see their finished website.
    # ------------------------------------------------------------------

    def launch_site(self, project_id: str) -> Optional[subprocess.Popen]:
        """Start the completed site — Flask API + Vite frontend.

        Called automatically at the end of run_full_pipeline(). Starts both
        the Flask backend (port 8001) and Vite dev server (port 5173).
        The Vite server proxies /api/* to Flask.
        """
        state = self.active_projects[project_id]
        workspace = state.workspace_path

        backend_proc, error_msg = _start_backend(workspace)
        if not backend_proc:
            logger.error("Could not launch site — no running backend. %s", error_msg)
            return None

        frontend_proc, fe_error = _start_frontend(workspace)
        if not frontend_proc:
            logger.warning("Frontend dev server failed to start: %s", fe_error[:300])
            # Fall back to API-only mode
            self._site_processes[project_id] = {"backend": backend_proc, "frontend": None}
            print("\n" + "=" * 60)
            print("  BACKEND API IS LIVE!")
            print("  API: http://localhost:8001")
            print("  Frontend failed to start — check logs")
            print("  Press Ctrl+C to stop the server")
            print("=" * 60 + "\n")
            return backend_proc

        self._site_processes[project_id] = {"backend": backend_proc, "frontend": frontend_proc}

        print("\n" + "=" * 60)
        print("  YOUR SITE IS LIVE!")
        print("  Open http://localhost:5173 in your browser")
        print("  API: http://localhost:8001")
        print("  Press Ctrl+C to stop the servers")
        print("=" * 60 + "\n")

        return backend_proc

    def stop_site(self, project_id: str) -> None:
        """Stop a previously launched site (both servers)."""
        procs = self._site_processes.pop(project_id, None)
        if isinstance(procs, dict):
            _stop_frontend(procs.get("frontend"))
            _stop_backend(procs.get("backend"))
        else:
            _stop_backend(procs)