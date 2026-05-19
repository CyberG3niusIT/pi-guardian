from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.agent_models import AgentPolicySettings


class SkillCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=1)


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1)
    skill_type: str = Field(default="system", min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_template: str | None = None
    preferred_model: str | None = None
    source_url: str | None = None
    read_only: bool = True
    version: str = Field(default="1.0", min_length=1)
    enabled: bool = True

    @field_validator("name", "description", "skill_type", "prompt_template", "preferred_model", "source_url")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized


class SkillCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1)
    prompt_template: str = Field(..., min_length=1)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    preferred_model: str | None = None
    source_url: str | None = None
    version: str = Field(default="1.0", min_length=1)
    read_only: bool = True

    @field_validator("name", "description", "prompt_template", "preferred_model", "source_url", "version")
    @classmethod
    def _strip_create_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized


class SkillUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    prompt_template: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    preferred_model: str | None = None
    source_url: str | None = None
    version: str | None = None

    @field_validator("description", "prompt_template", "preferred_model", "source_url", "version")
    @classmethod
    def _strip_update_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Wert darf nicht leer sein")
        return normalized


class SkillImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    github_url: str | None = None
    skills: list[SkillCreateRequest] = Field(default_factory=list)

    @field_validator("github_url")
    @classmethod
    def _strip_github_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SkillImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported_skills: list[SkillDefinition] = Field(default_factory=list)
    source: str


class SkillResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    success: bool
    output: Any = None
    error: str | None = None


class SkillExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(..., min_length=1)
    skill_name: str = Field(..., min_length=1)
    step_number: int = Field(..., ge=1)
    request_id: str | None = None
    allowed_skills: list[str] = Field(default_factory=list)
    policy: AgentPolicySettings = Field(default_factory=AgentPolicySettings)
