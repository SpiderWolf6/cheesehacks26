# Services

## jira_package
Python package for Jira Cloud REST (`/rest/api/3`) and Agile (`/rest/agile/1.0`) operations.

### Environment variables
All of the following must be present in your `.env`:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_KEY`
- `JIRA_PROJECT_KEY`
- `JIRA_BOARD_ID`

### `client.py`

- `JiraClient(...)`
  - Args: `timeout=30`, `load_env=True`, plus optional explicit overrides (`base_url`, `project_key`, `board_id`, `email`, `api_key`, `session`)
- `create_client_from_env(timeout=30)`
  - Output: `JiraClient`
- `delete_all_issues(project_key=None, progress_callback=None)`
  - Output: `{"projectKey", "totalFound", "deleted", "failed"}`
- `delete_all_sprints(board_id=None, progress_callback=None)`
  - Deletes only **future** sprints
  - Output: `{"boardId", "totalFound", "deleted", "failed"}`
- `delete_all_issues_and_sprints(project_key=None, board_id=None, progress_callback=None)`
  - Output: `{"issues": <issues_result>, "sprints": <sprints_result>}`

### `issues.py`

- `JiraTask`
  - Fields: `id`, `title`, `description`, `status`, `role`
- `Issues(client)`
- `get_all(project_key=None, jql=None, issue_ids=None, fields="id,summary,description,status", max_results=100)`
  - Output: `List[JiraTask]`
- `create_bulk(tasks, project_key=None, issue_type_name="Task")`
  - Output: `List[JiraTask]` with assigned IDs on success, else `[]`
  - Error details: `Issues.last_bulk_error`
- `update(task_id, update_text)`
  - Loads task via `get_all(issue_ids=[task_id])`, appends `UPDATE: ...` to description, transitions to `Done`
  - Output: updated `JiraTask` on success, else `None`
  - Error details: `Issues.last_update_error`

### `sprints.py`

- `Sprints(client)`
- `create_sprint(name, task_ids=None, origin_board_id=None, start_date=None, end_date=None)`
  - `start_date`/`end_date` default to now and +24h if omitted
  - Output: `int` sprint ID on success, else `None`
- `start_sprint(sprint_id)`
  - Full-update flow: loads sprint then updates state `future -> active`
  - Output: `True`/`False`
- `stop_sprint(sprint_id)`
  - Full-update flow: loads sprint then updates state `active -> closed`
  - Output: `True`/`False`

Failure details for sprint operations are stored in `Sprints.last_sprint_error`.
