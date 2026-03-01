import os
from typing import Any, Callable, Dict, List, Optional, Union

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

try:
	from .delete_ops import (
		delete_all_issues as _delete_all_issues,
		delete_all_issues_and_sprints as _delete_all_issues_and_sprints,
		delete_all_sprints as _delete_all_sprints,
	)
except ImportError:
	from delete_ops import (
		delete_all_issues as _delete_all_issues,
		delete_all_issues_and_sprints as _delete_all_issues_and_sprints,
		delete_all_sprints as _delete_all_sprints,
	)


class JiraClientError(Exception):
	def __init__(self, message: str, status_code: Optional[int] = None, response_text: str = ""):
		super().__init__(message)
		self.status_code = status_code
		self.response_text = response_text


class JiraClient:
	def __init__(
		self,
		base_url: Optional[str] = None,
		project_key: Optional[str] = None,
		board_id: Optional[int] = None,
		email: Optional[str] = None,
		api_key: Optional[str] = None,
		timeout: int = 30,
		load_env: bool = True,
		session: Optional[requests.Session] = None,
	):
		if load_env:
			load_dotenv()

		self.base_url = (base_url or os.getenv("JIRA_BASE_URL") or "").rstrip("/")
		self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY") or ""
		self.board_id = board_id if board_id is not None else os.getenv("JIRA_BOARD_ID")
		self.email = email or os.getenv("JIRA_EMAIL")
		self.api_key = api_key or os.getenv("JIRA_API_KEY")
		self.timeout = timeout

		if not self.base_url:
			raise JiraClientError("Missing Jira base URL. Set JIRA_BASE_URL or pass base_url.")
		if not self.email:
			raise JiraClientError("Missing Jira email. Set JIRA_EMAIL or pass email.")
		if not self.api_key:
			raise JiraClientError("Missing Jira API key. Set JIRA_API_KEY or pass api_key.")

		self.session = session or requests.Session()
		self.session.auth = HTTPBasicAuth(self.email, self.api_key)
		self.session.headers.update({"Accept": "application/json"})

	def request(
		self,
		method: str,
		path: str,
		*,
		params: Optional[Dict[str, Any]] = None,
		headers: Optional[Dict[str, str]] = None,
		json_body: Optional[Dict[str, Any]] = None,
		data: Optional[Any] = None,
	) -> Union[Dict[str, Any], List[Any], str]:
		url = f"{self.base_url}/{path.lstrip('/')}"
		merged_headers = dict(self.session.headers)
		if headers:
			merged_headers.update(headers)

		response = self.session.request(
			method=method.upper(),
			url=url,
			params=params,
			headers=merged_headers,
			json=json_body,
			data=data,
			timeout=self.timeout,
		)

		if response.status_code >= 400:
			raise JiraClientError(
				f"Jira request failed: {response.status_code}",
				status_code=response.status_code,
				response_text=response.text,
			)

		content_type = response.headers.get("Content-Type", "")
		if "application/json" in content_type:
			if not response.text or not response.text.strip():
				return {}
			try:
				return response.json()
			except ValueError:
				return {}
		return response.text

	def delete_all_issues(
		self,
		project_key: Optional[str] = None,
		progress_callback: Optional[Callable[[str], None]] = None,
	) -> Dict[str, Any]:
		return _delete_all_issues(
			client=self,
			project_key=project_key,
			progress_callback=progress_callback,
			error_cls=JiraClientError,
		)

	def delete_all_sprints(
		self,
		board_id: Optional[int] = None,
		progress_callback: Optional[Callable[[str], None]] = None,
	) -> Dict[str, Any]:
		return _delete_all_sprints(
			client=self,
			board_id=board_id,
			progress_callback=progress_callback,
			error_cls=JiraClientError,
		)

	def delete_all_issues_and_sprints(
		self,
		project_key: Optional[str] = None,
		board_id: Optional[int] = None,
		progress_callback: Optional[Callable[[str], None]] = None,
	) -> Dict[str, Any]:
		return _delete_all_issues_and_sprints(
			client=self,
			project_key=project_key,
			board_id=board_id,
			progress_callback=progress_callback,
			error_cls=JiraClientError,
		)

def create_client_from_env(timeout: int = 30) -> JiraClient:
	return JiraClient(timeout=timeout, load_env=True)


__all__ = [
	"JiraClient",
	"JiraClientError",
	"create_client_from_env",
]
