"""Engagement model — central state for an assessment engagement."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EnvironmentInventory(BaseModel):
    aws_account_ids: list[str] = Field(default_factory=list)
    aws_management_account_id: Optional[str] = None
    azure_subscription_ids: list[str] = Field(default_factory=list)
    azure_tenant_id: Optional[str] = None
    # Keys: us | emea | japan | other. Values: list of region strings
    aws_regions: dict = Field(default_factory=dict)
    azure_regions: dict = Field(default_factory=dict)
    known_constraints: list[str] = Field(default_factory=list)


class EngagementConfig(BaseModel):
    engagement_id: str
    client_name: str
    client_slug: str
    regions: list[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    engagement_end_date: Optional[str] = None
    inventory: Optional[EnvironmentInventory] = None
    modules_installed: list[str] = Field(default_factory=list)
    # DD-009: review_complete=False BLOCKS cna report
    review_complete: bool = False
    status: str = "initialized"  # initialized|discovering|analyzing|reviewing|reporting|delivered
