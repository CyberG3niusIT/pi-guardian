from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


_AGENT_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"
_TOOL_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agent_name: str = Field(
        ...,
        min_length=1,
        pattern=_AGENT_NAME_PATTERN,
        description="Name des registrierten Agents",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("input", "prompt"),
        description="Benutzereingabe für den Agenten",
    )
    preferred_model: str | None = Field(
        default=None,
        min_length=1,
        description="Optional bevorzugtes Ollama-Modell",
    )
    max_steps: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Optionales Limit für Agentenschritte",
    )

    @field_validator("agent_name", "prompt", "preferred_model")
    @classmethod
    def _strip_string_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1, pattern=_TOOL_NAME_PATTERN)
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=1)

    @field_validator("tool_name", "reason")
    @classmethod
    def _strip_required_strings(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1, pattern=_TOOL_NAME_PATTERN)
    success: bool
    output: Any = None
    error: str | None = None

    @field_validator("tool_name")
    @classmethod
    def _strip_tool_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool_name darf nicht leer sein")
        return normalized


class AgentPolicySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_tools: list[str] = Field(default_factory=list)
    allowed_skills: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    read_only: bool = True
    can_propose_actions: bool = False
    can_use_logs: bool = False
    can_use_services: bool = False
    can_use_docker: bool = False
    max_steps: int = Field(default=5, ge=1, le=20)
    max_tool_calls: int | None = Field(default=None, ge=1, le=100)

    @field_validator("allowed_tools")
    @classmethod
    def _normalize_allowed_tools(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for tool_name in value:
            if not isinstance(tool_name, str):
                raise TypeError("allowed_tools muss aus Strings bestehen")
            stripped = tool_name.strip()
            if not stripped:
                raise ValueError("allowed_tools enthält leere Einträge")
            if stripped in normalized:
                continue
            normalized.append(stripped)
        return normalized

    @field_validator("allowed_skills", "allowed_actions")
    @classmethod
    def _normalize_allowed_names(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item_name in value:
            if not isinstance(item_name, str):
                raise TypeError("Listen müssen aus Strings bestehen")
            stripped = item_name.strip()
            if not stripped:
                raise ValueError("Listen enthalten leere Einträge")
            if stripped in normalized:
                continue
            normalized.append(stripped)
        return normalized


class AgentBehaviorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_mode: Literal["summary", "balanced", "deep"] = "balanced"
    response_depth: Literal["concise", "balanced", "detailed"] = "balanced"
    prioritization_style: Literal["risks_first", "ops_first", "systems_first"] = (
        "risks_first"
    )
    uncertainty_behavior: Literal[
        "state_uncertainty",
        "ask_clarification",
        "be_conservative",
    ] = "state_uncertainty"
    risk_sensitivity: Literal["low", "medium", "high"] = "medium"


class AgentPersonalitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["analytical", "neutral", "supportive", "strict"] = "analytical"
    tone: Literal["direct", "formal", "neutral"] = "direct"
    directness: Literal["low", "medium", "high"] = "high"
    verbosity: Literal["short", "balanced", "detailed"] = "balanced"
    technical_strictness: Literal["low", "medium", "high"] = "high"


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool = True
    preferred_model: str | None = None
    max_steps: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    read_only: bool = True
    policy: AgentPolicySettings = Field(default_factory=AgentPolicySettings)
    behavior: AgentBehaviorSettings = Field(default_factory=AgentBehaviorSettings)
    personality: AgentPersonalitySettings = Field(default_factory=AgentPersonalitySettings)
    custom_instruction: str | None = Field(default=None, max_length=2000)

    @field_validator("preferred_model", "custom_instruction")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def _sync_policy(self) -> "AgentSettings":
        policy = self.policy.model_copy()
        policy.read_only = self.read_only
        policy.max_steps = self.max_steps
        policy.allowed_tools = list(dict.fromkeys(policy.allowed_tools))
        policy.allowed_skills = list(dict.fromkeys(policy.allowed_skills))
        policy.allowed_actions = list(dict.fromkeys(policy.allowed_actions))
        self.policy = policy
        return self


class AgentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(..., ge=1)
    action: Literal[
        "model_response",
        "tool_call",
        "tool_result",
        "skill_call",
        "skill_result",
        "action_proposal",
        "final_answer",
        "parse_error",
        "abort",
    ]
    tool_call_or_response: Any
    observation: str | None = None


class AgentPolicySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_only: bool
    allowed_tools: list[str]
    allowed_skills: list[str]
    allowed_actions: list[str]
    can_propose_actions: bool
    can_use_logs: bool
    can_use_services: bool
    can_use_docker: bool
    max_steps: int
    max_tool_calls: int | None = None


class AgentActivitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_run_id: str | None = None
    last_run_at: datetime | None = None
    last_status: Literal["success", "failed"] | None = None
    last_model: str | None = None
    last_activity: str | None = None
    last_result_preview: str | None = None
    last_duration_ms: int | None = None


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, pattern=_AGENT_NAME_PATTERN)
    description: str = Field(..., min_length=1)
    agent_type: Literal["system", "custom", "actor"] = "custom"
    allowed_tools: list[str] = Field(default_factory=list)
    settings: AgentSettings = Field(default_factory=AgentSettings)
    system_prompt: str = Field(..., min_length=1)
    activity: AgentActivitySummary | None = None

    @field_validator("name", "description", "system_prompt")
    @classmethod
    def _strip_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized

    @field_validator("agent_type")
    @classmethod
    def _normalize_agent_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"system", "custom", "actor"}:
            raise ValueError("agent_type muss system, custom oder actor sein")
        return normalized

    @field_validator("allowed_tools")
    @classmethod
    def _normalize_tools(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for tool_name in value:
            if not isinstance(tool_name, str):
                raise TypeError("allowed_tools muss aus Strings bestehen")
            stripped = tool_name.strip()
            if not stripped:
                raise ValueError("allowed_tools enthält leere Einträge")
            if stripped in normalized:
                continue
            normalized.append(stripped)
        return normalized

    @field_validator("settings")
    @classmethod
    def _validate_settings(cls, value: AgentSettings) -> AgentSettings:
        if not value.read_only:
            raise ValueError("read_only Agenten werden aktuell technisch erzwungen")
        return value

    @model_validator(mode="after")
    def _sync_policy(self) -> "AgentDefinition":
        policy = self.settings.policy.model_copy()
        if not policy.allowed_tools:
            policy.allowed_tools = list(self.allowed_tools)
        self.allowed_tools = list(policy.allowed_tools)
        policy.allowed_skills = list(policy.allowed_skills)
        policy.allowed_actions = list(policy.allowed_actions)
        policy.can_use_logs = any(
            tool_name == "router_logs" or tool_name.endswith("_logs")
            for tool_name in policy.allowed_tools
        )
        policy.can_use_services = "service_status" in policy.allowed_tools
        policy.can_use_docker = "docker_status" in policy.allowed_tools
        policy.allowed_skills = list(dict.fromkeys(policy.allowed_skills))
        policy.allowed_actions = list(dict.fromkeys(policy.allowed_actions))
        self.settings.policy = policy
        self.settings.max_steps = policy.max_steps
        self.settings.read_only = policy.read_only
        return self

    @property
    def policy_summary(self) -> AgentPolicySummary:
        return AgentPolicySummary(
            read_only=self.settings.policy.read_only,
            allowed_tools=list(self.settings.policy.allowed_tools),
            allowed_skills=list(self.settings.policy.allowed_skills),
            allowed_actions=list(self.settings.policy.allowed_actions),
            can_propose_actions=self.settings.policy.can_propose_actions,
            can_use_logs=self.settings.policy.can_use_logs,
            can_use_services=self.settings.policy.can_use_services,
            can_use_docker=self.settings.policy.can_use_docker,
            max_steps=self.settings.policy.max_steps,
            max_tool_calls=self.settings.policy.max_tool_calls,
        )


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, pattern=_AGENT_NAME_PATTERN)
    description: str = Field(..., min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    settings: AgentSettings = Field(default_factory=AgentSettings)
    read_only: bool = True

    @field_validator("name", "description")
    @classmethod
    def _strip_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized


class AgentImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    github_url: str | None = None
    agents: list["AgentCreateRequest"] = Field(default_factory=list)

    @field_validator("github_url")
    @classmethod
    def _strip_github_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_agents: list[AgentDefinition] = Field(default_factory=list)
    source: str


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    allowed_tools: list[str] | None = None
    settings: AgentSettings | None = None
    read_only: bool | None = None


class AgentSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool | None = None
    preferred_model: str | None = None
    max_steps: int | None = Field(default=None, ge=1, le=20)
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    policy: AgentPolicySettings | None = None
    behavior: AgentBehaviorSettings | None = None
    personality: AgentPersonalitySettings | None = None
    custom_instruction: str | None = Field(default=None, max_length=2000)
    read_only: bool | None = None

    @field_validator("preferred_model", "custom_instruction")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentRunState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(..., min_length=1, pattern=_AGENT_NAME_PATTERN)
    current_step: int = Field(default=0, ge=0)
    max_steps: int = Field(..., ge=1, le=20)
    tool_call_count: int = Field(default=0, ge=0)
    skill_call_count: int = Field(default=0, ge=0)
    context_history: list[AgentStep] = Field(default_factory=list)
    completed: bool = False


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    agent_name: str = Field(..., min_length=1, pattern=_AGENT_NAME_PATTERN)
    success: bool
    final_answer: str
    steps: list[AgentStep] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    proposed_action: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    used_model: str | None = None
