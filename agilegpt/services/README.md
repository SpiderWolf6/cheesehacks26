# Services
### Jira Service
Jira is an Agile managing service that is used in this project for orchestrating agent interactions and tracking progress among agents. 

Files:
`jira_service.py` - Test program: Prints cleaned json containing all current sprint issues and relevant metadata for each. 

Sample Output for one issue:
```json
{
  "id": "10004",
  "key": "SCRUM-4",
  "type": "Task",
  "title": "TEST TASK",
  "description": "",
  "status": "To Do",
  "priority": "Medium",
  "assignee": "Evan Cedeno",
  "reporter": "Evan Cedeno",
  "created": "2026-02-28T15:33:02.358-0600",
  "updated": "2026-02-28T15:41:24.257-0600",
  "dueDate": null,
  "labels": [],
  "parent": {
    "key": "SCRUM-1",
    "title": "Understand the JIRA API",
    "type": "Epic"
  },
  "project": {
    "key": "SCRUM",
    "name": "AgentSpace"
  }
}
```
