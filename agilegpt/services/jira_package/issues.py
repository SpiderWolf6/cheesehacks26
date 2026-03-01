from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
	from .client import JiraClient, JiraClientError
except ImportError:
	from client import JiraClient, JiraClientError


def _adf_to_text(node: Any) -> str:
	if node is None:
		return ""
	if isinstance(node, dict):
		if node.get("type") == "text":
			return node.get("text", "")
		return "".join(_adf_to_text(child) for child in node.get("content", []))
	if isinstance(node, list):
		return "".join(_adf_to_text(child) for child in node)
	return ""


@dataclass
class JiraTask:
	id: str
	title: str
	description: str
	status: str
	role: str


def _extract_role(description: str) -> tuple[str, str]:
	normalized_description = description.lstrip()
	role_map = {
		"FE": "frontend",
		"BE": "backend",
		"QA": "tester",
	}

	for prefix, role in role_map.items():
		prefix_with_colon = f"{prefix}:"
		if normalized_description.upper().startswith(prefix_with_colon):
			cleaned_description = normalized_description[len(prefix_with_colon):].strip()
			return role, cleaned_description

	return "", description.strip()


def _role_prefix(role: str) -> str:
	role_value = (role or "").strip().lower()
	if role_value == "frontend":
		return "FE"
	if role_value == "backend":
		return "BE"
	if role_value == "tester":
		return "QA"
	return ""


def _text_to_adf(text: str) -> Dict[str, Any]:
	return {
		"type": "doc",
		"version": 1,
		"content": [
			{
				"type": "paragraph",
				"content": [
					{
						"type": "text",
						"text": text,
					}
				],
			}
		],
	}


def _clean_issue(issue: Dict[str, Any]) -> JiraTask:
	fields = issue.get("fields", {})
	status = fields.get("status") or {}

	description_value = fields.get("description")
	description_text = _adf_to_text(description_value).strip() if isinstance(description_value, (dict, list)) else (description_value or "")
	role, cleaned_description = _extract_role(str(description_text or ""))

	return JiraTask(
		id=str(issue.get("id") or ""),
		title=str(fields.get("summary") or ""),
		description=cleaned_description,
		status=str(status.get("name") or ""),
		role=role,
	)


def _build_clean_response(payload: Dict[str, Any]) -> List[JiraTask]:
	issues = payload.get("issues", [])
	return [_clean_issue(issue) for issue in issues]


class Issues:
	def __init__(self, client: JiraClient):
		self.client = client
		self.last_bulk_error: Optional[Dict[str, Any]] = None
		self.last_update_error: Optional[Dict[str, Any]] = None

	def get_all(
		self,
		project_key: Optional[str] = None,
		jql: Optional[str] = None,
		task_ids: Optional[List[int]] = None,
		fields: str = "id,summary,description,status",
		max_results: int = 100,
	) -> List[JiraTask]:
		resolved_project_key = (project_key or self.client.project_key or "").strip()
		resolved_jql = jql or (f"project = {resolved_project_key}" if resolved_project_key else "")
		if task_ids:
			normalized_task_ids: List[int] = []
			for task_id in task_ids:
				if isinstance(task_id, bool):
					continue
				if isinstance(task_id, int) and task_id > 0:
					normalized_task_ids.append(task_id)
			if normalized_task_ids:
				serialized_ids = ",".join(str(task_id) for task_id in normalized_task_ids)
				id_filter = f"id in ({serialized_ids})"
				resolved_jql = f"({resolved_jql}) AND {id_filter}" if resolved_jql else id_filter
		if not resolved_jql:
			return []

		query = {
			"jql": resolved_jql,
			"fields": fields,
			"maxResults": max_results,
		}
		payload = self.client.request(
			"GET",
			"/rest/api/3/search/jql",
			params=query,
		)
		return _build_clean_response(payload)

	def create_bulk(
		self,
		tasks: List[JiraTask],
		project_key: Optional[str] = None,
		issue_type_name: str = "Task",
	) -> List[JiraTask]:
		self.last_bulk_error = None
		if not tasks:
			self.last_bulk_error = {"reason": "No tasks provided."}
			return []

		resolved_project_key = (project_key or self.client.project_key or "").strip()
		if not resolved_project_key:
			self.last_bulk_error = {"reason": "Missing project key. Set JIRA_PROJECT_KEY or pass project_key."}
			return []

		issue_updates: List[Dict[str, Any]] = []
		for task in tasks:
			prefix = _role_prefix(task.role)
			description_text = (task.description or "").strip()
			if prefix:
				description_text = f"{prefix}: {description_text}" if description_text else f"{prefix}:"

			issue_updates.append(
				{
					"fields": {
						"project": {"key": resolved_project_key},
						"issuetype": {"name": issue_type_name},
						"summary": task.title,
						"description": _text_to_adf(description_text),
					}
				}
			)

		try:
			payload = self.client.request(
				"POST",
				"/rest/api/3/issue/bulk",
				json_body={"issueUpdates": issue_updates},
			)
		except JiraClientError as error:
			self.last_bulk_error = {
				"reason": "Request failed.",
				"status_code": error.status_code,
				"response_text": error.response_text,
			}
			return []

		if not isinstance(payload, dict):
			self.last_bulk_error = {
				"reason": "Unexpected response type.",
				"payload_type": type(payload).__name__,
			}
			return []

		created_issues = payload.get("issues") or []
		errors = payload.get("errors") or []
		if errors or len(created_issues) != len(tasks):
			self.last_bulk_error = {
				"reason": "Bulk create returned errors or partial success.",
				"errors": errors,
				"created_count": len(created_issues),
				"requested_count": len(tasks),
				"response": payload,
			}
			return []

		updated_tasks: List[JiraTask] = []
		for original_task, created_issue in zip(tasks, created_issues):
			assigned_id = str(created_issue.get("id") or "")
			if not assigned_id:
				self.last_bulk_error = {
					"reason": "Bulk create response missing issue id.",
					"created_issue": created_issue,
				}
				return []
			updated_tasks.append(
				JiraTask(
					id=assigned_id,
					title=original_task.title,
					description=original_task.description,
					status=original_task.status,
					role=original_task.role,
				)
			)

		return updated_tasks

	def update(self, task_id: str, update_text: str) -> Optional[JiraTask]:
		self.last_update_error = None
		resolved_task_id = (task_id or "").strip()
		if not resolved_task_id:
			self.last_update_error = {"reason": "Task id is required."}
			return None
		if not update_text or not update_text.strip():
			self.last_update_error = {"reason": "update_text is required."}
			return None

		try:
			resolved_task_id_int = int(resolved_task_id)
		except ValueError:
			self.last_update_error = {"reason": "Task id must be an integer.", "task_id": resolved_task_id}
			return None

		tasks = self.get_all(task_ids=[resolved_task_id_int], max_results=1)
		if not tasks:
			self.last_update_error = {"reason": "Task not found.", "task_id": resolved_task_id}
			return None
		task = tasks[0]

		updated_description = f"{(task.description or '').rstrip()}\n\nUPDATE: {update_text.strip()}"
		prefix = _role_prefix(task.role)
		if prefix:
			updated_description = f"{prefix}: {updated_description}"

		try:
			self.client.request(
				"PUT",
				f"/rest/api/3/issue/{resolved_task_id}",
				json_body={
					"fields": {
						"description": _text_to_adf(updated_description),
					}
				},
			)
		except JiraClientError as error:
			self.last_update_error = {
				"reason": "Failed to update description.",
				"status_code": error.status_code,
				"response_text": error.response_text,
			}
			return None

		try:
			transitions_payload = self.client.request(
				"GET",
				f"/rest/api/3/issue/{resolved_task_id}/transitions",
			)
		except JiraClientError as error:
			self.last_update_error = {
				"reason": "Failed to fetch transitions.",
				"status_code": error.status_code,
				"response_text": error.response_text,
			}
			return None

		if not isinstance(transitions_payload, dict):
			self.last_update_error = {
				"reason": "Unexpected transitions response type.",
				"payload_type": type(transitions_payload).__name__,
			}
			return None

		transitions = transitions_payload.get("transitions") or []
		done_transition_id = ""
		for transition in transitions:
			to_status = (transition.get("to") or {}).get("name")
			if isinstance(to_status, str) and to_status.strip().lower() == "done":
				done_transition_id = str(transition.get("id") or "")
				break

		if not done_transition_id:
			self.last_update_error = {
				"reason": "No transition to Done found.",
				"available_transitions": transitions,
			}
			return None

		try:
			self.client.request(
				"POST",
				f"/rest/api/3/issue/{resolved_task_id}/transitions",
				json_body={"transition": {"id": done_transition_id}},
			)
		except JiraClientError as error:
			self.last_update_error = {
				"reason": "Failed to transition issue to Done.",
				"status_code": error.status_code,
				"response_text": error.response_text,
			}
			return None

		return JiraTask(
			id=resolved_task_id,
			title=task.title,
			description=updated_description,
			status="Done",
			role=task.role,
		)


__all__ = ["JiraTask", "Issues"]