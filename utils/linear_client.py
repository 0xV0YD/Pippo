import os
from collections import defaultdict

import requests
from dotenv import load_dotenv


LINEAR_API_URL = "https://api.linear.app/graphql"


def get_linear_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("LINEAR_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing LINEAR_API_KEY in environment")
    return api_key


def linear_graphql(query: str, variables: dict | None = None) -> dict:
    response = requests.post(
        LINEAR_API_URL,
        json={"query": query, "variables": variables or {}},
        headers={
            "Authorization": get_linear_api_key(),
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise ValueError(f"Linear API error: {payload['errors']}")
    return payload["data"]


def get_linear_viewer() -> dict:
    query = """
    query Viewer {
      viewer {
        id
        name
        email
      }
    }
    """
    return linear_graphql(query)["viewer"]


def list_linear_users() -> list[dict]:
    query = """
    query Users {
      users {
        nodes {
          id
          name
          email
          active
        }
      }
    }
    """
    return linear_graphql(query)["users"]["nodes"]


def get_linear_user_by_name_or_email(token: str) -> dict:
    normalized = token.strip().lower()
    for user in list_linear_users():
        if not user.get("active", True):
            continue
        if user["email"].strip().lower() == normalized or user["name"].strip().lower() == normalized:
            return user
    raise ValueError(f"Linear user '{token}' not found")


def list_linear_teams() -> list[dict]:
    query = """
    query Teams {
      teams {
        nodes {
          id
          key
          name
        }
      }
    }
    """
    return linear_graphql(query)["teams"]["nodes"]


def get_linear_team_by_key(team_key: str) -> dict:
    normalized_key = team_key.strip().upper()
    teams = list_linear_teams()
    for team in teams:
        if team["key"].upper() == normalized_key:
            return team
    raise ValueError(f"Linear team '{team_key}' not found")


def get_linear_issue(issue_id: str) -> dict:
    query = """
    query Issue($id: String!) {
      issue(id: $id) {
        id
        identifier
        title
        url
        team {
          id
          key
          name
        }
        state {
          id
          name
        }
        assignee {
          id
          name
        }
        project {
          id
          name
        }
        labels {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    issue = linear_graphql(query, {"id": issue_id})["issue"]
    if issue is None:
        raise ValueError(f"Linear issue '{issue_id}' not found")
    return issue


def get_linear_team_states(team_id: str) -> list[dict]:
    query = """
    query TeamStates($teamId: String!) {
      team(id: $teamId) {
        id
        key
        states {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    team = linear_graphql(query, {"teamId": team_id})["team"]
    if team is None:
        raise ValueError(f"Linear team '{team_id}' not found")
    return team["states"]["nodes"]


def list_linear_projects() -> list[dict]:
    query = """
    query Projects {
      projects {
        nodes {
          id
          name
          url
        }
      }
    }
    """
    return linear_graphql(query)["projects"]["nodes"]


def get_linear_project_by_name(project_name: str) -> dict:
    normalized = project_name.strip().lower()
    for project in list_linear_projects():
        if project["name"].strip().lower() == normalized:
            return project
    raise ValueError(f"Linear project '{project_name}' not found")


def list_linear_labels() -> list[dict]:
    query = """
    query IssueLabels {
      issueLabels {
        nodes {
          id
          name
          team {
            id
            key
            name
          }
        }
      }
    }
    """
    return linear_graphql(query)["issueLabels"]["nodes"]


def get_linear_label_by_name(label_name: str, team_id: str | None = None) -> dict:
    normalized = label_name.strip().lower()
    labels = list_linear_labels()

    if team_id:
        team_labels = [label for label in labels if (label.get("team") or {}).get("id") == team_id]
        for label in team_labels:
            if label["name"].strip().lower() == normalized:
                return label

    for label in labels:
        if label["name"].strip().lower() == normalized:
            return label

    raise ValueError(f"Linear label '{label_name}' not found")


def get_linear_state_by_name(team_id: str, state_name: str) -> dict:
    normalized = state_name.strip().lower()
    for state in get_linear_team_states(team_id):
        if state["name"].strip().lower() == normalized:
            return state
    raise ValueError(f"Linear state '{state_name}' not found for this team")


def list_linear_team_issues(team_key: str, limit: int = 20) -> list[dict]:
    team = get_linear_team_by_key(team_key)
    query = """
    query TeamIssues($teamId: String!, $first: Int!) {
      team(id: $teamId) {
        id
        key
        name
        issues(first: $first) {
          nodes {
            id
            identifier
            title
            priority
            state {
              name
            }
            team {
              key
              name
            }
            assignee {
              name
            }
            url
          }
        }
      }
    }
    """
    team_data = linear_graphql(query, {"teamId": team["id"], "first": limit})["team"]
    if team_data is None:
        raise ValueError(f"Linear team '{team_key}' not found")
    return team_data["issues"]["nodes"]


def list_my_linear_issues(limit: int = 20) -> list[dict]:
    query = """
    query MyIssues($first: Int!) {
      viewer {
        assignedIssues(first: $first) {
          nodes {
            id
            identifier
            title
            priority
            url
            team {
              key
              name
            }
            state {
              name
            }
            assignee {
              name
            }
          }
        }
      }
    }
    """
    return linear_graphql(query, {"first": limit})["viewer"]["assignedIssues"]["nodes"]


def filter_linear_issues(
    issues: list[dict],
    *,
    team_key: str | None = None,
    only_mine: bool = False,
    viewer_name: str | None = None,
    state_names: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    filtered = issues

    if team_key:
        normalized_team = team_key.strip().upper()
        filtered = [
            issue for issue in filtered if (issue.get("team") or {}).get("key", "").upper() == normalized_team
        ]

    if only_mine and viewer_name:
        normalized_viewer = viewer_name.strip().lower()
        filtered = [
            issue
            for issue in filtered
            if ((issue.get("assignee") or {}).get("name") or "").strip().lower() == normalized_viewer
        ]

    if state_names:
        normalized_states = {state.strip().lower() for state in state_names if state.strip()}
        filtered = [
            issue
            for issue in filtered
            if ((issue.get("state") or {}).get("name") or "").strip().lower() in normalized_states
        ]

    if limit is not None:
        filtered = filtered[:limit]

    return filtered


def format_linear_issues_readable(
    issues: list[dict],
    *,
    heading: str,
) -> str:
    if not issues:
        return f"{heading}\nNo issues found."

    grouped: dict[str, list[dict]] = defaultdict(list)
    for issue in issues:
        state_name = ((issue.get("state") or {}).get("name") or "Unknown").strip()
        grouped[state_name].append(issue)

    lines = [heading]
    for state_name in sorted(grouped.keys()):
        lines.append("")
        lines.append(f"{state_name}")
        for issue in grouped[state_name]:
            identifier = issue.get("identifier", "unknown")
            title = issue.get("title", "Untitled")
            team_key = (issue.get("team") or {}).get("key", "")
            assignee = (issue.get("assignee") or {}).get("name") or "Unassigned"
            url = issue.get("url", "")
            meta = f"{team_key} | {assignee}" if team_key else assignee
            lines.append(f"- {identifier}: {title}")
            lines.append(f"  {meta}")
            if url:
                lines.append(f"  {url}")

    return "\n".join(lines)


def create_linear_issue(
    team_id: str,
    title: str,
    description: str = "",
    assignee_id: str | None = None,
) -> dict:
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          title
          url
        }
      }
    }
    """
    input_data = {
        "teamId": team_id,
        "title": title.strip(),
    }
    if description.strip():
        input_data["description"] = description.strip()
    if assignee_id:
        input_data["assigneeId"] = assignee_id

    result = linear_graphql(mutation, {"input": input_data})["issueCreate"]
    if not result.get("success") or not result.get("issue"):
        raise ValueError("Linear issue creation failed")
    return result["issue"]


def update_linear_issue_state(issue_id: str, state_name: str) -> dict:
    issue = get_linear_issue(issue_id)
    team = issue.get("team")
    if not team:
        raise ValueError(f"Linear issue '{issue_id}' has no team")

    state = get_linear_state_by_name(team["id"], state_name)
    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue {
          id
          identifier
          title
          url
          state {
            id
            name
          }
        }
      }
    }
    """
    result = linear_graphql(
        mutation,
        {
            "id": issue_id,
            "input": {"stateId": state["id"]},
        },
    )["issueUpdate"]
    if not result.get("success") or not result.get("issue"):
        raise ValueError("Linear issue update failed")
    return result["issue"]


def update_linear_issue_labels(issue_id: str, label_names: list[str]) -> dict:
    issue = get_linear_issue(issue_id)
    team = issue.get("team")
    label_ids = []
    for label_name in label_names:
        label = get_linear_label_by_name(label_name, team_id=(team or {}).get("id"))
        label_ids.append(label["id"])

    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue {
          id
          identifier
          title
          url
          labels {
            nodes {
              id
              name
            }
          }
        }
      }
    }
    """
    result = linear_graphql(
        mutation,
        {
            "id": issue_id,
            "input": {"labelIds": label_ids},
        },
    )["issueUpdate"]
    if not result.get("success") or not result.get("issue"):
        raise ValueError("Linear issue label update failed")
    return result["issue"]


def add_linear_issue_labels(issue_id: str, label_names: list[str]) -> dict:
    issue = get_linear_issue(issue_id)
    current_ids = [label["id"] for label in issue["labels"]["nodes"]]
    team = issue.get("team")
    for label_name in label_names:
        label = get_linear_label_by_name(label_name, team_id=(team or {}).get("id"))
        if label["id"] not in current_ids:
            current_ids.append(label["id"])
    return _update_issue_fields(
        issue_id=issue_id,
        input_data={"labelIds": current_ids},
        selection="""
          labels {
            nodes {
              id
              name
            }
          }
        """,
        error_message="Linear issue label update failed",
    )


def remove_linear_issue_labels(issue_id: str, label_names: list[str]) -> dict:
    issue = get_linear_issue(issue_id)
    remove_names = {label_name.strip().lower() for label_name in label_names if label_name.strip()}
    remaining_ids = [
        label["id"]
        for label in issue["labels"]["nodes"]
        if label["name"].strip().lower() not in remove_names
    ]
    return _update_issue_fields(
        issue_id=issue_id,
        input_data={"labelIds": remaining_ids},
        selection="""
          labels {
            nodes {
              id
              name
            }
          }
        """,
        error_message="Linear issue label removal failed",
    )


def update_linear_issue_project(issue_id: str, project_name: str) -> dict:
    project = get_linear_project_by_name(project_name)
    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue {
          id
          identifier
          title
          url
          project {
            id
            name
          }
        }
      }
    }
    """
    result = linear_graphql(
        mutation,
        {
            "id": issue_id,
            "input": {"projectId": project["id"]},
        },
    )["issueUpdate"]
    if not result.get("success") or not result.get("issue"):
        raise ValueError("Linear issue project update failed")
    return result["issue"]


def assign_linear_issue(issue_id: str, assignee_token: str) -> dict:
    user = get_linear_user_by_name_or_email(assignee_token)
    return _update_issue_fields(
        issue_id=issue_id,
        input_data={"assigneeId": user["id"]},
        selection="""
          assignee {
            id
            name
            email
          }
        """,
        error_message="Linear issue assignee update failed",
    )


def _update_issue_fields(issue_id: str, input_data: dict, selection: str, error_message: str) -> dict:
    mutation = f"""
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {{
      issueUpdate(id: $id, input: $input) {{
        success
        issue {{
          id
          identifier
          title
          url
          {selection}
        }}
      }}
    }}
    """
    result = linear_graphql(mutation, {"id": issue_id, "input": input_data})["issueUpdate"]
    if not result.get("success") or not result.get("issue"):
        raise ValueError(error_message)
    return result["issue"]
