from typing import Any, Callable, Dict, List, Optional, Type


def _delete_issues_by_jql(
	client: Any,
	jql: str,
	progress_callback: Optional[Callable[[str], None]] = None,
	delete_subtasks: bool = False,
	error_cls: Type[Exception] = Exception,
) -> Dict[str, Any]:
	deleted = 0
	failed: List[Dict[str, Any]] = []
	processed = 0
	batch_size = 50

	while True:
		payload = client.request(
			"GET",
			"/rest/api/3/search/jql",
			params={
				"jql": jql,
				"fields": "parent",
				"maxResults": batch_size,
				"startAt": 0,
			},
		)

		if not isinstance(payload, dict):
			break

		page_issues = payload.get("issues") or []
		if not page_issues:
			break

		if progress_callback:
			progress_callback(f"Fetched batch of {len(page_issues)} issues for deletion.")

		for issue in page_issues:
			issue_ref = str(issue.get("key") or issue.get("id") or "").strip()
			if not issue_ref:
				continue
			processed += 1
			try:
				delete_params = {"deleteSubtasks": "true"} if delete_subtasks else None
				client.request("DELETE", f"/rest/api/3/issue/{issue_ref}", params=delete_params)
				deleted += 1
			except error_cls as error:
				failed.append(
					{
						"issue": issue_ref,
						"status_code": getattr(error, "status_code", None),
						"response_text": getattr(error, "response_text", str(error)),
					}
				)
			if progress_callback and (processed % 10 == 0):
				progress_callback(f"Issues progress: processed={processed}, deleted={deleted}, failed={len(failed)}")

	return {
		"processed": processed,
		"deleted": deleted,
		"failed": failed,
	}


def _get_all_board_sprints(client: Any, board_id: int) -> List[Dict[str, Any]]:
	sprints: List[Dict[str, Any]] = []
	start_at = 0
	max_results = 50

	while True:
		payload = client.request(
			"GET",
			f"/rest/agile/1.0/board/{board_id}/sprint",
			params={
				"state": "future",
				"startAt": start_at,
				"maxResults": max_results,
			},
		)

		if not isinstance(payload, dict):
			break

		page_sprints = payload.get("values") or []
		if not page_sprints:
			break

		sprints.extend(page_sprints)
		start_at += len(page_sprints)

		if payload.get("isLast") is True:
			break

	return sprints


def delete_all_issues(
	client: Any,
	project_key: Optional[str] = None,
	progress_callback: Optional[Callable[[str], None]] = None,
	error_cls: Type[Exception] = Exception,
) -> Dict[str, Any]:
	resolved_project_key = (project_key or client.project_key or "").strip()
	if not resolved_project_key:
		raise error_cls("Missing project key. Set JIRA_PROJECT_KEY or pass project_key.")

	if progress_callback:
		progress_callback(f"Deleting all issues in project {resolved_project_key} with deleteSubtasks=true...")
	delete_result = _delete_issues_by_jql(
		client=client,
		jql=f"project = {resolved_project_key}",
		progress_callback=progress_callback,
		delete_subtasks=True,
		error_cls=error_cls,
	)

	deleted = int(delete_result["deleted"])
	failed = list(delete_result["failed"])
	total_processed = int(delete_result["processed"])

	return {
		"projectKey": resolved_project_key,
		"totalFound": total_processed,
		"deleted": deleted,
		"failed": failed,
	}


def delete_all_sprints(
	client: Any,
	board_id: Optional[int] = None,
	progress_callback: Optional[Callable[[str], None]] = None,
	error_cls: Type[Exception] = Exception,
) -> Dict[str, Any]:
	board_value = board_id if board_id is not None else client.board_id
	if board_value is None or str(board_value).strip() == "":
		raise error_cls("Missing board id. Set JIRA_BOARD_ID or pass board_id.")

	try:
		resolved_board_id = int(board_value)
	except (TypeError, ValueError) as error:
		raise error_cls("Board id must be an integer.") from error

	sprints = _get_all_board_sprints(client, resolved_board_id)
	if progress_callback:
		progress_callback(f"Found {len(sprints)} future sprints on board {resolved_board_id}.")
	deleted = 0
	failed: List[Dict[str, Any]] = []
	total = len(sprints)

	for index, sprint in enumerate(sprints, start=1):
		sprint_id = sprint.get("id")
		if sprint_id is None:
			continue
		try:
			client.request("DELETE", f"/rest/agile/1.0/sprint/{int(sprint_id)}")
			deleted += 1
			if progress_callback and (index % 10 == 0 or index == total):
				progress_callback(f"Sprints progress: {index}/{total} processed, {deleted} deleted.")
		except error_cls as error:
			failed.append(
				{
					"sprintId": sprint_id,
					"state": sprint.get("state"),
					"status_code": getattr(error, "status_code", None),
					"response_text": getattr(error, "response_text", str(error)),
				}
			)
			if progress_callback:
				progress_callback(f"Sprint delete failed for {sprint_id}.")

	return {
		"boardId": resolved_board_id,
		"totalFound": len(sprints),
		"deleted": deleted,
		"failed": failed,
	}


def delete_all_issues_and_sprints(
	client: Any,
	project_key: Optional[str] = None,
	board_id: Optional[int] = None,
	progress_callback: Optional[Callable[[str], None]] = None,
	error_cls: Type[Exception] = Exception,
) -> Dict[str, Any]:
	issues_result = delete_all_issues(
		client=client,
		project_key=project_key,
		progress_callback=progress_callback,
		error_cls=error_cls,
	)
	sprints_result = delete_all_sprints(
		client=client,
		board_id=board_id,
		progress_callback=progress_callback,
		error_cls=error_cls,
	)
	return {
		"issues": issues_result,
		"sprints": sprints_result,
	}
