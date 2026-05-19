from __future__ import annotations

import logging
from typing import Iterable

from app.actions.registry import registry as action_registry
from app.agents.prompt_builder import build_system_prompt
from app.agents.store import load_agent_records, save_agent_records
from app.models.agent_models import (
    AgentCreateRequest,
    AgentDefinition,
    AgentPolicySettings,
    AgentSettings,
    AgentSettingsUpdate,
    AgentUpdateRequest,
)
from app.skills.registry import registry as skill_registry
from app.tools.registry import registry as tool_registry

logger = logging.getLogger(__name__)


def _policy_for_tools(
    *,
    allowed_tools: list[str],
    allowed_skills: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    read_only: bool = True,
    can_propose_actions: bool = False,
    max_steps: int = 5,
    can_use_logs: bool | None = None,
    can_use_services: bool | None = None,
    can_use_docker: bool | None = None,
    max_tool_calls: int | None = None,
) -> AgentPolicySettings:
    inferred_can_use_logs = any(
        tool_name == "router_logs" or tool_name.endswith("_logs")
        for tool_name in allowed_tools
    )
    inferred_can_use_services = "service_status" in allowed_tools
    inferred_can_use_docker = "docker_status" in allowed_tools
    return AgentPolicySettings(
        allowed_tools=allowed_tools,
        allowed_skills=allowed_skills or [],
        allowed_actions=allowed_actions or [],
        read_only=read_only,
        can_propose_actions=can_propose_actions,
        can_use_logs=inferred_can_use_logs if can_use_logs is None else can_use_logs,
        can_use_services=(
            inferred_can_use_services if can_use_services is None else can_use_services
        ),
        can_use_docker=inferred_can_use_docker if can_use_docker is None else can_use_docker,
        max_steps=max_steps,
        max_tool_calls=max_tool_calls,
    )


def _system_supervisor_template() -> AgentDefinition:
    return AgentDefinition(
        name="guardian_supervisor",
        description=(
            "Read-only Analyse-Agent, der System-, Docker- und Service-Zustände "
            "zusammenfasst und Maßnahmen nur empfiehlt."
        ),
        agent_type="system",
        allowed_tools=["system_status", "docker_status", "service_status"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=5,
            timeout_seconds=90,
            read_only=True,
            policy=_policy_for_tools(
                allowed_tools=["system_status", "docker_status", "service_status"],
                allowed_skills=[
                    "system_snapshot",
                    "service_triage",
                    "router_log_review",
                    "docker_snapshot",
                    "incident_summary",
                    "agent_health_check",
                ],
                allowed_actions=[],
                read_only=True,
                max_steps=5,
                can_use_services=True,
                can_use_docker=True,
            ),
            behavior={
                "analysis_mode": "deep",
                "response_depth": "detailed",
                "prioritization_style": "risks_first",
                "uncertainty_behavior": "state_uncertainty",
                "risk_sensitivity": "high",
            },
            personality={
                "style": "analytical",
                "tone": "direct",
                "directness": "high",
                "verbosity": "balanced",
                "technical_strictness": "high",
            },
            custom_instruction=(
                "Systemzustände zusammenfassen, Auffälligkeiten priorisieren und "
                "konkrete Maßnahmen nur empfehlen, nie ausführen."
            ),
        ),
        system_prompt="pending",
    )


def _service_diagnose_template() -> AgentDefinition:
    return AgentDefinition(
        name="service_diagnose",
        description=(
            "Read-only Diagnose-Agent, der systemd-Dienste bewertet, "
            "Problemzustände priorisiert und vorsichtige Empfehlungen gibt."
        ),
        agent_type="system",
        allowed_tools=["service_status", "system_status"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=5,
            timeout_seconds=90,
            read_only=True,
            policy=_policy_for_tools(
                allowed_tools=["service_status", "system_status"],
                allowed_skills=[
                    "system_snapshot",
                    "service_triage",
                    "service_log_correlation",
                ],
                allowed_actions=[],
                read_only=True,
                max_steps=5,
                can_use_services=True,
            ),
            behavior={
                "analysis_mode": "deep",
                "response_depth": "detailed",
                "prioritization_style": "ops_first",
                "uncertainty_behavior": "state_uncertainty",
                "risk_sensitivity": "high",
            },
            personality={
                "style": "analytical",
                "tone": "direct",
                "directness": "high",
                "verbosity": "balanced",
                "technical_strictness": "high",
            },
            custom_instruction=(
                "systemd-Dienste bewerten, kritische Zustände priorisieren, "
                "wahrscheinliche Ursachen benennen und nur vorsichtige "
                "Handlungsempfehlungen geben. Keine Änderungen ausführen."
            ),
        ),
        system_prompt="pending",
    )


def _log_analyst_template() -> AgentDefinition:
    return AgentDefinition(
        name="log_analyst",
        description=(
            "Read-only Analyse-Agent, der Router-Logs auf Fehlerbilder, Muster "
            "und wahrscheinliche Ursachen prüft."
        ),
        agent_type="system",
        allowed_tools=["router_logs", "service_status", "system_status"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=5,
            timeout_seconds=90,
            read_only=True,
            policy=_policy_for_tools(
                allowed_tools=["router_logs", "service_status", "system_status"],
                allowed_skills=[
                    "router_log_review",
                    "service_log_correlation",
                    "system_snapshot",
                    "service_triage",
                ],
                allowed_actions=[],
                read_only=True,
                max_steps=5,
                can_use_logs=True,
                can_use_services=True,
            ),
            behavior={
                "analysis_mode": "deep",
                "response_depth": "detailed",
                "prioritization_style": "risks_first",
                "uncertainty_behavior": "state_uncertainty",
                "risk_sensitivity": "high",
            },
            personality={
                "style": "analytical",
                "tone": "direct",
                "directness": "high",
                "verbosity": "balanced",
                "technical_strictness": "high",
            },
            custom_instruction=(
                "Definierte Router-Logs analysieren, Fehlerbilder und Muster "
                "erkennen, Priorität einschätzen, wahrscheinliche Ursachen "
                "benennen und nur vorsichtige Handlungsempfehlungen geben. "
                "Keine Änderungen ausführen."
            ),
        ),
        system_prompt="pending",
    )


def _service_operator_template() -> AgentDefinition:
    return AgentDefinition(
        name="service_operator",
        description=(
            "Read-only Aktor-Agent, der Service-Probleme einordnet und sichere "
            "Standard-Aktionen nur vorschlägt."
        ),
        agent_type="actor",
        allowed_tools=["system_status", "service_status", "router_logs"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=5,
            timeout_seconds=90,
            read_only=True,
            policy=_policy_for_tools(
                allowed_tools=["system_status", "service_status", "router_logs"],
                allowed_skills=[
                    "system_snapshot",
                    "service_triage",
                    "service_log_correlation",
                    "incident_summary",
                    "agent_health_check",
                ],
                allowed_actions=["restart_service", "rerun_health_check"],
                read_only=True,
                can_propose_actions=True,
                max_steps=5,
                can_use_logs=True,
                can_use_services=True,
            ),
            behavior={
                "analysis_mode": "deep",
                "response_depth": "balanced",
                "prioritization_style": "ops_first",
                "uncertainty_behavior": "be_conservative",
                "risk_sensitivity": "high",
            },
            personality={
                "style": "strict",
                "tone": "direct",
                "directness": "high",
                "verbosity": "balanced",
                "technical_strictness": "high",
            },
            custom_instruction=(
                "Service-Probleme einordnen, passende sichere Standardaktion "
                "nur vorschlagen, nie automatisch ausführen. Freigabe ist immer "
                "erforderlich."
            ),
        ),
        system_prompt="pending",
    )


def _kids_controller_supervisor_template() -> AgentDefinition:
    return AgentDefinition(
        name="kids_controller_supervisor",
        description=(
            "Read-only Supervisor-Agent für Kids-Controller-Beobachtungen mit Fokus "
            "auf häufig wiederkehrende Aufstellungen und klare Rückmeldungen."
        ),
        agent_type="system",
        allowed_tools=["system_status"],
        settings=AgentSettings(
            active=True,
            preferred_model=None,
            max_steps=5,
            timeout_seconds=45,
            read_only=True,
            policy=_policy_for_tools(
                allowed_tools=["system_status"],
                allowed_skills=["kids_controller_repetition_review"],
                allowed_actions=[],
                read_only=True,
                max_steps=5,
            ),
            behavior={
                "analysis_mode": "balanced",
                "response_depth": "balanced",
                "prioritization_style": "risks_first",
                "uncertainty_behavior": "state_uncertainty",
                "risk_sensitivity": "high",
            },
            personality={
                "style": "analytical",
                "tone": "direct",
                "directness": "high",
                "verbosity": "balanced",
                "technical_strictness": "high",
            },
            custom_instruction=(
                "Bewerte Kids-Controller-Beobachtungen knapp und klar. Nutze fuer "
                "Wiederholungsbewertungen direkt den Skill "
                "'kids_controller_repetition_review' und antworte danach ohne "
                "weitere Zwischenschritte. Wenn eine Aufstellung in letzter Zeit "
                "sehr oft vorkam, sage das explizit."
            ),
        ),
        system_prompt="pending",
    )


def _materialize(definition: AgentDefinition) -> AgentDefinition:
    return definition.model_copy(
        update={"system_prompt": build_system_prompt(definition)}
    )


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        self._load_defaults()
        self._load_persisted()

    def _load_defaults(self) -> None:
        for template in (
            _system_supervisor_template(),
            _service_diagnose_template(),
            _log_analyst_template(),
            _service_operator_template(),
            _kids_controller_supervisor_template(),
        ):
            agent = _materialize(template)
            self._agents[agent.name] = agent

    def _load_persisted(self) -> None:
        for agent in load_agent_records():
            existing = self._agents.get(agent.name)
            if existing is not None and existing.agent_type in {"system", "actor"}:
                continue
            self._agents[agent.name] = self._validate_and_materialize(agent)

    def reload_persisted(self) -> None:
        self._load_defaults()
        self._load_persisted()

    def _persist(self) -> None:
        save_agent_records(self._agents.values())

    def _validate_allowed_tools(self, allowed_tools: Iterable[str]) -> list[str]:
        normalized = tool_registry.ensure_allowed(allowed_tools)
        for tool_name in normalized:
            tool = tool_registry.get(tool_name)
            if tool is None:
                raise ValueError(f"Unbekanntes Tool in Agent-Definition: {tool_name}")
            if not tool.read_only:
                raise ValueError(f"Nicht-lesendes Tool ist nicht erlaubt: {tool_name}")
        return normalized

    def _validate_allowed_skills(self, allowed_skills: Iterable[str]) -> list[str]:
        normalized = skill_registry.ensure_allowed(allowed_skills)
        for skill_name in normalized:
            skill = skill_registry.get(skill_name)
            if skill is None:
                raise ValueError(f"Unbekannter Skill in Agent-Definition: {skill_name}")
            if not skill.read_only:
                raise ValueError(f"Nicht-lesender Skill ist nicht erlaubt: {skill_name}")
        return normalized

    def _validate_allowed_actions(self, allowed_actions: Iterable[str]) -> list[str]:
        normalized = action_registry.ensure_allowed(allowed_actions)
        for action_name in normalized:
            action = action_registry.get(action_name)
            if action is None:
                raise ValueError(f"Unbekannte Action in Agent-Definition: {action_name}")
            if action.read_only:
                raise ValueError(f"Read-only Action ist nicht erlaubt: {action_name}")
        return normalized

    def _validate_and_materialize(self, definition: AgentDefinition) -> AgentDefinition:
        if not definition.settings.read_only:
            raise ValueError("read_only Agenten werden aktuell technisch erzwungen")

        validated_definition = definition.model_copy(
            update={
                "allowed_tools": self._validate_allowed_tools(definition.allowed_tools),
                "settings": definition.settings.model_copy(update={"read_only": True}),
            }
        )
        definition = AgentDefinition.model_validate(validated_definition.model_dump(mode="json"))
        policy = definition.settings.policy
        if policy.read_only is False:
            raise ValueError("read_only Agenten werden aktuell technisch erzwungen")
        if not policy.allowed_tools:
            raise ValueError("Agenten-Policy benötigt erlaubte Tools")

        policy.allowed_tools = self._validate_allowed_tools(policy.allowed_tools)
        policy.allowed_skills = self._validate_allowed_skills(policy.allowed_skills)
        policy.allowed_actions = self._validate_allowed_actions(policy.allowed_actions)

        if policy.allowed_actions and not policy.can_propose_actions:
            raise ValueError("Action-Policies setzen can_propose_actions voraus")

        if not policy.can_use_logs and any(
            tool_name == "router_logs" or tool_name.endswith("_logs")
            for tool_name in definition.allowed_tools
        ):
            raise ValueError("Tool logs sind laut Policy nicht erlaubt")
        if not policy.can_use_services and "service_status" in definition.allowed_tools:
            raise ValueError("Service-Tools sind laut Policy nicht erlaubt")
        if not policy.can_use_docker and "docker_status" in definition.allowed_tools:
            raise ValueError("Docker-Tools sind laut Policy nicht erlaubt")

        if policy.allowed_tools != definition.allowed_tools:
            definition = definition.model_copy(update={"allowed_tools": list(policy.allowed_tools)})
        definition = definition.model_copy(
            update={
                "settings": definition.settings.model_copy(
                    update={
                        "policy": policy,
                        "read_only": True,
                        "max_steps": policy.max_steps,
                    }
                )
            }
        )
        return _materialize(definition)

    def list(self) -> list[AgentDefinition]:
        return [self._agents[name] for name in sorted(self._agents)]

    def get(self, agent_name: str) -> AgentDefinition | None:
        return self._agents.get(agent_name)

    def create(self, payload: AgentCreateRequest) -> AgentDefinition:
        if payload.name in self._agents:
            raise ValueError(f"Agent existiert bereits: {payload.name}")

        settings = payload.settings.model_copy()
        if not settings.policy.allowed_tools:
            settings.policy = _policy_for_tools(
                allowed_tools=self._validate_allowed_tools(payload.allowed_tools),
                allowed_skills=list(settings.policy.allowed_skills),
                allowed_actions=list(settings.policy.allowed_actions),
                read_only=settings.read_only,
                can_propose_actions=settings.policy.can_propose_actions,
                max_steps=settings.max_steps,
            )
        definition = AgentDefinition(
            name=payload.name,
            description=payload.description,
            agent_type="custom",
            allowed_tools=self._validate_allowed_tools(payload.allowed_tools),
            settings=settings.model_copy(update={"read_only": payload.read_only}),
            system_prompt="pending",
        )
        created = self._validate_and_materialize(definition)
        self._agents[created.name] = created
        self._persist()
        logger.info("Agent erstellt: %s", created.name)
        return created

    def update(self, agent_name: str, payload: AgentUpdateRequest) -> AgentDefinition:
        current = self._agents.get(agent_name)
        if current is None:
            raise ValueError(f"Agent nicht gefunden: {agent_name}")

        updates = payload.model_dump(exclude_unset=True)
        if current.agent_type == "system":
            allowed_keys = {"description", "settings"}
        else:
            allowed_keys = {"description", "allowed_tools", "settings", "read_only"}

        for key in list(updates):
            if key not in allowed_keys:
                raise ValueError(f"Feld nicht bearbeitbar: {key}")

        next_definition = current.model_copy(deep=True)
        if "description" in updates and updates["description"] is not None:
            next_definition.description = updates["description"].strip()
        if "allowed_tools" in updates and updates["allowed_tools"] is not None:
            validated_tools = self._validate_allowed_tools(updates["allowed_tools"])
            next_definition.allowed_tools = validated_tools
            next_definition.settings.policy = next_definition.settings.policy.model_copy(
                update={"allowed_tools": validated_tools}
            )
        if "settings" in updates and updates["settings"] is not None:
            if current.agent_type == "system":
                incoming_settings = updates["settings"]
                if "policy" in incoming_settings.model_fields_set and incoming_settings.policy != current.settings.policy:
                    raise ValueError("System-Agenten dürfen ihre Policy nicht ändern")
                if "read_only" in incoming_settings.model_fields_set and incoming_settings.read_only != current.settings.read_only:
                    raise ValueError("System-Agenten dürfen read_only nicht ändern")
                if "max_steps" in incoming_settings.model_fields_set and incoming_settings.max_steps != current.settings.max_steps:
                    raise ValueError("System-Agenten dürfen max_steps nicht ändern")
                next_definition.settings = incoming_settings.model_copy(
                    update={
                        "policy": current.settings.policy,
                        "read_only": current.settings.read_only,
                        "max_steps": current.settings.max_steps,
                    }
                )
            else:
                next_definition.settings = updates["settings"]
        if "read_only" in updates and updates["read_only"] is not None:
            next_definition.settings.read_only = updates["read_only"]

        if not next_definition.settings.read_only:
            raise ValueError("read_only Agenten werden aktuell technisch erzwungen")

        next_definition.agent_type = current.agent_type if current.agent_type == "system" else "custom"

        updated = self._validate_and_materialize(next_definition)
        self._agents[agent_name] = updated
        self._persist()
        logger.info("Agent aktualisiert: %s", agent_name)
        return updated

    def update_settings(
        self,
        agent_name: str,
        payload: AgentSettingsUpdate,
    ) -> AgentDefinition:
        current = self._agents.get(agent_name)
        if current is None:
            raise ValueError(f"Agent nicht gefunden: {agent_name}")

        merged_settings = current.settings.model_copy(
            update=payload.model_dump(exclude_unset=True, exclude_none=True)
        )
        if current.agent_type == "system":
            if "policy" in payload.model_fields_set and payload.policy != current.settings.policy:
                raise ValueError("System-Agenten dürfen ihre Policy nicht ändern")
            if "read_only" in payload.model_fields_set and payload.read_only != current.settings.read_only:
                raise ValueError("System-Agenten dürfen read_only nicht ändern")
            if "max_steps" in payload.model_fields_set and payload.max_steps != current.settings.max_steps:
                raise ValueError("System-Agenten dürfen max_steps nicht ändern")
            merged_settings = merged_settings.model_copy(
                update={
                    "policy": current.settings.policy,
                    "read_only": current.settings.read_only,
                    "max_steps": current.settings.max_steps,
                }
            )
        if not merged_settings.read_only:
            raise ValueError("read_only Agenten werden aktuell technisch erzwungen")

        updated = current.model_copy(update={"settings": merged_settings})
        updated = self._validate_and_materialize(updated)
        self._agents[agent_name] = updated
        self._persist()
        logger.info("Agent-Settings aktualisiert: %s", agent_name)
        return updated

    def enable(self, agent_name: str) -> AgentDefinition:
        return self.update_settings(agent_name, AgentSettingsUpdate(active=True))

    def disable(self, agent_name: str) -> AgentDefinition:
        return self.update_settings(agent_name, AgentSettingsUpdate(active=False))

    def delete(self, agent_name: str) -> None:
        current = self._agents.get(agent_name)
        if current is None:
            raise ValueError(f"Agent nicht gefunden: {agent_name}")
        if current.agent_type in {"system", "actor"}:
            raise ValueError("System- und Aktor-Agenten dürfen nicht gelöscht werden")
        del self._agents[agent_name]
        self._persist()
        logger.info("Agent gelöscht: %s", agent_name)


registry = AgentRegistry()


def register_agent(definition: AgentDefinition) -> None:
    registry._agents[definition.name] = registry._validate_and_materialize(definition)
    registry._persist()


def get_agent(agent_name: str) -> AgentDefinition | None:
    return registry.get(agent_name)


def list_agents() -> list[AgentDefinition]:
    return registry.list()


def create_agent(payload: AgentCreateRequest) -> AgentDefinition:
    return registry.create(payload)


def update_agent(agent_name: str, payload: AgentUpdateRequest) -> AgentDefinition:
    return registry.update(agent_name, payload)


def update_agent_settings(
    agent_name: str,
    payload: AgentSettingsUpdate,
) -> AgentDefinition:
    return registry.update_settings(agent_name, payload)


def enable_agent(agent_name: str) -> AgentDefinition:
    return registry.enable(agent_name)


def disable_agent(agent_name: str) -> AgentDefinition:
    return registry.disable(agent_name)


def delete_agent(agent_name: str) -> None:
    registry.delete(agent_name)
