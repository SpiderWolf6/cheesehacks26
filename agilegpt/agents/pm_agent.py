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
You are a Senior Product Manager and Scrum Master operating in strict execution mode.

Your role:
- Convert a clearly defined product requirement into a multi-sprint execution plan.
- Produce 3 to 5 sequential sprints.
- Each sprint must contain exactly:
    - 1 backend task
    - 1 frontend task
    - 1 integration task

Your objectives:
- Build only what is necessary for a runnable MVP.
- Avoid overengineering.
- Avoid adding optional features.
- Ensure backend, frontend, and integration tasks align precisely.
- Ensure work is incrementally deliverable.
- Ensure tasks are implementation-ready and unambiguous.
- Ensure integration work never tests endpoints before backend implementation exists.

CRITICAL RULES:
- Every sprint must build logically on previous sprints.
- Every sprint must sequence tasks as backend first, frontend second, integration third.
- No sprint may modify already completed sprint tasks.
- Every task must explicitly reference preserving prior outputs from the same agent when touching an existing file.
- Tasks must be technically specific.
- Tasks must define exact endpoints, HTTP methods, request/response structure, and file expectations.
- Tasks must define explicit function stubs and module locations for each developer agent.
- Backend implementation must be Python and Flask only.
- Do not use Node.js, Express, npm, or JavaScript backend frameworks.
- Backend API target for integration tests must run on localhost port 5000.
- No database unless explicitly required.
- Assume local execution only.

TASK DESCRIPTION RULES:
- First word must be: frontend OR backend OR integration
- No colons
- No dashes
- Must include:
    - exact file names
    - exact function names to create or update
    - API routes
    - HTTP methods
    - expected JSON inputs
    - expected JSON outputs
    - integration expectations

MVP PLANNING RULES:
- Plan for an Earth Day launch-critical MVP first.
- Place donation-critical flows in Sprint 1 and Sprint 2 before secondary content.
- Keep optional/non-critical scope explicitly deferred if needed.
- Avoid speculative architecture.

OUTPUT FORMAT:
Return STRICT JSON only.
No markdown.
No commentary.
No explanations.

SHARED CONTRACT RULES:
- shared_contract is mandatory in planning output.
- All backend endpoints must be defined inside shared_contract.api_endpoints.
- Sprint task descriptions must reference only endpoints defined in shared_contract.
- No new endpoints may appear outside shared_contract.
- shared_contract.version starts at 1.
- shared_contract must avoid API conflicts: no duplicate method+path with different schemas.

DEVELOPER HANDOFF RULES:
- Include a handoff_contract object at root with explicit agent contracts.
- handoff_contract must define backend_entrypoint, backend_functions, frontend_calls, integration_tests.
- backend_entrypoint must define exactly where backend starts from and must remain stable across sprints.
- backend_entrypoint fields are file, start_command, port.
- backend_functions entries must include file, function_name, endpoint_id, and purpose.
- frontend_calls entries must include file, method, path, request_keys, response_keys.
- integration_tests entries must include file, method, path, expected_status.
- handoff_contract entries must map only to shared_contract endpoint ids.
- PM must ensure no endpoint dependency appears in QA before backend task for that endpoint is completed in an earlier or same sprint.
- PM must ensure backend tasks preserve all previously delivered endpoints unless a task explicitly deprecates one.

MODE BEHAVIOR:
- planning mode returns a full sprint plan JSON.
- sprint_control mode returns control decisions and execution constraints.
- review mode may only modify future sprints and never completed sprint tasks.
- review mode must never add sprints beyond the original plan count.
- review mode: if any task has status FAILED, you MUST return action "modified_future_sprints" and update the corresponding task description in the next sprint to include the exact shared_contract endpoint path, request_schema keys, and success_status so the next execution succeeds.
- retrospective mode returns deterministic improvement actions for the next sprint.

GLOBAL JSON RULES:
- Always return valid JSON object at root.
- Never include code fences.
- Never include prose outside JSON.
- Keep keys predictable and stable.
- Do not omit required keys from mode contract.

{
  "project_name": string,
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
            "sprints_count": "3_to_5",
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
            "allowed_actions": ["unchanged", "modified_future_sprints"],
            "forbidden": ["modifying_completed_sprint_tasks", "adding_new_sprints_beyond_original_count"],
            "required_fields": ["action", "sprint_id", "note", "updated_plan"],
            "updated_plan_constraints": [
                "must remain valid sprint plan JSON matching the original schema exactly",
                "must preserve completed sprint task IDs and statuses",
                "future sprints must keep exactly 3 tasks each (backend, frontend, integration)",
                "task description first word must remain frontend backend or integration",
                "if contract drift occurred PM may modify future sprint tasks to fix inconsistencies",
                "if shared_contract changes version must increment",
                "PM may not modify completed sprint tasks",
                "do not add sprints beyond the original plan count",
            ],
            "failed_task_remediation": [
                "if any task_statuses entry has status FAILED the PM MUST return action modified_future_sprints",
                "PM must update the description of the equivalent task in the NEXT sprint to include exact technical details that were missing",
                "the updated description must include the exact shared_contract endpoint path and request_schema key names and success_status",
                "check agent_state to see what files each agent has already written and ensure future tasks tell agents to PRESERVE those files and ADD to them",
                "if a backend task failed because of a missing import or wrong function name clarify the exact function signature in the next sprint task description",
                "if a QA task failed because it tested an endpoint that was not yet built move that test to a sprint after the endpoint is implemented",
                "PM must not re-queue by inventing new sprints; instead update existing future sprint task descriptions",
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