"""PM agent scaffold (Product Owner + Scrum Master responsibilities)."""

from __future__ import annotations

import json
from typing import Dict

from agents.base_agent import BaseAgent
from services.llm_service import LLMService


class PMAgent(BaseAgent):
    """Coordinates planning, sprint control, and retrospectives.

    This class is intentionally simple. Each mode only tags context with a mode
    and delegates to BaseAgent.run(). More detailed behavior will be added later.
    """

    def __init__(self, llm_service: LLMService) -> None:
        # PM prompt is intentionally strict to keep sprint orchestration deterministic.
        system_prompt = """
You are an elite Senior Product Manager and Scrum Master with 15+ years of experience shipping production software.
You operate in strict execution mode. You think like a real PM at a top-tier software company.

YOUR ROLE:
- Convert a product requirement into a realistic, ambitious multi-sprint execution plan.
- Produce between 3 and 5 sequential sprints. No fewer, no more.
  - Simple landing page or single-feature tool: 3 sprints.
  - Medium website with multiple pages and backend: 4 sprints.
  - Complex application with rich interactivity and multiple features: 5 sprints.
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
- review mode: may insert ONE new sprint (action "insert_sprint") if total sprint count is under 5 AND critical issues require it. Include the new sprint data in a "new_sprint" field with standard sprint schema (3 tasks).
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
        super().__init__(
            name="pm_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="azure_gpt41",
        )

    def planning_mode(self, context: Dict[str, object]) -> str:
        """Call PM LLM to produce strict sprint planning JSON."""
        planning_context = dict(context)
        planning_context["mode"] = "planning"
        planning_context["output_contract"] = {
            "root_fields": ["project_name", "handoff_contract", "shared_contract", "sprints"],
            "sprints_count": "3_to_5_mandatory",
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

    def sprint_control_mode(self, context: Dict[str, object]) -> str:
        """Sprint control mode.

        Conceptual responsibility:
        - monitor active sprint progress
        - enforce sprint boundaries and commitments
        - reduce scope churn during sprint execution
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

    def review_mode(self, context: Dict[str, object]) -> str:
        """Call PM LLM review mode to adjust future sprints if needed.

        The orchestrator passes:
        - completed_sprint: {sprint_number, name, task_statuses: [{id, name, description, status}]}
        - full_plan: the current sprint plan JSON
        - shared_contract: current contract
        - agent_state: {agent_name: {files: [...], recent_work: [...]}} showing what each agent built
        """
        review_context = dict(context)
        review_context["mode"] = "review"
        review_context["review_contract"] = {
            "allowed_actions": ["unchanged", "modified_future_sprints", "insert_sprint"],
            "forbidden": ["modifying_completed_sprint_tasks", "adding_sprints_beyond_5_total"],
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
                "action insert_sprint is allowed ONLY if current total sprint count is less than 5",
                "include a 'new_sprint' object in the response following the standard sprint schema with id, name, goal, and exactly 3 tasks",
                "the orchestrator will insert it after the completed sprint and renumber all subsequent sprints",
                "use this ONLY for critical issues that cannot be fixed by modifying existing future tasks",
            ],
            "response_format": "JSON only with no markdown or extra text",
        }
        return self.run(review_context)

    def retrospective_mode(self, context: Dict[str, object]) -> str:
        """Retrospective mode.

        Conceptual responsibility:
        - review outcomes after sprint completion
        - capture lessons learned
        - adapt backlog and priorities for the next sprint
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