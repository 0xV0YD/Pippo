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
