"""PM Agent — the Product Manager / Scrum Master AI agent.

This agent acts as the project's PM. It does NOT write code. Instead, it:
1. PLANS the entire project: breaks down the user story into 7-10 sprints,
   each with exactly 3 tasks (backend, frontend, QA), and produces a
   detailed JSON sprint plan with API contracts.
2. REVIEWS completed sprints: after each sprint, the PM agent examines what
   passed and failed, and adjusts future sprint tasks to fix issues.
3. CONTROLS sprint execution: provides guardrails and scope management.
4. RUNS RETROSPECTIVES: captures lessons learned after sprint completion.

The PM agent's output is pure JSON — no code, no markdown. The orchestrator
parses this JSON to know what tasks to assign to which dev agents.

The system prompt below is the PM's "instruction manual." It's very long and
very strict because the PM's output structure must be exact — the orchestrator
and other agents parse it programmatically. Any drift in format breaks the pipeline.
"""

from __future__ import annotations

import json
from typing import Dict

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class PMAgent(BaseAgent):
    """The PM agent — orchestrates planning, reviews, and sprint adjustments.

    This class has four modes, each corresponding to a different phase of the
    SCRUM cycle. Each mode adds a "mode" tag to the context and calls the
    base run() method, which sends everything to the AI with the PM's system prompt.

    Modes:
    - planning_mode():        Produces the full sprint plan JSON at project start.
    - sprint_control_mode():  Monitors and guides active sprint execution.
    - review_mode():          Reviews completed sprint results and adjusts future tasks.
    - retrospective_mode():   Captures lessons learned for continuous improvement.
    """

    def __init__(self, llm_service: LLMService) -> None:
        # The PM system prompt is intentionally very strict and detailed.
        # It defines the exact JSON schema the PM must return, the rules for
        # sprint planning, task description format, shared contract structure,
        # and more. This strictness is essential because the orchestrator parses
        # the PM's output programmatically — any deviation breaks the pipeline.
        system_prompt = """
You are an elite Senior Product Manager and Scrum Master with 15+ years of experience shipping production software.
You operate in strict execution mode. You think like a real PM at a top-tier software company.

YOUR ROLE:
- Convert a product requirement into a realistic, ambitious multi-sprint execution plan.
- Produce exactly 5 sequential sprints. No fewer, no more.
  - The PM should always plan for 5 sprints regardless of project complexity.
  - Up to 2 additional sprints may be added later during review mode if critical issues arise (max 7 total), but the initial plan must be exactly 5.
- Each sprint must contain exactly 3 tasks: 1 backend, 1 frontend, 1 integration/QA.
- The integration/QA task MUST produce TWO test files each sprint:
  1. tests/test_api.py for backend API endpoint testing (Python pytest + requests).
  2. tests/test_frontend.py for frontend behavior validation (Python pytest + requests to fetch HTML and validate component structure, script tags, API fetch calls, and UI section presence).

YOUR PLANNING PHILOSOPHY:
- Think like a real engineering team. Sprint 1 is ALWAYS foundation/scaffolding.
- Sprint 1 backend: set up app.py with Flask app factory, CORS, health endpoint, and the first core API route.
- Sprint 1 frontend: set up the React project structure (index.html with React/ReactDOM CDN, App component, CSS reset, responsive layout shell, navigation skeleton, hero section).
- Sprint 1 integration: validate the health endpoint and first API route work end-to-end.
- Subsequent sprints build features from highest to lowest priority, one cohesive feature per sprint.
- Final sprint should focus on polish: animations, transitions, error states, loading states, final styling, and end-to-end smoke tests.
- With more sprints you MUST ensure EVERY planned subpage and feature is fully built, coded, and functional by the end. No page should be left as a skeleton or placeholder.
- Distribute work evenly across sprints. Do not front-load all features into early sprints and leave later sprints thin, or vice versa.

COMPLETENESS RULES (CRITICAL):
- Every frontend page, subpage, section, and component that appears in the navigation or is linked from anywhere MUST be fully built with real content and functionality by the final sprint. No dead links, no empty pages, no placeholder text.
- Every frontend form, button, or interactive element that submits data (donations, signups, contact forms, RSVPs, etc.) MUST have a corresponding backend API endpoint that accepts and PERSISTS the data.
- The backend MUST persist all user-submitted form data to CSV files in a data/ directory (e.g., data/donations.csv, data/members.csv, data/contacts.csv). Each CSV should have a header row and append new entries. In-memory-only storage is NOT acceptable for user submissions.
- For every POST endpoint that stores data, there MUST be a corresponding GET endpoint that retrieves the stored entries (e.g., POST /api/donations -> GET /api/donations).
- For every form that collects user data (donations, members, signups, contacts, etc.), plan a frontend display view that fetches the GET endpoint and shows the stored entries in a styled table or list. For example: a "Recent Donors" section on the donations page, a "Members Directory" on the members page, or a "Submissions" admin view. This gives users visible proof their data was saved and makes the app feel complete.
- Plan backend data persistence tasks BEFORE or in the SAME sprint as the frontend forms that POST to them. Never build a frontend form that submits to a nonexistent endpoint.
- The PM must verify in review mode that every frontend action has a working backend counterpart. If not, the next sprint MUST fix it.

AMBITION LEVEL:
- You are building something that should genuinely impress. Not a toy demo.
- Plan for a visually stunning, professionally designed, fully functional application.
- Include features that showcase modern web capabilities: smooth animations, responsive design, interactive elements, data visualization where relevant, polished micro-interactions.
- Think about what would make a hiring manager or investor say "wow, this is real."
- But stay realistic. Every task must be achievable by a single agent in one sprint.

TASK DESCRIPTION FORMAT (CRITICAL):
- First word MUST be: frontend OR backend OR integration (this is how the orchestrator routes tasks).
- No colons or dashes in descriptions.
- Each task description must be FULLY SELF-CONTAINED. The agent receiving it works BLIND with no knowledge of other tasks.
- Every task description MUST include ALL of the following inline:
  1. Exact file paths to create or modify
  2. Exact function/component names to implement
  3. For backend: exact Flask route decorators, HTTP methods, request JSON schema with field names and types, response JSON schema with field names and types, status codes
  4. For frontend: exact component names, which API endpoints to call (full path like /api/something), expected request/response shapes, UI layout description, styling requirements
  5. For integration: exact backend endpoints to test (HTTP methods, request payloads, expected status codes, response body structure) AND frontend behavior checks (which component script files should exist, which API fetch calls should be in the JavaScript, which section headings should appear in the UI)
  6. Explicit instruction to PRESERVE all existing code from prior sprints when modifying a file
  7. Reference to shared_contract endpoint IDs where applicable

CONTINUITY RULES:
- Every task that touches a file written in a previous sprint MUST say: "PRESERVE all existing code from previous sprints. ADD the following new code."
- Backend tasks must list every existing route that must remain untouched.
- Frontend tasks must list every existing component/section that must remain untouched.
- This is non-negotiable. Agents will overwrite files without this instruction.

TECHNICAL STACK:
- Backend: Python 3, Flask, flask-cors. Single app.py unless project needs modules. app.run(host="0.0.0.0", port=5000).
- Frontend: React 18 via CDN (ReactDOM, React, Babel standalone for JSX). No npm, no Node.js, no build tools. The frontend must work by opening index.html in a browser.
- Frontend styling: Modern CSS with CSS custom properties, flexbox, grid, animations, transitions. Aim for a polished, professional look. Think Stripe/Linear/Vercel level design quality.
- Integration: Python requests + pytest. Backend runs on http://localhost:5000.

ARCHITECTURE RULES:
- Backend MUST serve the React frontend as static files. This is MANDATORY in Sprint 1:
  - Flask must use send_from_directory to serve index.html at the root route /.
  - Flask must serve styles.css, src/ directory files, and all .js component files as static assets.
  - Use a catch-all route or explicit routes to serve the workspace directory files.
  - The Sprint 1 backend task description MUST include this static file serving requirement explicitly.
- All API routes must be prefixed with /api/.
- Backend must enable CORS for all origins.
- No database unless explicitly required. Use in-memory data structures or JSON files.
- No authentication unless explicitly required.

MULTI-FILE ARCHITECTURE (CRITICAL):
- Agents WILL overwrite files if everything lives in one file. You MUST plan a modular file structure.
- Backend: app.py is ONLY the Flask app factory and entry point. It imports route modules and registers Blueprints. Each feature gets a new Python file in routes/ (e.g., routes/health.py, routes/programs.py, routes/donations.py). Each route file defines a Flask Blueprint. Shared helpers go in utils/. Create routes/__init__.py as empty file.
- Sprint 1 backend task MUST include static file serving: app.py must use send_from_directory to serve index.html at /, styles.css, and all files under src/ (component JS files). This is REQUIRED for both the live site and QA frontend tests.
- Frontend: index.html is ONLY the HTML shell loading React CDN, styles.css, and component scripts. Each UI section is a separate .js file in src/components/ (e.g., src/components/HeroSection.js, src/components/DonationForm.js). Each component file sets window.ComponentName = function() {...}. index.html loads component scripts via <script type="text/babel" src="src/components/Name.js"></script> tags in order, then has a final <script type="text/babel"> block defining the App component referencing window.ComponentName.
- Sprint 1 MUST set up this modular structure for both backend and frontend.
- Subsequent sprint tasks create NEW files for new features with MINIMAL edits to app.py and index.html (one import/register line for backend, one script tag + one component reference for frontend).
- Task descriptions MUST specify which NEW files to create and what MINIMAL changes to make to existing files.

SHARED CONTRACT RULES:
- shared_contract is mandatory in planning output.
- All backend endpoints must be defined inside shared_contract.api_endpoints BEFORE any sprint references them.
- Sprint task descriptions must reference only endpoints defined in shared_contract.
- No new endpoints may appear outside shared_contract.
- shared_contract.version starts at 1.
- No duplicate method+path combinations with different schemas.

DEVELOPER HANDOFF RULES:
- Include a handoff_contract object at root with explicit agent contracts.
- handoff_contract must define backend_entrypoint, backend_functions, frontend_calls, integration_tests.
- backend_entrypoint: {file, start_command, port}.
- backend_functions entries: {file, function_name, endpoint_id, purpose}.
- frontend_calls entries: {file, method, path, request_keys, response_keys}.
- integration_tests entries: {file, method, path, expected_status}.
- All handoff_contract entries must map to shared_contract endpoint IDs.
- No endpoint dependency may appear in QA before backend implements it in an earlier or same sprint.
- Backend tasks must preserve all previously delivered endpoints.

SPRINT SEQUENCING RULES:
- Every sprint builds logically on previous sprints.
- Task execution order within a sprint is always: backend first, frontend second, integration third.
- No sprint may modify completed sprint tasks.
- Integration tests must only test endpoints that exist by that sprint.

MODE BEHAVIOR:
- planning mode: return a full sprint plan JSON.
- sprint_control mode: return control decisions and execution constraints.
- review mode: may only modify future sprints, never completed sprint tasks.
- review mode: may insert ONE new sprint (action "insert_sprint") if total sprint count is under 7 AND critical issues require it. Include the new sprint data in a "new_sprint" field with standard sprint schema (3 tasks).
- review mode: if any task has status FAILED, you MUST return action "modified_future_sprints" and update the corresponding task description in the next sprint to include the exact shared_contract endpoint path, request_schema keys, and success_status so the next execution succeeds.
- retrospective mode: return deterministic improvement actions.

OUTPUT FORMAT:
Return STRICT JSON only. No markdown. No commentary. No explanations.
Include a "requirements" array listing all pip packages needed (e.g. ["flask", "flask-cors", "requests", "pytest"]).

{
  "project_name": string,
  "requirements": [string],
  "handoff_contract": {
    "backend_entrypoint": {
      "file": string,
      "start_command": string,
      "port": integer
    },
    "backend_functions": [
      {
        "file": string,
        "function_name": string,
        "endpoint_id": string,
        "purpose": string
      }
    ],
    "frontend_calls": [
      {
        "file": string,
        "method": "GET" | "POST" | "PUT" | "DELETE",
        "path": string,
        "request_keys": [string],
        "response_keys": [string]
      }
    ],
    "integration_tests": [
      {
        "file": string,
        "method": "GET" | "POST" | "PUT" | "DELETE",
        "path": string,
        "expected_status": integer
      }
    ]
  },
  "shared_contract": {
    "version": 1,
    "api_endpoints": [
      {
        "id": string,
        "method": "GET" | "POST" | "PUT" | "DELETE",
        "path": string,
        "request_schema": object,
        "response_schema": object,
        "success_status": integer
      }
    ]
  },
  "sprints": [
    {
      "id": "uuid_v4_string",
      "name": "Sprint X",
      "goal": string,
      "tasks": [
        {
          "id": "uuid_v4_string",
          "name": string,
          "description": string,
          "status": "TODO"
        }
      ]
    }
  ]
}
""".strip()
        # Register this agent with its name, system prompt, and the AI model to use.
        # "azure_gpt41" refers to GPT-4.1 on Azure — a powerful model needed because
        # the PM must produce long, complex, structurally perfect JSON plans.
        super().__init__(
            name="pm_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="azure_gpt41",
        )

    # ------------------------------------------------------------------
    # Planning Mode — called once at project start to create the full sprint plan.
    # The PM receives the user story and produces a complete JSON plan with
    # 7-10 sprints, shared API contracts, and handoff contracts.
    # ------------------------------------------------------------------

    def planning_mode(self, context: Dict[str, object]) -> str:
        """Ask the PM AI to produce the full sprint plan JSON.

        Input: The clarified user story (what the client wants built).
        Output: A large JSON object containing:
          - project_name: Human-readable project name
          - shared_contract: Every API endpoint definition (method, path, schemas)
          - handoff_contract: Maps endpoints to files, functions, and tests
          - sprints: Array of 7-10 sprints, each with 3 tasks (backend, frontend, QA)
          - requirements: Python packages to install (flask, flask-cors, etc.)

        The output_contract in the context tells the PM exactly what structure
        we expect, acting as a schema validator embedded in the prompt.
        """
        planning_context = dict(context)
        planning_context["mode"] = "planning"
        planning_context["output_contract"] = {
            "root_fields": ["project_name", "handoff_contract", "shared_contract", "sprints"],
            "sprints_count": "exactly_5_mandatory",
            "tasks_per_sprint": 3,
            "task_fields": ["id", "name", "description", "status"],
            "task_id_format": "uuid_v4_string",
            "backend_stack": "python_flask_only",
            "backend_runtime": "localhost_5000",
            "shared_contract_required": True,
            "shared_contract_shape": {
                "required_fields": ["version", "api_endpoints"],
                "version": 1,
                "api_endpoint_fields": [
                    "id",
                    "method",
                    "path",
                    "request_schema",
                    "response_schema",
                    "success_status",
                ],
                "method_allowed": ["GET", "POST", "PUT", "DELETE"],
            },
            "description_prefix_allowed": ["frontend", "backend", "integration"],
            "required_task_sequence_per_sprint": ["backend", "frontend", "integration"],
            "description_rules": [
                "first word must be frontend or backend or integration",
                "no colons",
                "no dashes",
                "must include required files function names api routes method names inputs outputs integration expectations",
                "must reference only endpoints declared in shared_contract",
                "must include continuity instruction to preserve previous sprint outputs for touched files",
            ],
            "handoff_contract_required": True,
            "handoff_contract_shape": {
                "required_fields": ["backend_entrypoint", "backend_functions", "frontend_calls", "integration_tests"],
                "backend_entrypoint_required_fields": ["file", "start_command", "port"],
                "backend_functions_required_fields": ["file", "function_name", "endpoint_id", "purpose"],
                "frontend_calls_required_fields": ["file", "method", "path", "request_keys", "response_keys"],
                "integration_tests_required_fields": ["file", "method", "path", "expected_status"],
            },
            "status_value": "TODO",
            "response_format": "JSON only with no markdown or extra text",
        }
        return self.run(planning_context)

    # ------------------------------------------------------------------
    # Sprint Control Mode — provides real-time guidance during sprint execution.
    # ------------------------------------------------------------------

    def sprint_control_mode(self, context: Dict[str, object]) -> str:
        """Ask the PM AI to evaluate the current sprint's health and provide guidance.

        This mode monitors whether the sprint is on track, at risk, or blocked,
        and returns decisions about whether each task should continue, be replanned
        to the next sprint, or be blocked. It acts as a scope guardrail to prevent
        agents from drifting off-track during execution.
        """
        sprint_context = dict(context)
        sprint_context["mode"] = "sprint_control"
        sprint_context["control_contract"] = {
            "required_fields": [
                "sprint_id",
                "overall_status",
                "task_decisions",
                "scope_guardrails",
                "notes",
            ],
            "overall_status_allowed": ["on_track", "at_risk", "blocked"],
            "task_decisions_item_fields": ["task_id", "decision", "reason"],
            "task_decision_allowed": ["continue", "replan_next_sprint", "block"],
            "rules": [
                "do not modify completed sprint tasks",
                "do not add new sprint tasks during sprint execution",
                "only adjust sequencing and execution guidance",
            ],
            "response_format": "JSON only with no markdown or extra text",
        }
        return self.run(sprint_context)

    # ------------------------------------------------------------------
    # Review Mode — called AFTER each sprint completes (except the last).
    # The PM examines what passed and failed, and can modify future sprints
    # to fix issues or even insert a new sprint if critical problems need it.
    # This is the "adaptive" part of the SCRUM cycle — the plan evolves
    # based on actual results, not just the original plan.
    # ------------------------------------------------------------------

    def review_mode(self, context: Dict[str, object]) -> str:
        """Ask the PM AI to review a completed sprint and adjust the remaining plan.

        The orchestrator provides:
        - completed_sprint: Which sprint just finished, with pass/fail per task
        - full_plan: The current sprint plan JSON (so PM can see what's coming next)
        - shared_contract: The API contract (PM may update it if endpoints changed)
        - agent_state: What files each agent has written (so PM can reference exact paths)

        The PM returns one of three actions:
        - "unchanged": Everything is fine, proceed as planned.
        - "modified_future_sprints": Adjust task descriptions in upcoming sprints
          (e.g., fix a broken endpoint reference, add missing preservation instructions).
        - "insert_sprint": Add a brand new sprint to fix critical issues (max 10 total).
        """
        review_context = dict(context)
        review_context["mode"] = "review"
        review_context["review_contract"] = {
            "allowed_actions": ["unchanged", "modified_future_sprints", "insert_sprint"],
            "forbidden": ["modifying_completed_sprint_tasks", "adding_sprints_beyond_7_total"],
            "required_fields": ["action", "sprint_id", "note", "updated_plan"],
            "updated_plan_constraints": [
                "must remain valid sprint plan JSON matching the original schema exactly",
                "must preserve completed sprint task IDs and statuses",
                "future sprints must keep exactly 3 tasks each (backend, frontend, integration)",
                "task description first word must remain frontend backend or integration",
                "if contract drift occurred PM may modify future sprint tasks to fix inconsistencies",
                "if shared_contract changes version must increment",
                "PM may not modify completed sprint tasks",
                "may insert a sprint via insert_sprint action if total is under 5 and critical issues require it",
                "when remediating failed tasks ensure the updated description is FULLY SELF-CONTAINED with all file paths, function names, API routes, request/response schemas, and preservation instructions",
                "check agent_state.files to see exact file names each agent has written and reference those exact paths in updated task descriptions",
            ],
            "failed_task_remediation": [
                "if any task_statuses entry has status FAILED the PM MUST return action modified_future_sprints",
                "PM must update the description of the equivalent task in the NEXT sprint to include exact technical details that were missing",
                "the updated description must include the exact shared_contract endpoint path and request_schema key names and success_status",
                "check agent_state to see what files each agent has already written and ensure future tasks tell agents to PRESERVE those files and ADD to them",
                "if a backend task failed because of a missing import or wrong function name clarify the exact function signature in the next sprint task description",
                "if a QA task failed because it tested an endpoint that was not yet built move that test to a sprint after the endpoint is implemented",
                "prefer modifying existing future sprint task descriptions; only use insert_sprint for critical issues that cannot be addressed otherwise",
            ],
            "insert_sprint_rules": [
                "action insert_sprint is allowed ONLY if current total sprint count is less than 7",
                "include a 'new_sprint' object in the response following the standard sprint schema with id, name, goal, and exactly 3 tasks",
                "the orchestrator will insert it after the completed sprint and renumber all subsequent sprints",
                "use this ONLY for critical issues that cannot be fixed by modifying existing future tasks",
            ],
            "response_format": "JSON only with no markdown or extra text",
        }
        return self.run(review_context)

    # ------------------------------------------------------------------
    # Retrospective Mode — captures lessons learned after sprint completion.
    # This is the "continuous improvement" step in SCRUM methodology.
    # ------------------------------------------------------------------

    def retrospective_mode(self, context: Dict[str, object]) -> str:
        """Ask the PM AI to reflect on a completed sprint and identify improvements.

        Returns a structured retrospective with:
        - what_went_well: Things that worked and should be repeated
        - what_went_wrong: Issues that need fixing
        - action_items: Concrete steps assigned to specific agents for the next sprint
        - carry_forward_to_next_sprint: Unfinished work that needs to continue
        """
        retro_context = dict(context)
        retro_context["mode"] = "retrospective"
        retro_context["retrospective_contract"] = {
            "required_fields": [
                "sprint_id",
                "what_went_well",
                "what_went_wrong",
                "action_items",
                "carry_forward_to_next_sprint",
            ],
            "action_item_fields": ["owner", "action", "target_sprint"],
            "owner_allowed": ["pm", "frontend_agent", "backend_agent", "qa_agent"],
            "rules": [
                "no blame language",
                "focus on concrete execution improvements",
                "do not modify completed sprint tasks",
            ],
            "response_format": "JSON only with no markdown or extra text",
        }
        return self.run(retro_context)