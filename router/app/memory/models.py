from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    agent_type: str = Field(index=True)
    description: str
    enabled: bool = Field(default=True)
    read_only: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentSettingsRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_name: str = Field(index=True, unique=True)
    preferred_model: str | None = None
    max_steps: int = Field(default=5)
    timeout_seconds: int | None = None
    behavior: str = Field(default="{}")
    personality: str = Field(default="{}")
    policy: str = Field(default="{}")
    custom_instruction: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SkillRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    skill_type: str = Field(default="system", index=True)
    description: str
    allowed_tools: str = Field(default="[]")
    input_schema: str = Field(default="{}")
    output_schema: str = Field(default="{}")
    prompt_template: str | None = None
    preferred_model: str | None = None
    source_url: str | None = None
    read_only: bool = Field(default=True)
    version: str = Field(default="1.0")
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SkillRunRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step_number: int = Field(index=True)
    skill_name: str = Field(index=True)
    arguments: str = Field(default="{}")
    reason: str = Field(default="")
    success: bool = Field(default=False)
    output: str = Field(default="")
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class ActionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str
    allowed_targets: str = Field(default="[]")
    input_schema: str = Field(default="{}")
    output_schema: str = Field(default="{}")
    read_only: bool = Field(default=False)
    requires_approval: bool = Field(default=True)
    version: str = Field(default="1.0")
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentRunRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    agent_name: str = Field(index=True)
    input: str
    used_model: str | None = None
    success: bool = Field(default=False)
    final_answer: str = Field(default="")
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None


class AgentStepRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step_number: int = Field(index=True)
    action_type: str = Field(index=True)
    observation: str | None = None
    raw_payload: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.now)


class ToolCallRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step_number: int = Field(index=True)
    tool_name: str = Field(index=True)
    arguments: str = Field(default="{}")
    reason: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)


class ToolResultRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step_number: int = Field(index=True)
    tool_name: str = Field(index=True)
    success: bool = Field(default=False)
    output: str = Field(default="")
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class ActionProposalRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: str = Field(index=True, unique=True)
    run_id: str | None = Field(default=None, index=True)
    agent_name: str = Field(index=True)
    action_name: str = Field(index=True)
    arguments: str = Field(default="{}")
    reason: str = Field(default="")
    target: str | None = None
    requires_approval: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class ActionExecutionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: str = Field(index=True)
    run_id: str | None = Field(default=None, index=True)
    action_name: str = Field(index=True)
    approved: bool = Field(default=False)
    success: bool = Field(default=False)
    output: str = Field(default="")
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class ApprovalRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: str = Field(index=True)
    approved_by: str | None = None
    approved_at: datetime = Field(default_factory=datetime.now)
    decision: str = Field(default="approved")
    comment: str | None = None


class IncidentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    summary: str = Field(default="")
    severity: str = Field(default="medium", index=True)
    status: str = Field(default="open", index=True)
    related_run_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class IncidentFindingRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(index=True)
    source_type: str = Field(index=True)
    source_ref: str = Field(index=True)
    finding_type: str = Field(default="")
    content: str = Field(default="")
    confidence: float = Field(default=0.0)


class KnowledgeEntryRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    pattern: str = Field(default="")
    probable_cause: str = Field(default="")
    recommended_checks: str = Field(default="")
    recommended_actions: str = Field(default="")
    confidence: float = Field(default=0.0)
    confirmed: bool = Field(default=False, index=True)
    source: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class FeedbackEntryRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    related_run_id: str | None = Field(default=None, index=True)
    related_incident_id: int | None = Field(default=None, index=True)
    verdict: str = Field(default="")
    comment: str = Field(default="")
    created_by: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)


class AgentMemoryEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_name: str = Field(index=True)
    memory_type: str = Field(index=True)  # "finding", "failure", "feedback", "instruction"
    content: str  # Short text injected into prompt, keep under 300 chars
    active: bool = Field(default=True, index=True)
    priority: int = Field(default=3)  # 1-5, higher shown first (5=critical)
    source_run_id: str | None = Field(default=None, index=True)
    times_confirmed: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
