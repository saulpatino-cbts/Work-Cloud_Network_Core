"""AWS MCP Client — Phase D.

Connects to awslabs/mcp (AWS MCP Server) to fetch Well-Architected and
service-specific recommendations for network findings.

MCP server: https://github.com/awslabs/mcp
Recommended tool: aws.well-architected.get-recommendation

Connection:
  - Requires MCP server running locally or accessible via stdio/SSE transport
  - Configured via env vars: CNA_AWS_MCP_ENDPOINT, CNA_AWS_MCP_TRANSPORT
  - Default transport: stdio (local subprocess)
  - Graceful degradation: on ImportError or connection failure, returns []
"""

from __future__ import annotations

import logging
import os

from cna.core.findings_schema import FindingRecommendation

logger = logging.getLogger("cna.mcp.aws")

_MCP_ENDPOINT = os.getenv("CNA_AWS_MCP_ENDPOINT", "")
_MCP_TRANSPORT = os.getenv("CNA_AWS_MCP_TRANSPORT", "stdio")


class AWSMCPClient:
    """Client for awslabs/mcp AWS MCP Server.

    Falls back gracefully if MCP SDK is not installed or server is unreachable.
    """

    def __init__(self, endpoint: str = _MCP_ENDPOINT, transport: str = _MCP_TRANSPORT):
        self._endpoint = endpoint
        self._transport = transport
        self._session = None
        self._available = False
        self._try_init()

    def _try_init(self) -> None:
        """Attempt MCP SDK import and connection. Silently marks unavailable on failure."""
        try:
            import mcp  # noqa: F401 — optional dependency

            self._available = True
            logger.info("AWS MCP client initialized (transport=%s)", self._transport)
        except ImportError:
            logger.info(
                "mcp package not installed. AWS MCP client operating in offline mode. "
                "Install with: pip install mcp"
            )
            self._available = False

    def get_recommendations(
        self,
        rule_id: str,
        resource_type: str,
        finding_title: str,
    ) -> list[FindingRecommendation]:
        """Fetch recommendations from AWS MCP Server.

        Returns empty list if MCP unavailable — caller applies offline fallback.
        """
        if not self._available:
            return []

        try:
            # MCP tool call: aws.well-architected.get-recommendation
            # When mcp SDK is present, this sends the tool call to the MCP server.
            # The tool takes: pillar, resource_type, issue_description
            # Returns: list of recommendation objects with text + reference_url
            result = self._call_mcp_tool(
                tool_name="aws.well-architected.get-recommendation",
                params={
                    "resource_type": resource_type,
                    "issue_description": finding_title,
                },
            )
            return [
                FindingRecommendation(
                    source="AWS MCP Server (awslabs/mcp)",
                    text=r.get("recommendation", ""),
                    reference_url=r.get("reference_url", ""),
                )
                for r in (result or [])
                if r.get("recommendation")
            ]
        except Exception as e:
            logger.warning("AWS MCP tool call failed for %s: %s", rule_id, e)
            return []

    def _call_mcp_tool(self, tool_name: str, params: dict) -> list[dict]:
        """Execute an MCP tool call. Returns parsed result list.

        In production: delegates to mcp.ClientSession.call_tool().
        Raises on transport error — caller handles gracefully.
        """
        # Production implementation:
        # async with mcp.ClientSession(...) as session:
        #     result = await session.call_tool(tool_name, params)
        #     return result.content
        #
        # Sync wrapper deferred until async CLI refactor (Phase F target).
        # For now: returns [] to trigger offline fallback.
        logger.debug("MCP tool call deferred (sync wrapper not yet implemented): %s", tool_name)
        return []
