"""
Jira Sprint Coach
==================
Pattern : MCP Integration — third-party SaaS via stdio

Same MCP stdio architecture as Project 09, but the server represents a
SaaS integration (Jira) rather than local toolchain. The key distinction:

  Project 09 server → wraps local tools (git, docker, env files)
  Project 10 server → wraps a remote REST API (Jira / Atlassian)

In production, server.py would make authenticated HTTP calls to
https://<org>.atlassian.net/rest/api/3/ using a Jira API token stored
in the server's own environment. The agent.py is completely unaware of
Jira credentials — it only speaks MCP.

This separation is the point of the pattern: the MCP server is the
integration layer. Swapping it for a different project management tool
(Linear, Shortcut, GitHub Projects) requires no changes to agent.py.
"""

import os
import sys
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ---------------------------------------------------------------------------
# Load prompt from file
# ---------------------------------------------------------------------------
def load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# MCP server connection
# ---------------------------------------------------------------------------
async def connect_to_mcp_server(exit_stack: AsyncExitStack) -> ClientSession:
    server_script = str(Path(__file__).parent / "server.py")
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env=None,
    )

    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = stdio_transport

    session = await exit_stack.enter_async_context(ClientSession(stdio, write))
    await session.initialize()

    tools_response = await session.list_tools()
    tool_names = [t.name for t in tools_response.tools]
    print(f"  Jira MCP server connected. Tools: {tool_names}\n")

    return session


# ---------------------------------------------------------------------------
# Build FunctionTool definitions from MCP metadata
# ---------------------------------------------------------------------------
def build_function_tools(mcp_tools) -> list[FunctionTool]:
    function_tools = []
    for tool in mcp_tools:
        parameters = (
            tool.inputSchema
            if hasattr(tool, "inputSchema") and tool.inputSchema
            else {"type": "object", "properties": {}, "additionalProperties": False}
        )
        if isinstance(parameters, dict):
            parameters["additionalProperties"] = False

        function_tools.append(
            FunctionTool(
                name=tool.name,
                description=tool.description or tool.name,
                parameters=parameters,
                strict=True,
            )
        )
    return function_tools


# ---------------------------------------------------------------------------
# Dispatch function calls to MCP server
# ---------------------------------------------------------------------------
async def dispatch_to_mcp(session: ClientSession, response) -> list:
    outputs = []
    for item in response.output:
        if item.type != "function_call":
            continue
        try:
            args = json.loads(item.arguments) if item.arguments else {}
            mcp_result = await session.call_tool(item.name, args)
            result_text = mcp_result.content[0].text if mcp_result.content else "{}"
            print(f"  [jira] {item.name}({args}) → OK")
        except Exception as exc:
            result_text = json.dumps({"error": str(exc)})
            print(f"  [jira] {item.name} → ERROR: {exc}")

        outputs.append(
            FunctionCallOutput(
                type="function_call_output",
                call_id=item.call_id,
                output=result_text,
            )
        )
    return outputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def print_banner():
    print("=" * 60)
    print("   JIRA SPRINT COACH")
    print("   Powered by Azure AI Foundry — MCP (SaaS Integration)")
    print("=" * 60)
    print()


def has_function_calls(response) -> bool:
    return any(item.type == "function_call" for item in response.output)


# ---------------------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------------------
async def run_chat(session: ClientSession):
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    if not project_endpoint or not model_deployment:
        print("ERROR: PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME must be set in .env")
        sys.exit(1)

    tools_response = await session.list_tools()
    function_tools = build_function_tools(tools_response.tools)
    system_prompt = load_prompt("system_prompt.txt")

    with (
        DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True,
        ) as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        agent = project_client.agents.create_version(
            agent_name="jira-sprint-coach",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=system_prompt,
                tools=function_tools,
            ),
        )
        print(f"Agent ready: {agent.name} (version={agent.version})\n")

        conversation = openai_client.conversations.create()
        print("Session started. Type 'quit' to exit.\n")
        print("Suggested questions:")
        print("  1. Give me a full sprint health check.")
        print("  2. Who is overloaded and who has capacity?")
        print("  3. What's blocked and what's the downstream impact?")
        print("  4. Are we on track to finish the sprint?")
        print("  5. What issues are overdue right now?")
        print("  6. Show me our velocity trend over the last few sprints.")
        print()

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )

            print("\nQuerying Jira...\n")
            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                input="",
            )

            if response.status == "failed":
                print(f"[Error] {response.error}\n")
                continue

            while has_function_calls(response):
                mcp_outputs = await dispatch_to_mcp(session, response)
                print()
                response = openai_client.responses.create(
                    input=mcp_outputs,
                    previous_response_id=response.id,
                    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
                )
                if response.status == "failed":
                    print(f"[Error] {response.error}\n")
                    break

            print(f"Coach: {response.output_text}\n")
            print("-" * 60)
            print()

        # Cleanup
        print("\nCleaning up...")
        try:
            openai_client.conversations.delete(conversation_id=conversation.id)
        except Exception:
            pass
        try:
            project_client.agents.delete_version(
                agent_name=agent.name, agent_version=agent.version
            )
        except Exception:
            pass
        print("  Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    print_banner()
    exit_stack = AsyncExitStack()
    try:
        print("Connecting to Jira MCP server...")
        session = await connect_to_mcp_server(exit_stack)
        await run_chat(session)
    finally:
        await exit_stack.aclose()
        print("\nMCP server stopped. Session complete.")


if __name__ == "__main__":
    asyncio.run(main())
