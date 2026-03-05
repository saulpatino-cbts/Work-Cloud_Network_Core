"""Universal findings schema.

DD-002: observed_state is REQUIRED — only what was discovered, no assumptions.
DD-003: recommendation sourced from MCP servers, not custom prompts.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


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
    recommendation_source: Optional[str] = None  # MCP server reference URL
    recommendation: Optional[str] = None         # From MCP — not our opinion
    human_reviewed: bool = False                 # DD-009: must be True before report
    human_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
