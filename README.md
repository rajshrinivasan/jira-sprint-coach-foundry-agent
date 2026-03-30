# Project 10 — Jira Sprint Coach

## Pattern
**MCP Integration — third-party SaaS via stdio**

Same MCP stdio architecture as Project 09, but the server represents a
remote SaaS API (Jira) rather than local toolchain tools. The agent is
completely isolated from Jira credentials — it speaks only MCP. The server
is the integration layer.

This separation means swapping Jira for Linear, Shortcut, or GitHub Projects
requires changes only to `server.py` — `agent.py` stays untouched.

---

## Architecture

```
agent.py  (MCP client + Foundry agent)
    │
    │  1. Spawns server.py as subprocess (stdio transport)
    │  2. Discovers 6 tools dynamically via session.list_tools()
    │  3. Registers as FunctionTools with Foundry agent
    │
    │  ── per turn ────────────────────────────────────────────────
    │  4. User question → agent emits function_call items
    │  5. dispatch_to_mcp() → session.call_tool(name, args)
    │       └─► server.py queries Jira API → returns JSON
    │  6. FunctionCallOutput → model composes answer
    └──────────────────────────────────────────────────────────────

server.py  (FastMCP — Jira integration layer)
    ├── get_active_sprint()          reads: sprint metadata
    ├── get_sprint_issues(...)       reads: all issues with filters
    ├── get_team_workload()          computes: points per person
    ├── get_blockers()               reads: blocked + cascade risk
    ├── get_overdue_issues()         reads: past-due incomplete issues
    └── get_velocity_metrics()       reads: 4-sprint velocity history
```

---

## Project 09 vs Project 10 — what's different

| Dimension | Project 09 (Dev Onboarding) | Project 10 (Sprint Coach) |
|---|---|---|
| Server wraps | Local processes (git, docker, env) | Remote SaaS API (Jira) |
| Credential boundary | No credentials needed | Jira API token lives in server only |
| Swappability | Replace with real shell commands | Replace with real `httpx` calls to Jira |
| State | Read-only, ephemeral | Read-only (write tools could be added) |
| Domain | Dev setup | Agile project management |

The `agent.py` files are nearly identical. This is intentional — it demonstrates
that the MCP pattern is generic. Only the server changes per integration.

---

## Connecting to a real Jira instance

To use a live Jira board instead of simulated data, replace the data layer in
`server.py` with real Jira REST API calls. Each tool body would become:

```python
import httpx, os

JIRA_BASE = os.getenv("JIRA_BASE_URL")
AUTH = (os.getenv("JIRA_USER_EMAIL"), os.getenv("JIRA_API_TOKEN"))

@mcp.tool()
def get_active_sprint() -> str:
    board_id = os.getenv("JIRA_BOARD_ID")
    r = httpx.get(
        f"{JIRA_BASE}/rest/agile/1.0/board/{board_id}/sprint",
        params={"state": "active"},
        auth=AUTH,
    )
    sprint = r.json()["values"][0]
    return json.dumps(sprint)
```

The agent and prompt require no changes.

---

## Simulated sprint data

**Sprint 42 — Platform Reliability** (active)
- Goal: Reduce p99 API latency below 200ms and ship observability dashboard v1
- 84 story points total, 31 completed, ~14 days remaining
- 5 team members: sarah.chen, james.okafor, priya.nair, alex.wong, mia.garcia, tom.harris

Notable issues planted for interesting agent analysis:
- `ENG-1198` — Blocked by legal review; blocks `ENG-1209` (13 pts, Critical) — cascade risk
- `ENG-1201` — In Progress; blocks 3 dashboard tickets (ENG-1210, 1211, 1215)
- `ENG-1204` — In Progress, due 2026-03-31 (overdue)
- alex.wong — assigned 2 issues both blocked by ENG-1201 (workload risk)

---

## The six tools

| Tool | Filters | What it reveals |
|---|---|---|
| `get_active_sprint` | None | Sprint goal, dates, % complete, points remaining |
| `get_sprint_issues` | status, assignee | Full issue list with priorities and due dates |
| `get_team_workload` | None | Remaining points per person, at-risk flags |
| `get_blockers` | None | Blocked issues + downstream cascade count |
| `get_overdue_issues` | None | Incomplete issues past due date |
| `get_velocity_metrics` | None | 4-sprint trend, on-track indicator |

---

## Prerequisites

- Python 3.11+
- An Azure AI Foundry project with a **gpt-4.1** (or gpt-4o) model deployment
- Azure CLI logged in (`az login`)
- `mcp` Python package (included in requirements)

---

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate      # Windows
# source venv/bin/activate        # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env — fill in PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME
```

## Running

```bash
python agent.py
```

`agent.py` starts `server.py` automatically as a subprocess.

---

## Suggested questions

| Question | Tools called |
|---|---|
| Give me a full sprint health check | all 6 tools |
| Who is overloaded? | `get_team_workload` |
| What's blocked and what's the cascade risk? | `get_blockers` |
| Are we on track to finish? | `get_active_sprint` + `get_velocity_metrics` |
| What issues are overdue? | `get_overdue_issues` |
| Show me everything assigned to sarah.chen | `get_sprint_issues(assignee_filter="sarah.chen")` |

---

## File structure

```
10-jira-sprint-coach/
├── agent.py                    # MCP client + Foundry agent bridge
├── server.py                   # FastMCP server — 6 Jira tools
├── prompts/
│   └── system_prompt.txt       # Sprint coach persona and risk thresholds
├── requirements.txt
├── .env.example                # Includes commented real-Jira vars
├── .env
└── README.md
```
