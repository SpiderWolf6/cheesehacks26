# Services

## jira_package
Python package for Jira Cloud REST (`/rest/api/3`) and Agile (`/rest/agile/1.0`) operations.

### Environment variables
Used when constructor args are omitted:

- `JIRA_BASE_URL` (required unless `base_url` arg is provided)
- `JIRA_EMAIL` (required unless `email` arg is provided)
- `JIRA_API_KEY` (required unless `api_key` arg is provided)
- `JIRA_PROJECT_KEY` (optional fallback for issue/project-scoped methods)
- `JIRA_BOARD_ID` (optional fallback for sprint/board-scoped methods)

### `client.py`

- `JiraClient(...)`
  - Required (directly or via env): `base_url`, `email`, `api_key`
  - Optional: `project_key`, `board_id`, `timeout`, `session`
- `request(method, path, ..., params=None, headers=None, json_body=None, data=None)`
  - Output: `dict | list | str` (empty JSON body returns `{}`)
  - Raises: `JiraClientError` on HTTP `>= 400`
- `delete_all_issues(project_key=None, progress_callback=None)`
  - Uses `project_key` arg, otherwise `client.project_key` (`JIRA_PROJECT_KEY`)
  - Output: `{"projectKey", "totalFound", "deleted", "failed"}`
- `delete_all_sprints(board_id=None, progress_callback=None)`
  - Uses `board_id` arg, otherwise `client.board_id` (`JIRA_BOARD_ID`)
  - Deletes only **future** sprints
  - Output: `{"boardId", "totalFound", "deleted", "failed"}`
- `delete_all_issues_and_sprints(project_key=None, board_id=None, progress_callback=None)`
  - Output: `{"issues": <issues_result>, "sprints": <sprints_result>}`

### `issues.py`

- `JiraTask`
  - Fields: `id`, `title`, `description`, `status`, `role`
- `Issues(client)`
- `get_all(project_key=None, jql=None, issue_ids=None, fields="id,summary,description,status", max_results=100)`
  - `project_key` falls back to `client.project_key`
  - If `issue_ids` provided, adds ID filter to JQL
  - Output: `List[JiraTask]`
- `create_bulk(tasks, project_key=None, issue_type_name="Task")`
  - `project_key` falls back to `client.project_key`
  - Output: `List[JiraTask]` with assigned IDs on success, else `[]`
  - Error details: `Issues.last_bulk_error`
- `update(task_id, update_text)`
  - Loads task via `get_all(issue_ids=[task_id])`, appends `UPDATE: ...` to description, transitions to `Done`
  - Output: updated `JiraTask` on success, else `None`
  - Error details: `Issues.last_update_error`

### `sprints.py`

- `Sprints(client)`
- `create_sprint(name, task_ids=None, origin_board_id=None, start_date=None, end_date=None)`
  - `origin_board_id` falls back to `client.board_id` (`JIRA_BOARD_ID`)
  - `start_date`/`end_date` default to now and +24h if omitted
  - Output: `int` sprint ID on success, else `None`
- `start_sprint(sprint_id)`
  - Full-update flow: loads sprint then updates state `future -> active`
  - Output: `True`/`False`
- `stop_sprint(sprint_id)`
  - Full-update flow: loads sprint then updates state `active -> closed`
  - Output: `True`/`False`

Failure details for sprint operations are stored in `Sprints.last_sprint_error`.
