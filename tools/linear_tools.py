from server import mcp
from utils.linear_client import (
    create_linear_issue,
    filter_linear_issues,
    format_linear_issues_readable,
    get_linear_issue,
    list_linear_labels,
    list_linear_projects,
    get_linear_viewer,
    list_linear_team_issues,
    list_linear_teams,
    list_my_linear_issues,
    update_linear_issue_labels,
    update_linear_issue_project,
    update_linear_issue_state,
)


@mcp.tool()
def get_linear_profile() -> str:
    """
    Return the current Linear viewer profile for the configured API key.
    """
    viewer = get_linear_viewer()
    return f"Linear viewer: {viewer['name']} <{viewer['email']}> (id: {viewer['id']})"


@mcp.tool()
def list_linear_orgs() -> str:
    """
    List available Linear teams for the configured workspace.
    """
    teams = list_linear_teams()
    if not teams:
        return "No Linear teams found."
    formatted = [f"{team['key']}: {team['name']} (id: {team['id']})" for team in teams]
    return "Linear teams:\n" + "\n".join(formatted)


@mcp.tool()
def list_linear_projects_tool() -> str:
    """
    List Linear projects in the workspace.
    """
    projects = list_linear_projects()
    if not projects:
        return "No Linear projects found."
    return "Linear projects:\n" + "\n".join(f"{p['name']} (id: {p['id']}) {p['url']}" for p in projects)


@mcp.tool()
def list_linear_labels_tool() -> str:
    """
    List available Linear issue labels.
    """
    labels = list_linear_labels()
    if not labels:
        return "No Linear labels found."
    lines = []
    for label in labels:
        team_key = (label.get("team") or {}).get("key", "workspace")
        lines.append(f"{label['name']} [{team_key}] (id: {label['id']})")
    return "Linear labels:\n" + "\n".join(lines)


@mcp.tool()
def list_linear_issues(
    team_key: str,
    limit: int = 20,
    only_mine: bool = False,
    state_filter: str = "",
) -> str:
    """
    List issues for a Linear team key such as ENG or OPS.
    """
    issues = list_linear_team_issues(team_key=team_key, limit=limit)
    viewer = get_linear_viewer()
    state_names = [part.strip() for part in state_filter.split(",") if part.strip()]
    filtered = filter_linear_issues(
        issues,
        only_mine=only_mine,
        viewer_name=viewer["name"],
        state_names=state_names or None,
        limit=limit,
    )
    return format_linear_issues_readable(filtered, heading=f"Linear issues in {team_key.upper()}:")


@mcp.tool()
def list_my_linear_assigned_issues(team_key: str = "", limit: int = 20, state_filter: str = "") -> str:
    """
    List issues assigned to the current Linear viewer.
    """
    issues = list_my_linear_issues(limit=limit)
    viewer = get_linear_viewer()
    state_names = [part.strip() for part in state_filter.split(",") if part.strip()]
    filtered = filter_linear_issues(
        issues,
        team_key=team_key or None,
        only_mine=True,
        viewer_name=viewer["name"],
        state_names=state_names or None,
        limit=limit,
    )
    heading = "Your Linear issues:"
    if team_key:
        heading = f"Your Linear issues in {team_key.upper()}:"
    return format_linear_issues_readable(filtered, heading=heading)


@mcp.tool()
def create_linear_issue_tool(
    team_id: str,
    title: str,
    description: str = "",
    assignee_id: str = "",
) -> str:
    """
    Create a new Linear issue in the specified team.
    """
    issue = create_linear_issue(
        team_id=team_id,
        title=title,
        description=description,
        assignee_id=assignee_id or None,
    )
    return f"Created Linear issue {issue['identifier']}: {issue['title']} {issue['url']}"


@mcp.tool()
def update_linear_issue_state_tool(issue_id: str, state_name: str) -> str:
    """
    Update a Linear issue to a new workflow state such as Todo, In Progress, In Review, or Done.
    """
    issue = update_linear_issue_state(issue_id=issue_id, state_name=state_name)
    return (
        f"Updated Linear issue {issue['identifier']} to {issue['state']['name']}: "
        f"{issue['title']} {issue['url']}"
    )


@mcp.tool()
def update_linear_issue_labels_tool(issue_id: str, label_names_csv: str) -> str:
    """
    Replace the labels on a Linear issue using a comma-separated list of label names.
    """
    label_names = [part.strip() for part in label_names_csv.split(",") if part.strip()]
    issue = update_linear_issue_labels(issue_id=issue_id, label_names=label_names)
    label_text = ", ".join(label["name"] for label in issue["labels"]["nodes"]) or "no labels"
    return f"Updated labels for {issue['identifier']}: {label_text}"


@mcp.tool()
def update_linear_issue_project_tool(issue_id: str, project_name: str) -> str:
    """
    Assign a Linear issue to a project by project name.
    """
    issue = update_linear_issue_project(issue_id=issue_id, project_name=project_name)
    project_name = issue["project"]["name"] if issue.get("project") else "No project"
    return f"Updated project for {issue['identifier']}: {project_name}"
