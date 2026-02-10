import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import autogen
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

from ..settings import get_settings
from .tools import (
    get_custom_function_map,
    get_custom_tool_schemas,
)

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MCP_ROOT = PROJECT_ROOT / "mcp_servers"


@dataclass
class SessionState:
    """Per-session conversation state."""

    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    investigation_summary: str = ""
    tool_calls_count: int = 0


SESSIONS: Dict[str, SessionState] = {}


class JewelryOpsAgentService:
    """Orchestrates the JewelryOps AutoGen agent: sessions, MCP tools, and streaming."""

    def __init__(self) -> None:
        self._mcp_tools_cache: List[Dict[str, Any]] | None = None

    def get_session(self, session_id: str) -> SessionState:
        """Return or create the SessionState for the given session_id.
        
        Args:
            session_id: Unique identifier for the session (str).
            
        Returns:
            SessionState: Session object containing messages, summary, and tool call count.
        """
        if session_id not in SESSIONS:
            SESSIONS[session_id] = SessionState(session_id=session_id)
        return SESSIONS[session_id]


    async def _load_mcp_tools_async(self) -> List[Dict[str, Any]]:
        """Load tools from all MCP servers and convert to OpenAI function format.
        
        Returns:
            List[Dict[str, Any]]: List of tool schemas in OpenAI function format.
                Each dict contains {"type": "function", "function": {...}}.
        """
        settings = get_settings()
        env = {"PYTHONPATH": str(PROJECT_ROOT), **os.environ}

        mcp_configs = [
            {
                "name": "jewelryops_mysql",
                "default_cmd": str(MCP_ROOT / "jewelryops_mysql" / "server.py"),
                "config_cmd": settings.mcp_jewelryops_cmd,
            },
            {
                "name": "notion_mock",
                "default_cmd": str(MCP_ROOT / "notion_mock" / "server.py"),
                "config_cmd": settings.mcp_notion_cmd,
            },
            {
                "name": "gmail_mock",
                "default_cmd": str(MCP_ROOT / "gmail_mock" / "server.py"),
                "config_cmd": settings.mcp_gmail_cmd,
            },
        ]

        all_tools: List[Dict[str, Any]] = []

        for config in mcp_configs:
            cmd = config["config_cmd"]
            if not cmd:
                logger.info(
                    "MCP server '%s' has no startup command configured; skipping",
                    config["name"],
                )
                continue

            cmd_parts = cmd.split()
            if len(cmd_parts) < 2:
                logger.warning(
                    "Invalid MCP command format for '%s': %s",
                    config["name"],
                    cmd,
                )
                continue

            server_params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:],
                env=env,
            )

            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        for tool_info in tools_result.tools:
                            tool_schema = {
                                "type": "function",
                                "function": {
                                    "name": tool_info.name,
                                    "description": tool_info.description or "",
                                    "parameters": tool_info.inputSchema or {},
                                },
                            }
                            all_tools.append(tool_schema)
            except (OSError, ConnectionError, TimeoutError) as e:
                logger.warning(
                    "Failed to connect to MCP server '%s': %s",
                    config["name"],
                    e,
                )
                continue

        return all_tools

    async def get_mcp_tools_async(self) -> List[Dict[str, Any]]:
        """Get MCP tools, loading them if needed (cached).
        
        Returns:
            List[Dict[str, Any]]: Cached list of MCP tool schemas in OpenAI format.
        """
        if self._mcp_tools_cache is None:
            self._mcp_tools_cache = await self._load_mcp_tools_async()
        return self._mcp_tools_cache or []

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get MCP tools synchronously from cache (or empty list).
        
        Returns:
            List[Dict[str, Any]]: Cached MCP tool schemas or empty list if not yet loaded.
        """
        return self._mcp_tools_cache or []


    async def execute_tool_async(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name. Custom tools run in-process; MCP tools via stdio.
        
        Args:
            name: Name of the tool to execute (str).
            arguments: Dict of tool arguments.
            
        Returns:
            str: JSON-formatted tool result or error message.
        """
        logger.info("Executing tool: %s", name)
        custom_functions = get_custom_function_map()
        if name in custom_functions:
            logger.debug(f"Executing custom tool: {name}")
            func = custom_functions[name]
            result = func(**arguments)
            logger.info(f"Custom tool {name} completed successfully")
            return result

        logger.debug(f"Tool {name} not found in custom tools, checking MCP servers...")
        settings = get_settings()
        env = {"PYTHONPATH": str(PROJECT_ROOT), **os.environ}

        mcp_configs = [
            {
                "name": "jewelryops_mysql",
                "default_cmd": str(MCP_ROOT / "jewelryops_mysql" / "server.py"),
                "config_cmd": settings.mcp_jewelryops_cmd,
            },
            {
                "name": "notion_mock",
                "default_cmd": str(MCP_ROOT / "notion_mock" / "server.py"),
                "config_cmd": settings.mcp_notion_cmd,
            },
            {
                "name": "gmail_mock",
                "default_cmd": str(MCP_ROOT / "gmail_mock" / "server.py"),
                "config_cmd": settings.mcp_gmail_cmd,
            },
        ]

        for config in mcp_configs:
            cmd = config["config_cmd"]
            if not cmd:
                continue

            cmd_parts = cmd.split()
            if len(cmd_parts) < 2:
                continue

            server_params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:],
                env=env,
            )

            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        tool_names = [t.name for t in tools_result.tools]
                        if name in tool_names:
                            logger.info(
                                "Calling MCP tool %s on server %s",
                                name,
                                config["name"],
                            )
                            result = await session.call_tool(name, arguments)
                            if result.content:
                                return result.content[0].text or ""
                            return json.dumps(result, indent=2, default=str)
            except (OSError, ConnectionError, TimeoutError) as e:
                logger.debug(
                    "MCP server %s did not provide tool %s: %s",
                    config["name"],
                    name,
                    e,
                )
                continue

        logger.error(f"Tool {name} not found on any MCP server or custom tools")
        return f"Error: Tool {name} not found"


    async def build_agent_async(self, session: SessionState) -> autogen.ConversableAgent:
        """Create the main JewelryOps support agent with tools attached.
        
        Args:
            session: SessionState containing conversation history and context.
            
        Returns:
            autogen.ConversableAgent: Configured agent ready to process user queries.
        """
        settings = get_settings()

        system_message_parts: List[str] = [settings.agent_system_prompt]

        if session.investigation_summary:
            system_message_parts.append(
                f"\n Prior Investigation Summary\n{session.investigation_summary}"
            )

        if session.messages:
            system_message_parts.append("\n Recent Conversation Context")
            for msg in session.messages[-5:]:
                content = msg["content"]
                content_preview = (
                    content[:200] + "..." if len(content) > 200 else content
                )
                system_message_parts.append(
                    f"{msg['role']}: {content_preview}"
                )

        custom_tools = get_custom_tool_schemas()
        mcp_tools = await self.get_mcp_tools_async()
        all_tools = custom_tools + mcp_tools

        llm_config = {
            "model": settings.model,
            "temperature": settings.temperature,
            "api_key": settings.openai_api_key,
            "api_type": "cerebras",
            "base_url": settings.openai_base_url,
            "functions": all_tools,
        }

        agent = autogen.ConversableAgent(
            name="jewelryops_agent",
            system_message="\n".join(system_message_parts),
            llm_config=llm_config,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=settings.max_iterations,
            code_execution_config=False,
        )

        agent.register_function(function_map=get_custom_function_map())

        return agent


    async def run_agent_stream(
        self, session_id: str, user_message: str
    ) -> AsyncIterator[str]:
        """Run the agent for a given message and yield streaming tokens.
        
        Args:
            session_id: Unique session identifier (str).
            user_message: User query text (str).
            
        Yields:
            str: Individual tokens from agent response including investigation steps and thoughts.
        """
        logger.info(f"Starting agent session: {session_id}")
        logger.debug(f"User message: {user_message[:200]}")
        session = self.get_session(session_id)
        session.messages.append({"role": "user", "content": user_message})

        agent = await self.build_agent_async(session)

        settings_obj = get_settings()
        client = AsyncOpenAI(
            api_key=settings_obj.openai_api_key,
            base_url=settings_obj.openai_base_url,
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": agent.system_message}
        ]
        for msg in session.messages[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        custom_tools = get_custom_tool_schemas()
        mcp_tools = self.get_mcp_tools()
        all_tools = custom_tools + mcp_tools

        full_response = ""
        tool_calls_made: List[Dict[str, Any]] = []

        try:
            stream = await client.chat.completions.create(
                model=settings_obj.model,
                messages=messages,
                tools=all_tools if all_tools else None,
                tool_choice="auto",
                stream=True,
                temperature=settings_obj.temperature,
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            if tool_call_delta.index is not None:
                                while (
                                    len(tool_calls_made)
                                    <= tool_call_delta.index
                                ):
                                    tool_calls_made.append(
                                        {"id": "", "name": "", "arguments": ""}
                                    )
                                tc = tool_calls_made[tool_call_delta.index]
                                if tool_call_delta.id:
                                    tc["id"] = tool_call_delta.id
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tc["name"] = tool_call_delta.function.name
                                    if tool_call_delta.function.arguments:
                                        tc["arguments"] += (
                                            tool_call_delta.function.arguments
                                        )

            tool_names_in_order: List[str] = []
            if tool_calls_made:
                tool_calls_for_message: List[Dict[str, Any]] = []
                for tc in tool_calls_made:
                    if tc["name"]:
                        tool_calls_for_message.append(
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                        )
                        tool_names_in_order.append(tc["name"])

                if tool_calls_for_message:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": full_response or None,
                            "tool_calls": tool_calls_for_message,
                        }
                    )

                for tc in tool_calls_made:
                    if tc["name"]:
                        session.tool_calls_count += 1
                        logger.info(f"Processing tool call #{session.tool_calls_count}: {tc['name']}")
                        try:
                            args = (
                                json.loads(tc["arguments"])
                                if tc["arguments"]
                                else {}
                            )
                            result = await self.execute_tool_async(
                                tc["name"], args
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result,
                                }
                            )
                        except json.JSONDecodeError as e:
                            logger.error(
                                "Invalid tool arguments for %s: %s",
                                tc["name"],
                                e,
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": f"Error: invalid arguments - {e}",
                                }
                            )
                        except (OSError, ConnectionError, TimeoutError, ValueError) as e:
                            logger.error("Error executing tool %s: %s", tc["name"], e)
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": f"Error: {e}",
                                }
                            )

                if tool_names_in_order:
                    logger.info(f"Session {session.session_id}: Tools called in order: {', '.join(tool_names_in_order)}")
                    yield "\nInvestigation Steps:\n"
                    for i, tool_name in enumerate(tool_names_in_order, 1):
                        yield f"{i}. {tool_name}\n"
                else:
                    logger.info(f"Session {session.session_id}: No tools were called for this query")
                    yield (
                        "\nInvestigation Steps:\n"
                        "(no tools were called for this query)\n"
                    )

                summary_messages = messages + [
                    {
                        "role": "system",
                        "content": (
                            "You have already called tools and seen their JSON results. "
                            "Now produce your final thoughts for a human colleague.\n\n"
                            "- Do NOT include raw JSON objects or code blocks in your reply.\n"
                            "- Do NOT paste full tool responses.\n"
                            "- Refer to tools by name (e.g. get_order, get_customer) and "
                            "summarize what they showed in plain language.\n"
                            "- Write concise, readable prose only."
                        ),
                    }
                ]

                final_stream = await client.chat.completions.create(
                    model=settings_obj.model,
                    messages=summary_messages,
                    stream=True,
                    temperature=settings_obj.temperature,
                )

                yield "\nThoughts:\n"
                final_response = ""
                async for chunk in final_stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            final_response += delta.content
                            for ch in delta.content:
                                yield ch

                full_response = final_response

        except (TimeoutError, ConnectionError, ValueError) as e:
            logger.exception("Agent execution failed: %s", e)
            yield f"Error during agent execution: {e}"

        if full_response:
            session.messages.append(
                {"role": "assistant", "content": full_response}
            )
            session.investigation_summary = full_response[:500]



_SERVICE = JewelryOpsAgentService()


def get_session(session_id: str) -> SessionState:
    return _SERVICE.get_session(session_id)


async def get_mcp_tools_async() -> List[Dict[str, Any]]:
    return await _SERVICE.get_mcp_tools_async()


def get_mcp_tools() -> List[Dict[str, Any]]:
    return _SERVICE.get_mcp_tools()


async def run_agent_stream(
    session_id: str, user_message: str
) -> AsyncIterator[str]:
    async for token in _SERVICE.run_agent_stream(session_id, user_message):
        yield token


__all__ = [
    "JewelryOpsAgentService",
    "SessionState",
    "get_session",
    "get_mcp_tools",
    "get_mcp_tools_async",
    "run_agent_stream",
]
