# Services

## jira_package
Python package for Jira Cloud REST (`/rest/api/3`) and Agile (`/rest/agile/1.0`) operations.

## How to use
Workflow for managing a sprint
- Ensure `.env` file is in jira_package directory.
- Create a client: `client.create_client_from_env`. Initialize `Issues` and `Sprints` objects from client.
- Create a group of three `JiraTask` objects (1 for each agent: frontend, backend, tester).
- Upload tasks in bulk: `Issues.create_bulk` - Returns list of JiraTask's with ids and statuses set.
- Create a sprint with the newly created tasks added: `Sprints.create_sprint` - Returns sprint id.
- Run sprint: `Sprints.start_sprint`.
- All three agents (frontend, backend, tester) will add their task results to their task description and get moved to status `Done` by calling `update`.
- Poll all three active tasks: `Issues.get_all` and filter for the three issue ids.
- When all three active tasks are status `Done`, call `Sprints.stop_sprint`.
- Repeat for sequential sprints until project is complete. 

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

```python
class JiraTask:
	id: str # Initialize as ""
	title: str 
	description: str
	status: str # Initialize as ""
	role: str # Either frontend, backend, or tester
```

- Class: `Issues(client: JiraClient)`
- `get_all(task_ids: [task_id: int], max_results=100)`
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


