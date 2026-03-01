from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
	from .client import JiraClient, JiraClientError
except ImportError:
	from client import JiraClient, JiraClientError


class Sprints:
	def __init__(self, client: JiraClient):
		self.client = client
		self.last_sprint_error: Optional[Dict[str, Any]] = None

	def _format_jira_datetime(self, value: datetime) -> str:
		return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")

	def _get_sprint(self, sprint_id: int) -> Optional[Dict[str, Any]]:
		try:
			payload = self.client.request(
				"GET",
				f"/rest/agile/1.0/sprint/{sprint_id}",
			)
		except JiraClientError as error:
			self.last_sprint_error = {
				"reason": "Failed to fetch sprint.",
				"status_code": error.status_code,
				"response_text": error.response_text,
				"sprint_id": sprint_id,
			}
			return None

		if not isinstance(payload, dict):
			self.last_sprint_error = {
				"reason": "Unexpected sprint response type.",
				"payload_type": type(payload).__name__,
				"sprint_id": sprint_id,
			}
			return None

		return payload

	def _build_sprint_update_payload(self, sprint: Dict[str, Any], state: str) -> Dict[str, Any]:
		now_utc = datetime.now(timezone.utc)
		payload: Dict[str, Any] = {
			"name": sprint.get("name"),
			"state": state,
		}

		start_date = sprint.get("startDate")
		end_date = sprint.get("endDate")

		if state == "active":
			payload["startDate"] = start_date or self._format_jira_datetime(now_utc)
			payload["endDate"] = end_date or self._format_jira_datetime(now_utc + timedelta(hours=24))
		else:
			if start_date is not None:
				payload["startDate"] = start_date
			if end_date is not None:
				payload["endDate"] = end_date

		if "goal" in sprint:
			payload["goal"] = sprint.get("goal")

		return payload

	def start_sprint(self, sprint_id: int) -> bool:
		self.last_sprint_error = None
		try:
			resolved_sprint_id = int(sprint_id)
		except (TypeError, ValueError):
			self.last_sprint_error = {
				"reason": "sprint_id must be an integer.",
				"sprint_id": sprint_id,
			}
			return False

		sprint = self._get_sprint(resolved_sprint_id)
		if not sprint:
			return False

		current_state = str(sprint.get("state") or "").strip().lower()
		if current_state != "future":
			self.last_sprint_error = {
				"reason": "Sprint can only be started from future state.",
				"sprint_id": resolved_sprint_id,
				"current_state": sprint.get("state"),
			}
			return False

		payload = self._build_sprint_update_payload(sprint, "active")

		try:
			self.client.request(
				"PUT",
				f"/rest/agile/1.0/sprint/{resolved_sprint_id}",
				json_body=payload,
			)
		except JiraClientError as error:
			self.last_sprint_error = {
				"reason": "Failed to start sprint.",
				"status_code": error.status_code,
				"response_text": error.response_text,
				"sprint_id": resolved_sprint_id,
			}
			return False

		return True

	def stop_sprint(self, sprint_id: int) -> bool:
		self.last_sprint_error = None
		try:
			resolved_sprint_id = int(sprint_id)
		except (TypeError, ValueError):
			self.last_sprint_error = {
				"reason": "sprint_id must be an integer.",
				"sprint_id": sprint_id,
			}
			return False

		sprint = self._get_sprint(resolved_sprint_id)
		if not sprint:
			return False

		current_state = str(sprint.get("state") or "").strip().lower()
		if current_state != "active":
			self.last_sprint_error = {
				"reason": "Sprint can only be stopped from active state.",
				"sprint_id": resolved_sprint_id,
				"current_state": sprint.get("state"),
			}
			return False

		payload = self._build_sprint_update_payload(sprint, "closed")

		try:
			self.client.request(
				"PUT",
				f"/rest/agile/1.0/sprint/{resolved_sprint_id}",
				json_body=payload,
			)
		except JiraClientError as error:
			self.last_sprint_error = {
				"reason": "Failed to stop sprint.",
				"status_code": error.status_code,
				"response_text": error.response_text,
				"sprint_id": resolved_sprint_id,
			}
			return False

		return True

	def create_sprint(
		self,
		name: str,
		task_ids: Optional[List[str]] = None,
		origin_board_id: Optional[int] = None,
		start_date: Optional[str] = None,
		end_date: Optional[str] = None,
	) -> Optional[int]:
		self.last_sprint_error = None

		resolved_name = (name or "").strip()
		if not resolved_name:
			self.last_sprint_error = {"reason": "Sprint name is required."}
			return None

		board_value = origin_board_id if origin_board_id is not None else self.client.board_id
		if board_value is None or str(board_value).strip() == "":
			self.last_sprint_error = {
				"reason": "origin_board_id is required. Pass origin_board_id or set JIRA_BOARD_ID.",
			}
			return None

		try:
			resolved_board_id = int(board_value)
		except (TypeError, ValueError):
			self.last_sprint_error = {
				"reason": "origin_board_id must be an integer.",
				"origin_board_id": board_value,
			}
			return None

		sprint_payload: Dict[str, Any] = {
			"name": resolved_name,
			"originBoardId": resolved_board_id,
		}
		now_utc = datetime.now(timezone.utc)
		resolved_start_date = start_date or self._format_jira_datetime(now_utc)
		resolved_end_date = end_date or self._format_jira_datetime(now_utc + timedelta(hours=24))
		sprint_payload["startDate"] = resolved_start_date
		sprint_payload["endDate"] = resolved_end_date

		try:
			created_sprint = self.client.request(
				"POST",
				"/rest/agile/1.0/sprint",
				json_body=sprint_payload,
			)
		except JiraClientError as error:
			self.last_sprint_error = {
				"reason": "Failed to create sprint.",
				"status_code": error.status_code,
				"response_text": error.response_text,
			}
			return None

		if not isinstance(created_sprint, dict):
			self.last_sprint_error = {
				"reason": "Unexpected create sprint response type.",
				"payload_type": type(created_sprint).__name__,
			}
			return None

		sprint_id_value = created_sprint.get("id")
		if sprint_id_value is None:
			self.last_sprint_error = {
				"reason": "Create sprint response missing id.",
				"response": created_sprint,
			}
			return None

		try:
			sprint_id = int(sprint_id_value)
		except (TypeError, ValueError):
			self.last_sprint_error = {
				"reason": "Create sprint response returned non-integer id.",
				"sprint_id": sprint_id_value,
			}
			return None

		normalized_issue_ids = [str(issue_id).strip() for issue_id in (task_ids or []) if str(issue_id).strip()]
		if not normalized_issue_ids:
			return sprint_id

		if len(normalized_issue_ids) > 50:
			self.last_sprint_error = {
				"reason": "At most 50 issues can be added to a sprint per request.",
				"issue_count": len(normalized_issue_ids),
				"sprint_id": sprint_id,
			}
			return None

		try:
			self.client.request(
				"POST",
				f"/rest/agile/1.0/sprint/{sprint_id}/issue",
				json_body={"issues": normalized_issue_ids},
			)
		except JiraClientError as error:
			self.last_sprint_error = {
				"reason": "Sprint created but failed to add issues to sprint.",
				"status_code": error.status_code,
				"response_text": error.response_text,
				"sprint_id": sprint_id,
			}
			return None

		return sprint_id


__all__ = ["Sprints"]