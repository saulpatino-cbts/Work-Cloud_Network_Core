"""Universal findings schema.

DD-002: observed_state is REQUIRED — only what was discovered, no assumptions.
DD-003: recommendation sourced from MCP servers, not custom prompts.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class FrameworkMapping(BaseModel):
    framework: str    # e.g. "CIS AWS Foundations Benchmark"
    version: str      # e.g. "3.0"
    control_id: str   # e.g. "5.1"
    control_name: str
    alignment: str    # Aligned | Partial | Gap


class Finding(BaseModel):
    id: str
    severity: str        # critical | high | medium | low | informational
    platform: str        # aws | azure | both
    region: str
    category: str
    title: str
    description: str
    observed_state: str  # DD-002: ONLY what was discovered — no assumptions
    affected_resources: list[str] = Field(default_factory=list)
    framework_mappings: list[FrameworkMapping] = Field(default_factory=list)
    data_confidence: str = "HIGH"   # HIGH | MEDIUM | LOW
    recommendation_source: str | None = None  # MCP server reference URL
    recommendation: str | None = None         # From MCP — not our opinion
    human_reviewed: bool = False                 # DD-009: must be True before report
    human_notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
