"""Azure MCP Client — Phase D.

Connects to the Microsoft Azure MCP Server to fetch Azure Well-Architected
and Azure Advisor recommendations for network findings.

MCP server: https://github.com/Azure/azure-mcp
Recommended tool: azure.advisor.get-recommendation

Connection:
  - Requires Azure MCP Server running locally or accessible via SSE transport
  - Configured via env vars: CNA_AZURE_MCP_ENDPOINT, CNA_AZURE_MCP_TRANSPORT
  - Default transport: streamable-http (public Azure MCP endpoint default)
  - Graceful degradation: on ImportError or connection failure, returns []
"""

from __future__ import annotations

import logging
import os

from cna.core.findings_schema import FindingRecommendation

logger = logging.getLogger("cna.mcp.azure")

_MCP_ENDPOINT = os.getenv("CNA_AZURE_MCP_ENDPOINT", "")
_MCP_TRANSPORT = os.getenv("CNA_AZURE_MCP_TRANSPORT", "streamable-http")


class AzureMCPClient:
    """Client for Microsoft Azure MCP Server.

    Falls back gracefully if MCP SDK is not installed or server unreachable.
    """

    def __init__(
        self,
        endpoint: str = _MCP_ENDPOINT,
        transport: str = _MCP_TRANSPORT,
    ):
        self._endpoint = endpoint
        self._transport = transport
        self._available = False
        self._try_init()

    def _try_init(self) -> None:
        try:
            import mcp  # noqa: F401 — optional dependency

            self._available = True
            logger.info(
                "Azure MCP client initialized (transport=%s)",
                self._transport,
            )
        except ImportError:
            logger.info(
                "mcp package not installed. Azure MCP client operating in "
                "offline mode. Install with: pip install mcp"
            )
            self._available = False

    def get_recommendations(
        self,
        rule_id: str,
        resource_type: str,
        finding_title: str,
    ) -> list[FindingRecommendation]:
        """Fetch recommendations from Azure MCP Server.

        Returns empty list if MCP is unavailable; the caller applies the
        offline fallback.
        """
        if not self._available:
            return []

        try:
            result = self._call_mcp_tool(
                tool_name="azure.advisor.get-recommendation",
                params={
                    "resource_type": resource_type,
                    "issue_description": finding_title,
                },
            )
            return [
                FindingRecommendation(
                    source="Azure MCP Server (Azure/azure-mcp)",
                    text=r.get("recommendation", ""),
                    reference_url=r.get("reference_url", ""),
                )
                for r in (result or [])
                if r.get("recommendation")
            ]
        except Exception as e:
            logger.warning("Azure MCP tool call failed for %s: %s", rule_id, e)
            return []

    def _call_mcp_tool(self, tool_name: str, params: dict) -> list[dict]:
        """Execute an MCP tool call.

        See AWSMCPClient._call_mcp_tool for implementation notes.
        """
        logger.debug(
            "MCP tool call deferred (sync wrapper not yet implemented): %s",
            tool_name,
        )
        return []
