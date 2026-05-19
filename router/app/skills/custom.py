from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.skill_models import SkillCreateRequest, SkillDefinition, SkillResult
from app.router.classifier import select_model_for_prompt
from app.router.ollama_client import generate_with_ollama
from app.skills.base import BaseSkill


class GenericSkillInput(BaseModel):
    model_config = ConfigDict(extra="allow")


class GenericSkillOutput(BaseModel):
    model_config = ConfigDict(extra="allow")


@dataclass(slots=True)
class CustomSkillPayload:
    name: str
    description: str
    prompt_template: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    preferred_model: str | None = None
    source_url: str | None = None
    version: str = "1.0"
    skill_type: str = "custom"


def _validate_schema_payload(payload: Any, schema: dict[str, Any], *, label: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} muss ein JSON-Objekt sein")

    schema_type = schema.get("type", "object")
    if schema_type != "object":
        raise ValueError(f"{label} unterstützt aktuell nur type=object")

    required = schema.get("required", [])
    if isinstance(required, list):
        for key in required:
            if key not in payload:
                raise ValueError(f"{label}: Pflichtfeld fehlt: {key}")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return

    for key, rules in properties.items():
        if key not in payload or not isinstance(rules, dict):
            continue
        _validate_value_type(payload[key], rules, label=f"{label}.{key}")


def _validate_value_type(value: Any, rules: dict[str, Any], *, label: str) -> None:
    expected_type = rules.get("type")
    if expected_type is None:
        return
    if expected_type == "string" and not isinstance(value, str):
        raise ValueError(f"{label} muss vom Typ string sein")
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{label} muss vom Typ integer sein")
    if expected_type == "number" and not isinstance(value, (int, float)):
        raise ValueError(f"{label} muss vom Typ number sein")
    if expected_type == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{label} muss vom Typ boolean sein")
    if expected_type == "array":
        if not isinstance(value, list):
            raise ValueError(f"{label} muss vom Typ array sein")
        item_rules = rules.get("items")
        if isinstance(item_rules, dict):
            for index, item in enumerate(value):
                _validate_value_type(item, item_rules, label=f"{label}[{index}]")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{label} muss vom Typ object sein")
        _validate_schema_payload(value, rules, label=label)


def _extract_json_object(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Skill-Antwort ist leer")

    decoder = json.JSONDecoder()
    start = stripped.find("{")
    if start < 0:
        raise ValueError("Skill-Antwort enthält kein JSON-Objekt")
    try:
        payload, _ = decoder.raw_decode(stripped[start:])
    except json.JSONDecodeError as exc:
        raise ValueError("Skill-Antwort enthält ungültiges JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Skill-Antwort muss ein JSON-Objekt sein")
    return payload


def _render_template(template: str, arguments: dict[str, Any]) -> str:
    render_context = {key: json.dumps(value, ensure_ascii=False) for key, value in arguments.items()}
    render_context["input_json"] = json.dumps(arguments, ensure_ascii=False, indent=2, default=str)
    try:
        return template.format_map(_SafeDict(render_context))
    except Exception as exc:
        raise ValueError(f"Prompt-Template konnte nicht gerendert werden: {exc}") from exc


class _SafeDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class CustomPromptSkill(BaseSkill):
    input_schema = GenericSkillInput
    output_schema = GenericSkillOutput
    read_only = True

    def __init__(self, payload: CustomSkillPayload) -> None:
        self.name = payload.name
        self.description = payload.description
        self.allowed_tools = []
        self.version = payload.version
        self.skill_type = payload.skill_type
        self.prompt_template = payload.prompt_template
        self.input_schema_json = payload.input_schema or {"type": "object"}
        self.output_schema_json = payload.output_schema or {"type": "object"}
        self.preferred_model = payload.preferred_model
        self.source_url = payload.source_url

    def validate_arguments(self, arguments: dict[str, Any] | None) -> BaseModel:
        payload = arguments or {}
        _validate_schema_payload(payload, self.input_schema_json, label="Skill-Eingabe")
        return GenericSkillInput.model_validate(payload)

    def execute(self, validated_input: BaseModel) -> SkillResult:
        arguments = validated_input.model_dump(mode="json")
        rendered_instruction = _render_template(self.prompt_template, arguments)
        prompt = "\n".join(
            [
                "You are executing a registered PI Guardian custom skill.",
                f"Skill name: {self.name}",
                f"Description: {self.description}",
                "Return only one JSON object that matches the required output schema.",
                f"Output schema: {json.dumps(self.output_schema_json, ensure_ascii=False)}",
                f"Input arguments: {json.dumps(arguments, ensure_ascii=False)}",
                "Skill instruction:",
                rendered_instruction,
            ]
        )
        model_name = self.preferred_model or select_model_for_prompt(
            f"{self.description}\n{rendered_instruction}"
        )
        response = asyncio.run(
            generate_with_ollama(
                model=model_name,
                prompt=prompt,
                request_id=str(uuid.uuid4()),
                stream=False,
            )
        )
        raw_output = str(response.get("response", ""))
        output_payload = _extract_json_object(raw_output)
        _validate_schema_payload(output_payload, self.output_schema_json, label="Skill-Ausgabe")
        return SkillResult(skill_name=self.name, success=True, output=output_payload)


def payload_to_skill_definition(payload: CustomSkillPayload) -> SkillDefinition:
    return SkillDefinition(
        name=payload.name,
        description=payload.description,
        skill_type=payload.skill_type,
        allowed_tools=[],
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        prompt_template=payload.prompt_template,
        preferred_model=payload.preferred_model,
        source_url=payload.source_url,
        read_only=True,
        version=payload.version,
        enabled=True,
    )


def request_to_custom_skill_payload(
    request: SkillCreateRequest,
    *,
    skill_type: str = "custom",
) -> CustomSkillPayload:
    return CustomSkillPayload(
        name=request.name,
        description=request.description,
        prompt_template=request.prompt_template,
        input_schema=request.input_schema,
        output_schema=request.output_schema,
        preferred_model=request.preferred_model,
        source_url=request.source_url,
        version=request.version,
        skill_type=skill_type,
    )
