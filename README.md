# Jira Sprint Coach

An AI agent that acts as a sprint coach for engineering teams — analysing sprint health, flagging blockers, surfacing workload risks, and tracking velocity trends. Built on **Azure AI Foundry** using the **MCP (Model Context Protocol)** stdio integration pattern.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Azure AI Foundry](https://img.shields.io/badge/Azure-AI%20Foundry-0078D4.svg)](https://ai.azure.com/)

---

## What it does

Ask natural-language questions about your sprint and get direct, actionable answers:

- "Give me a full sprint health check."
- "Who is overloaded and who has capacity?"
- "What's blocked and what's the downstream cascade risk?"
- "Are we on track to finish the sprint?"
- "What issues are overdue right now?"
- "Show me our velocity trend over the last few sprints."

Every response ends with a **RISK LEVEL: GREEN / AMBER / RED** and a single top-priority action for the team.

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

**Key design principle:** `agent.py` is completely unaware of Jira credentials — it speaks only MCP. The server is the integration boundary. Swapping Jira for Linear, Shortcut, or GitHub Projects requires changes only to `server.py`.

---

## The six tools

| Tool | Filters | What it reveals |
|---|---|---|
| `get_active_sprint` | — | Sprint goal, dates, % complete, points remaining |
| `get_sprint_issues` | status, assignee | Full issue list with priorities and due dates |
| `get_team_workload` | — | Remaining points per person, at-risk flags |
| `get_blockers` | — | Blocked issues + downstream cascade count |
| `get_overdue_issues` | — | Incomplete issues past due date |
| `get_velocity_metrics` | — | 4-sprint trend, on-track indicator |

---

## Prerequisites

- Python 3.11+
- An [Azure AI Foundry](https://ai.azure.com/) project with a **gpt-4.1** (or gpt-4o) model deployment
- Azure CLI installed and logged in (`az login`)

---

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/rajshrinivasan/jira-sprint-coach-foundry-agent.git
cd jira-sprint-coach-foundry-agent

# 2. Create and activate a virtual environment
python -m venv venv
source venv/Scripts/activate      # Windows
# source venv/bin/activate        # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env and fill in PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME
```

### .env values

| Variable | Where to find it |
|---|---|
| `PROJECT_ENDPOINT` | AI Foundry portal → your project → Overview → Project details |
| `MODEL_DEPLOYMENT_NAME` | AI Foundry portal → your project → Deployments |

---

## Running

```bash
python agent.py
```

`agent.py` spawns `server.py` automatically as a subprocess — no separate terminal needed.

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

## Simulated sprint data

The repo ships with a fully simulated Sprint 42 — Platform Reliability designed to exercise all the agent's analytical capabilities:

- **84 story points** total, 31 completed
- **5 team members:** sarah.chen, james.okafor, priya.nair, alex.wong, mia.garcia, tom.harris
- `ENG-1198` — Blocked by legal/DPO review; cascades into `ENG-1209` (13 pts, Critical)
- `ENG-1201` — In Progress; blocks 3 dashboard tickets (ENG-1210, 1211, 1215)
- tom.harris — highest remaining load (16 pts)

---

## Connecting to a real Jira instance

Replace the simulated data layer in `server.py` with real Jira REST API calls:

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

Add the corresponding variables to `.env` (see `.env.example`). `agent.py` and `prompts/system_prompt.txt` require no changes.

---

## File structure

```
jira-sprint-coach-foundry-agent/
├── agent.py                    # MCP client + Foundry agent bridge
├── server.py                   # FastMCP server — 6 Jira tools
├── prompts/
│   └── system_prompt.txt       # Sprint coach persona and risk thresholds
├── requirements.txt
├── .env.example                # Template — copy to .env and fill in values
├── LICENSE
└── README.md
```

---

## License

[MIT](LICENSE)
