from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)

ARXIV_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")


@dataclass(frozen=True)
class DiscoveredArxivTools:
    search: str | None
    details: str | None


class MCPAgentBridge:
    """Bridge between chat agent logic and MCP arXiv tools."""

    def __init__(
        self,
        server_command: str | None = None,
        server_args: list[str] | None = None,
    ) -> None:
        # Use the active interpreter so this works in local venvs and containers.
        self._server_command = server_command or sys.executable
        self._server_args = server_args or ["-m", "mcp_simple_arxiv"]

    async def discover_tools(self) -> DiscoveredArxivTools:
        """Discover available arXiv tool names exposed by the MCP server."""
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        async with stdio_client(
            StdioServerParameters(command=self._server_command, args=self._server_args)
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await self._discover_tools_from_session(session)

    async def build_research_context(self, user_query: str, max_results: int = 5) -> str:
        """
        Run MCP tool calls for a user research query and return a normalized text block.

        The returned string is designed to be injected into the existing system prompt
        flow without changing the frontend response schema.
        """
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        async with stdio_client(
            StdioServerParameters(command=self._server_command, args=self._server_args)
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                discovered = await self._discover_tools_from_session(session)

                if not discovered.search:
                    raise RuntimeError("No compatible arXiv search tool found on MCP server")

                search_payload = {
                    "query": user_query,
                    "max_results": max(1, min(max_results, 10)),
                    "sort_by": "submitted_date",
                    "sort_order": "descending",
                }
                search_result = await session.call_tool(discovered.search, search_payload)
                search_text = _result_to_text(search_result)

                sections = ["MCP Tool: arXiv search", search_text.strip() or "No search data returned."]

                paper_id = _extract_arxiv_id(user_query)
                if paper_id and discovered.details:
                    details_result = await session.call_tool(discovered.details, {"paper_id": paper_id})
                    details_text = _result_to_text(details_result)
                    sections.extend(
                        [
                            "",
                            f"MCP Tool: arXiv details ({paper_id})",
                            details_text.strip() or "No details data returned.",
                        ]
                    )

                return "\n".join(sections).strip()

    async def _discover_tools_from_session(self, session: "ClientSession") -> DiscoveredArxivTools:
        listed = await session.list_tools()
        tool_names = {tool.name for tool in listed.tools}

        search_tool = _pick_first(tool_names, ["arxiv_search", "search_papers"])
        details_tool = _pick_first(tool_names, ["arxiv_get_details", "get_paper_data"])

        logger.info(
            "mcp_tools_discovered",
            available_tools=sorted(tool_names),
            mapped_search=search_tool,
            mapped_details=details_tool,
        )
        return DiscoveredArxivTools(search=search_tool, details=details_tool)


def _pick_first(candidates: set[str], preferred_names: list[str]) -> str | None:
    for name in preferred_names:
        if name in candidates:
            return name
    return None


def _extract_arxiv_id(text: str) -> str | None:
    match = ARXIV_ID_PATTERN.search(text or "")
    return match.group(0) if match else None


def _result_to_text(result: Any) -> str:
    chunks: list[str] = []

    for item in result.content:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    if result.structuredContent:
        chunks.append(json.dumps(result.structuredContent, ensure_ascii=True, indent=2))

    if result.isError and not chunks:
        chunks.append("MCP tool call returned an error with no text payload.")

    return "\n\n".join(chunks).strip()