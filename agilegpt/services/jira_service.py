"""Minimal JIRA service abstraction.

This module provides a simple interface that higher-level agents can call.
Some methods are intentionally stubbed with TODOs while we finalize workflow.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from requests.auth import HTTPBasicAuth

from config import Config


class JiraService:
    """Small wrapper around JIRA REST APIs.

    JIRA usually exposes:
    - Core issue/project APIs under /rest/api/3
    - Agile sprint APIs under /rest/agile/1.0
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.base_url: str = config.JIRA_BASE_URL.rstrip("/")
        self.auth = HTTPBasicAuth(config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal helper to keep HTTP request logic in one place."""
        url = f"{self.base_url}{path}"
        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            auth=self.auth,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        if not response.text:
            return {}
        return response.json()

    def create_project(self, name: str, key: str) -> Dict[str, Any]:
        """Create a JIRA project.

        TODO: Confirm project template key and assignee settings for your org.
        """
        payload = {
            "key": key,
            "name": name,
            "projectTypeKey": "software",
            "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-scrum-template",
        }
        return self._request("POST", "/rest/api/3/project", payload)

    def create_epic(self, project_key: str, summary: str) -> Dict[str, Any]:
        """Create an Epic issue in JIRA.

        TODO: Your JIRA instance may use a custom field for Epic Name.
        """
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": "Epic"},
            }
        }
        return self._request("POST", "/rest/api/3/issue", payload)

    def create_story(self, project_key: str, summary: str, description: str) -> Dict[str, Any]:
        """Create a Story issue in JIRA."""
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Story"},
            }
        }
        return self._request("POST", "/rest/api/3/issue", payload)

    def create_sprint(self, project_key: str, sprint_name: str) -> Dict[str, Any]:
        """Create a sprint for a board associated with the project.

        TODO: Discover board ID for project_key in your JIRA instance.
        """
        # This is a placeholder board id for scaffold purposes.
        board_id = 1
        payload = {
            "name": sprint_name,
            "originBoardId": board_id,
        }
        return self._request("POST", "/rest/agile/1.0/sprint", payload)

    def add_issue_to_sprint(self, issue_key: str, sprint_id: int) -> Dict[str, Any]:
        """Add an existing issue to a sprint."""
        payload = {
            "issues": [issue_key],
        }
        return self._request("POST", f"/rest/agile/1.0/sprint/{sprint_id}/issue", payload)

    def transition_issue(self, issue_key: str, status: str) -> Dict[str, Any]:
        """Transition an issue to a target status.

        TODO: In real usage, fetch transitions first and map status -> transition id.
        """
        # Placeholder transition id. Real code should map this from JIRA transitions API.
        payload = {
            "transition": {"id": "31"},
            "update": {
                "comment": [
                    {
                        "add": {
                            "body": f"Transition requested to status: {status}",
                        }
                    }
                ]
            },
        }
        return self._request("POST", f"/rest/api/3/issue/{issue_key}/transitions", payload)
