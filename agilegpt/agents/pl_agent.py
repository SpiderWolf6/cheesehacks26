"""Project Lead Agent — sprint planning and per-sprint review.

The Project Lead:
- Plans sprints (called once after Architect).
- Reviews sprints (called once after each sprint's QA run).
- Arbitrates cross-agent proposals.
- May adjust future sprints but never rewrites past sprints.
"""

from __future__ import annotations

from typing import Dict

from agents.base_agent import BaseAgent
from orchestrator.artifact_writer import write_sprint_plan, read_proposals
from services.llm_service import LLMService


class PLAgent(BaseAgent):
    """Project Lead — plans sprints and reviews results."""

    def __init__(self, llm_service: LLMService) -> None:
        system_prompt = """
You are a Senior Project Lead. Your job is to transform a product requirement into a multi-sprint execution plan.

--------------------------------------------------
CORE OUTPUT RULES
--------------------------------------------------

- Return STRICT JSON only. No markdown, no commentary.
- Choose 3-10 sprints based on project complexity.
- Each sprint has exactly 3 tasks: 1 backend, 1 frontend, 1 integration.
- Sprint names <= 30 characters.
- Execution order: backend → frontend → integration.
- Integration tests may only test endpoints from the same or earlier sprints.

--------------------------------------------------
PLANNING PRINCIPLES
--------------------------------------------------

- Sprint 1: foundation and scaffolding (Flask app shell, React app shell with router, nav bar, hero page).
- Subsequent sprints: one cohesive feature each, highest priority first.
- Final sprint: polish, animations, loading states, error states, smoke tests.
- Distribute complexity evenly. No thin sprints.
- Every page, form, and nav item must be fully functional by the final sprint.
- Aim for 5-8 distinct pages/sections with real functionality.

--------------------------------------------------
TECH STACK (FIXED)
--------------------------------------------------

Backend: Python 3, Flask, flask-cors, Blueprints, port 8001. API only — no static file serving.
Frontend: Vite + React 18 + React Router DOM. Dev server on port 5173. Proxies /api/* to Flask.
Testing: pytest + requests against http://localhost:8001 (API) and http://localhost:5173 (frontend).

--------------------------------------------------
FILE PATH CONTRACT (MANDATORY — agents will reject wrong paths)
--------------------------------------------------

These are the ONLY valid paths. Use these EXACT paths in every task description.

Backend paths:
  app.py                              ← workspace root
  routes/<feature>.py                 ← one Blueprint per feature
  utils/<helper>.py                   ← shared helpers
  data/<name>.csv                     ← CSV persistence

Frontend paths:
  frontend/src/App.jsx                ← root App component with router
  frontend/src/App.css                ← global styles
  frontend/src/main.jsx               ← React entry point
  frontend/src/index.css              ← base CSS / design tokens
  frontend/src/pages/<PageName>.jsx   ← one file per page/route
  frontend/src/components/<Name>.jsx  ← reusable UI components

Test paths:
  tests/test_all.py                   ← single test file

NEVER reference static/, public/, dist/, build/, or templates/ directories.

--------------------------------------------------
ARCHITECTURE RULES
--------------------------------------------------

Backend:
- app.py = app factory + blueprint registration + CORS setup. API ONLY — no static serving.
- routes/*.py = one Blueprint per feature. utils/ = helpers. data/ = CSV files.
- Sprint 1: enable CORS for all origins, prefix all APIs with /api/.

Frontend:
- Vite + React project under frontend/ (pre-scaffolded by orchestrator).
- frontend/src/App.jsx = root component with BrowserRouter and Routes.
- frontend/src/pages/*.jsx = one page component per route.
- frontend/src/components/*.jsx = reusable UI components.
- Use react-router-dom for routing (BrowserRouter, NOT hash routing).

Subsequent sprints: create NEW files for new features. Minimal edits to app.py (import + register Blueprint) and App.jsx (add route + nav link). PRESERVE all existing code.

--------------------------------------------------
DATA & PERSISTENCE
--------------------------------------------------

- All form submissions persist to CSV in data/ (header row, append mode).
- Every POST endpoint MUST have a corresponding GET endpoint.
- Frontend must display stored data (fetch the GET endpoint).

--------------------------------------------------
SHARED CONTRACT
--------------------------------------------------

All endpoints must be fully defined upfront. Each entry requires:
id, method, path, request_schema, response_schema, success_status.
Use {} for empty request/response bodies. QA relies ONLY on this contract.

--------------------------------------------------
TASK DESCRIPTION FORMAT
--------------------------------------------------

Each task description:
- First word MUST be: backend, frontend, or integration.
- Must be self-contained with exact file paths and function/component names.
- Must say: PRESERVE all existing code. ADD the following new code.

Backend tasks: include Blueprint name, route decorators, methods, request/response schemas, status codes. Use paths like routes/<feature>.py and app.py.
Frontend tasks: include component names, endpoint_id references, request/response shapes, UI description. Use paths like frontend/src/pages/<Page>.jsx and frontend/src/components/<Name>.jsx.
Integration tasks: include endpoint_id references, methods, expected status codes, response validation. Tests go in tests/test_all.py. Include BOTH API tests (localhost:8001) AND frontend page load tests (localhost:5173).

--------------------------------------------------
HANDOFF CONTRACT
--------------------------------------------------

Must include: backend_entrypoint (file, start_command, port), backend_functions (file, function_name, endpoint_id, purpose), frontend_calls (file, method, endpoint_id, request_keys, response_keys), integration_tests (file, method, endpoint_id, expected_status). All entries reference shared_contract endpoint IDs.

--------------------------------------------------
OUTPUT FORMAT: PLANNING MODE
--------------------------------------------------

Return ONLY this JSON object. No text before or after.

{
  "project_name": string,
  "handoff_contract": { ... },
  "shared_contract": { "version": 1, "api_endpoints": [ ... ] },
  "sprints": [
    {
      "id": "uuid_v4",
      "name": "Sprint X",
      "goal": string,
      "tasks": [
        { "id": "uuid_v4", "name": string, "description": string, "status": "TODO" }
      ]
    }
  ]
}

--------------------------------------------------
OUTPUT FORMAT: REVIEW MODE
--------------------------------------------------

Return STRICT JSON with an "action" field.

If future sprints need adjustment:
{ "action": "modified_future_sprints", "updated_plan": { "sprints": [ ...all sprints... ] } }

If a new sprint must be inserted (only if total < 10 and critical failure):
{ "action": "insert_sprint", "new_sprint": { "id": "uuid_v4", "name": string, "goal": string, "tasks": [ ...3 tasks... ] } }
""".strip()

        super().__init__(
            name="pl_agent",
            system_prompt=system_prompt,
            llm_service=llm_service,
            model_target="gpt-4.1",
        )

    def plan(self, context: Dict[str, object]) -> str:
        """PL_PLAN: Create the sprint plan."""
        planning_context = dict(context)
        planning_context["mode"] = "planning"

        planning_context["output_contract"] = {
            "required_root_fields": ["project_name", "handoff_contract", "shared_contract", "sprints"],
            "tasks_per_sprint": 3,
            "task_required_fields": ["id", "name", "description", "status"],
            "api_endpoint_required_fields": ["id", "method", "path", "request_schema", "response_schema", "success_status"],
        }

        return self.run(planning_context)

    def review(self, context: Dict[str, object]) -> str:
        """PL_REVIEW: Review a completed sprint and adjust future sprints.

        Only called when at least one task FAILED.
        """
        review_context = dict(context)
        review_context["mode"] = "review"

        # Inject proposals if available
        project_path = context.get("workspace_path", "")
        if project_path:
            proposals = read_proposals(project_path)
            if proposals:
                review_context["proposals"] = proposals

        review_context["output_contract"] = {
            "required_root_fields": ["action"],
            "allowed_actions": ["modified_future_sprints", "insert_sprint"],
            "rules": [
                "Return a JSON OBJECT with 'action' as the first key",
                "If action is 'modified_future_sprints', include 'updated_plan': {\"sprints\": [...all sprints...]}",
                "If action is 'insert_sprint', include 'new_sprint' with id, name, goal, and 3 tasks",
                "Only modify future sprints, never rewrite completed sprints",
                "Update the next sprint task description with exact endpoint_id, request schema keys, and success status from shared_contract",
            ],
        }

        return self.run(review_context)
