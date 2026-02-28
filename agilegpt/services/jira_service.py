import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import json

load_dotenv()
JIRA_API_KEY = os.getenv("JIRA_API_KEY")

url = "https://evan-cedeno.atlassian.net/rest/api/3/search/jql"

auth = HTTPBasicAuth("escedeno8@gmail.com", JIRA_API_KEY)

headers = {
  "Accept": "application/json"
}

query = {
  'jql': 'project = AgentSpace',
  'fields': 'key,summary,description,issuetype,assignee,reporter,status,priority,created,updated,duedate,labels,parent,project',
  'maxResults': 100
}


def adf_to_text(node):
  if node is None:
    return ""
  if isinstance(node, dict):
    if node.get("type") == "text":
      return node.get("text", "")
    return "".join(adf_to_text(child) for child in node.get("content", []))
  if isinstance(node, list):
    return "".join(adf_to_text(child) for child in node)
  return ""


def clean_issue(issue):
  fields = issue.get("fields", {})
  assignee = fields.get("assignee") or {}
  reporter = fields.get("reporter") or {}
  issue_type = fields.get("issuetype") or {}
  status = fields.get("status") or {}
  priority = fields.get("priority") or {}
  parent = fields.get("parent") or {}
  parent_fields = parent.get("fields") or {}
  project = fields.get("project") or {}

  description_value = fields.get("description")
  description_text = adf_to_text(description_value).strip() if isinstance(description_value, (dict, list)) else (description_value or "")

  return {
    "id": issue.get("id"),
    "key": issue.get("key"),
    "type": issue_type.get("name"),
    "title": fields.get("summary"),
    "description": description_text,
    "status": status.get("name"),
    "priority": priority.get("name"),
    "assignee": assignee.get("displayName"),
    "reporter": reporter.get("displayName"),
    "created": fields.get("created"),
    "updated": fields.get("updated"),
    "dueDate": fields.get("duedate"),
    "labels": fields.get("labels", []),
    "parent": {
      "key": parent.get("key"),
      "title": parent_fields.get("summary"),
      "type": (parent_fields.get("issuetype") or {}).get("name")
    } if parent else None,
    "project": {
      "key": project.get("key"),
      "name": project.get("name")
    }
  }


def build_clean_response(payload):
  issues = payload.get("issues", [])
  cleaned = [clean_issue(issue) for issue in issues]
  return {
    "isLast": payload.get("isLast"),
    "count": len(cleaned),
    "issues": cleaned
  }

response = requests.request(
   "GET",
   url,
   headers=headers,
   params=query,
   auth=auth
)

if response.status_code != 200:
  print(f"Request failed: {response.status_code}")
  print(response.text)
else:
  payload = response.json()
  clean_payload = build_clean_response(payload)
  print(json.dumps(clean_payload, indent=2))