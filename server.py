"""
server.py — FastMCP server simulating a Jira REST API integration.

In production this server would make authenticated HTTP calls to
https://<your-org>.atlassian.net/rest/api/3/  using a Jira API token.
The tool signatures, return shapes, and field names match what a real
Jira MCP server would expose, making it straightforward to swap the
simulated data layer for real Jira API calls.

Tools exposed:
  - get_active_sprint       : current sprint metadata and progress
  - get_sprint_issues       : all issues in a sprint, filterable by status/assignee
  - get_team_workload       : story point load per team member
  - get_blockers            : all blocked issues with blocker descriptions
  - get_overdue_issues      : issues past due date that are not done
  - get_velocity_metrics    : story points completed across recent sprints
"""

import json
from datetime import date
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="JiraSprint")


# ---------------------------------------------------------------------------
# Simulated Jira data
# ---------------------------------------------------------------------------

_SPRINT = {
    "id": "SPR-42",
    "name": "Sprint 42 — Platform Reliability",
    "board": "Engineering",
    "state": "active",
    "start_date": "2026-03-24",
    "end_date": "2026-04-07",
    "goal": "Reduce p99 API latency below 200ms and ship observability dashboard v1.",
    "total_story_points": 84,
    "completed_story_points": 31,
    "days_remaining": (date(2026, 4, 7) - date.today()).days,
}

_ISSUES = [
    # In Progress
    {"key": "ENG-1201", "summary": "Implement distributed tracing with OpenTelemetry", "status": "In Progress", "assignee": "sarah.chen", "story_points": 8, "due_date": "2026-04-02", "priority": "High", "labels": ["observability"], "blocked_by": None},
    {"key": "ENG-1204", "summary": "Add Redis caching layer to user profile endpoint", "status": "In Progress", "assignee": "james.okafor", "story_points": 5, "due_date": "2026-03-31", "priority": "High", "labels": ["performance"], "blocked_by": None},
    {"key": "ENG-1209", "summary": "Migrate auth service to async request handling", "status": "In Progress", "assignee": "priya.nair", "story_points": 13, "due_date": "2026-04-04", "priority": "Critical", "labels": ["auth", "performance"], "blocked_by": "ENG-1198"},
    # To Do
    {"key": "ENG-1210", "summary": "Dashboard: latency histogram widget", "status": "To Do", "assignee": "alex.wong", "story_points": 5, "due_date": "2026-04-05", "priority": "Medium", "labels": ["observability"], "blocked_by": "ENG-1201"},
    {"key": "ENG-1211", "summary": "Dashboard: error rate time-series chart", "status": "To Do", "assignee": "alex.wong", "story_points": 5, "due_date": "2026-04-05", "priority": "Medium", "labels": ["observability"], "blocked_by": "ENG-1201"},
    {"key": "ENG-1212", "summary": "Load test API gateway at 10k RPS", "status": "To Do", "assignee": "mia.garcia", "story_points": 8, "due_date": "2026-04-06", "priority": "High", "labels": ["performance", "testing"], "blocked_by": None},
    {"key": "ENG-1213", "summary": "Write runbook for on-call latency incidents", "status": "To Do", "assignee": "tom.harris", "story_points": 3, "due_date": "2026-04-07", "priority": "Low", "labels": ["docs"], "blocked_by": None},
    {"key": "ENG-1214", "summary": "Database query optimisation: N+1 in orders API", "status": "To Do", "assignee": "james.okafor", "story_points": 8, "due_date": "2026-04-03", "priority": "High", "labels": ["performance", "database"], "blocked_by": None},
    {"key": "ENG-1215", "summary": "Set up Grafana alerting for SLO breach", "status": "To Do", "assignee": "sarah.chen", "story_points": 5, "due_date": "2026-04-04", "priority": "High", "labels": ["observability"], "blocked_by": "ENG-1201"},
    # Done
    {"key": "ENG-1190", "summary": "Upgrade Postgres to 16.2", "status": "Done", "assignee": "devops-bot", "story_points": 3, "due_date": "2026-03-26", "priority": "Medium", "labels": ["infrastructure"], "blocked_by": None},
    {"key": "ENG-1195", "summary": "Add structured logging to payment service", "status": "Done", "assignee": "priya.nair", "story_points": 5, "due_date": "2026-03-27", "priority": "Medium", "labels": ["observability"], "blocked_by": None},
    {"key": "ENG-1197", "summary": "Remove deprecated v1 API endpoints", "status": "Done", "assignee": "sarah.chen", "story_points": 3, "due_date": "2026-03-28", "priority": "Low", "labels": ["tech-debt"], "blocked_by": None},
    {"key": "ENG-1199", "summary": "Connection pool tuning for read replicas", "status": "Done", "assignee": "james.okafor", "story_points": 5, "due_date": "2026-03-29", "priority": "High", "labels": ["database", "performance"], "blocked_by": None},
    {"key": "ENG-1200", "summary": "Deploy CDN for static assets", "status": "Done", "assignee": "mia.garcia", "story_points": 5, "due_date": "2026-03-29", "priority": "Medium", "labels": ["infrastructure"], "blocked_by": None},
    # Blocked
    {"key": "ENG-1198", "summary": "Refactor session token storage for GDPR compliance", "status": "Blocked", "assignee": "tom.harris", "story_points": 13, "due_date": "2026-04-01", "priority": "Critical", "labels": ["compliance", "auth"], "blocked_by": "Legal review pending — awaiting sign-off from DPO"},
]

_VELOCITY = [
    {"sprint": "Sprint 39", "committed": 72, "completed": 68},
    {"sprint": "Sprint 40", "committed": 80, "completed": 74},
    {"sprint": "Sprint 41", "committed": 78, "completed": 71},
    {"sprint": "Sprint 42", "committed": 84, "completed": 31, "note": "In progress"},
]


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_active_sprint() -> str:
    """Return metadata and progress summary for the currently active sprint."""
    sprint = dict(_SPRINT)
    total = sprint["total_story_points"]
    done  = sprint["completed_story_points"]
    sprint["percent_complete"] = round((done / total) * 100) if total else 0
    sprint["points_remaining"] = total - done
    return json.dumps(sprint)


@mcp.tool()
def get_sprint_issues(status_filter: str = "all", assignee_filter: str = "all") -> str:
    """
    Return issues in the active sprint.
    status_filter: 'To Do', 'In Progress', 'Done', 'Blocked', or 'all'
    assignee_filter: email prefix (e.g. 'sarah.chen') or 'all'
    """
    issues = _ISSUES
    if status_filter != "all":
        issues = [i for i in issues if i["status"].lower() == status_filter.lower()]
    if assignee_filter != "all":
        issues = [i for i in issues if i["assignee"] == assignee_filter]

    return json.dumps({
        "sprint_id": _SPRINT["id"],
        "filter": {"status": status_filter, "assignee": assignee_filter},
        "count": len(issues),
        "issues": issues,
    })


@mcp.tool()
def get_team_workload() -> str:
    """
    Return story point load and issue count per team member for the active sprint.
    Excludes Done issues from the 'remaining' count.
    """
    workload: dict[str, dict] = {}
    for issue in _ISSUES:
        name = issue["assignee"]
        if name not in workload:
            workload[name] = {"total_points": 0, "remaining_points": 0, "issues": [], "done": 0}
        workload[name]["total_points"] += issue["story_points"]
        workload[name]["issues"].append(issue["key"])
        if issue["status"] != "Done":
            workload[name]["remaining_points"] += issue["story_points"]
        else:
            workload[name]["done"] += 1

    # Flag members who are overloaded (remaining > 13 points with < 7 days left)
    days_left = _SPRINT["days_remaining"]
    for name, data in workload.items():
        data["at_risk"] = data["remaining_points"] > 13 and days_left < 7

    return json.dumps({
        "sprint_id": _SPRINT["id"],
        "days_remaining": days_left,
        "team": workload,
    })


@mcp.tool()
def get_blockers() -> str:
    """Return all blocked issues with their blocker descriptions and risk assessment."""
    blocked = [i for i in _ISSUES if i["status"] == "Blocked" or i["blocked_by"] is not None]

    enriched = []
    for issue in blocked:
        downstream = [
            d["key"] for d in _ISSUES
            if d["blocked_by"] == issue["key"]
        ]
        enriched.append({
            **issue,
            "downstream_blocked": downstream,
            "cascade_risk": len(downstream) > 0,
        })

    return json.dumps({
        "sprint_id": _SPRINT["id"],
        "blocked_count": len(enriched),
        "blockers": enriched,
    })


@mcp.tool()
def get_overdue_issues() -> str:
    """Return all incomplete issues whose due date has already passed."""
    today_str = date.today().isoformat()
    overdue = [
        i for i in _ISSUES
        if i["status"] != "Done" and i["due_date"] < today_str
    ]
    return json.dumps({
        "sprint_id": _SPRINT["id"],
        "today": today_str,
        "overdue_count": len(overdue),
        "issues": overdue,
    })


@mcp.tool()
def get_velocity_metrics() -> str:
    """Return story point velocity across the last four sprints including the current one."""
    avg_completed = sum(s["completed"] for s in _VELOCITY[:-1]) / max(len(_VELOCITY) - 1, 1)
    current = _VELOCITY[-1]
    projected_completion = round(
        (current["completed"] / max(_SPRINT["total_story_points"] - current["completed"], 1))
        * _SPRINT["days_remaining"]
    )

    return json.dumps({
        "sprints": _VELOCITY,
        "avg_velocity_last_3": round(avg_completed, 1),
        "current_sprint_on_track": current["completed"] >= (avg_completed * 0.4),
        "projected_days_to_complete": projected_completion,
    })


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
