# Services

## jira_package
Python package for Jira Cloud REST (`/rest/api/3`) and Agile (`/rest/agile/1.0`) operations.

### Environment variables
All of the following must be present in your `.env`:

```
JIRA_BASE_URL="https://evan-cedeno.atlassian.net"
JIRA_EMAIL="escedeno8@gmail.com"
JIRA_API_KEY="<INSERT API KEY>"
JIRA_PROJECT_KEY="SCRUM"
JIRA_BOARD_ID="1"
```

### `client.py`

- Class: `JiraClient()`
  - Uses .env file variables as args
- `create_client_from_env(timeout=30)`
  - Output: `JiraClient`
- `delete_all_issues_and_sprints()`
  - Output: `{"issues": <issues_result>, "sprints": <sprints_result>}`

### `issues.py`

- Class Object: `JiraTask`
  - All task issues passed as args and as output with this api utilize `JiraTask` objects.
  - Fields: `id`, `title`, `description`, `status`, `role`
- Class: `Issues(client: JiraClient)`
- `get_all(max_results=100)`
  - Output: `List[JiraTask]`
- `create_bulk(tasks: [JiraTask])`
  - Output: `List[JiraTask]` with assigned IDs and statuses of `To Do` on success, else `[]`
- `update(task_id: int, update_text: str)`
  - Loads task via `get_all(issue_ids=[task_id: int])`, appends `UPDATE: ...` to description, transitions to `Done`
  - Output: updated `JiraTask` on success, else `None`

### `sprints.py`

- Class: `Sprints(client)`
- `create_sprint(name, task_ids=[task_id: int])`
  - Full-update flow: creates sprint then adds tasks to sprint
  - Output: `int` sprint ID on success, else `None`
- `start_sprint(sprint_id: int)`
  - Full-update flow: loads sprint then updates state `future -> active`
  - Output: `True`/`False`
- `stop_sprint(sprint_id: int)`
  - Full-update flow: loads sprint then updates state `active -> closed`
  - Output: `True`/`False`

