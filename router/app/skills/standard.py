from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.skill_models import SkillResult
from app.skills.base import BaseSkill
from app.skills.registry import register_builtin_skill
from app.tools.executor import ToolExecutor
from app.skills.registry import list_skill_names


class EmptySkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemSnapshotOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: dict[str, Any]
    status: Literal["ok", "warning", "error"]
    summary: str


class SystemSnapshotSkill(BaseSkill):
    name = "system_snapshot"
    description = "Normierter Systemzustand auf Basis von system_status."
    allowed_tools = ["system_status"]
    input_schema = SystemSnapshotInput
    output_schema = SystemSnapshotOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        del validated_input
        tool_executor = ToolExecutor(timeout_seconds=10)
        from app.models.tool_models import ToolExecutionContext

        context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="system_status",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )
        result = asyncio.run(
            tool_executor.execute(
                "system_status",
                {},
                allowed_tools=list(self.allowed_tools),
                context=context,
            )
        )
        if not result.success:
            return SkillResult(skill_name=self.name, success=False, error=result.error)

        output = SystemSnapshotOutput(
            system=result.output or {},
            status="ok",
            summary="Systemzustand wurde erfolgreich normalisiert.",
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))


class ServiceTriageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")


class ServiceTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str
    severity: Literal["low", "medium", "high", "critical"]
    state: dict[str, Any]
    likely_causes: list[str]
    recommendations: list[str]


class ServiceTriageSkill(BaseSkill):
    name = "service_triage"
    description = "Dienstzustände fachlich einordnen."
    allowed_tools = ["service_status", "system_status"]
    input_schema = ServiceTriageInput
    output_schema = ServiceTriageOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        from app.models.tool_models import ToolExecutionContext

        tool_executor = ToolExecutor(timeout_seconds=10)
        service_context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="service_status",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )
        service_result = asyncio.run(
            tool_executor.execute(
                "service_status",
                {"service_name": getattr(validated_input, "service_name")},
                allowed_tools=list(self.allowed_tools),
                context=service_context,
            )
        )
        if not service_result.success:
            return SkillResult(skill_name=self.name, success=False, error=service_result.error)

        state = service_result.output or {}
        active_state = str(state.get("active_state", "unknown")).lower()
        sub_state = str(state.get("sub_state", "unknown")).lower()
        severity: Literal["low", "medium", "high", "critical"] = "low"
        likely_causes: list[str] = []
        recommendations: list[str] = []

        if active_state != "active":
            severity = "high"
            likely_causes.append("Dienst ist nicht aktiv")
            recommendations.append("Dienstzustand und Unit-Konfiguration prüfen")
        elif sub_state not in {"running", "listening"}:
            severity = "medium"
            likely_causes.append("Dienst läuft nicht im erwarteten SubState")
            recommendations.append("SubState und Logs auf Startfehler prüfen")
        else:
            recommendations.append("Dienstzustand ist vorerst stabil")

        if state.get("main_pid") in (None, 0):
            severity = "high" if severity == "low" else severity
            likely_causes.append("Kein MainPID sichtbar")

        output = ServiceTriageOutput(
            service_name=getattr(validated_input, "service_name"),
            severity=severity,
            state=state,
            likely_causes=likely_causes or ["Keine offensichtliche Ursache erkannt"],
            recommendations=recommendations,
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))


class RouterLogReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=20)
    level: Literal["info", "warn", "error"] | None = None
    source_contains: str | None = Field(default=None, max_length=64)
    message_contains: str | None = Field(default=None, max_length=128)


class RouterLogReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    returned_count: int
    severity: Literal["low", "medium", "high", "critical"]
    entries: list[dict[str, Any]]
    summary: str


class RouterLogReviewSkill(BaseSkill):
    name = "router_log_review"
    description = "Router-Logs verdichten und priorisieren."
    allowed_tools = ["router_logs"]
    input_schema = RouterLogReviewInput
    output_schema = RouterLogReviewOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        from app.models.tool_models import ToolExecutionContext

        tool_executor = ToolExecutor(timeout_seconds=10)
        context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="router_logs",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )
        result = asyncio.run(
            tool_executor.execute(
                "router_logs",
                validated_input.model_dump(exclude_none=True),
                allowed_tools=list(self.allowed_tools),
                context=context,
            )
        )
        if not result.success:
            return SkillResult(skill_name=self.name, success=False, error=result.error)

        output = result.output or {}
        entries = list(output.get("entries", []))
        error_count = sum(1 for entry in entries if str(entry.get("level", "")).lower() == "error")
        severity: Literal["low", "medium", "high", "critical"] = "low"
        if error_count >= 5:
            severity = "critical"
        elif error_count >= 2:
            severity = "high"
        elif error_count >= 1:
            severity = "medium"

        summary = f"{len(entries)} Logeinträge geprüft, {error_count} Fehler gefunden."
        review = RouterLogReviewOutput(
            returned_count=len(entries),
            severity=severity,
            entries=entries,
            summary=summary,
        )
        return SkillResult(skill_name=self.name, success=True, output=review.model_dump(mode="json"))


class DockerSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DockerSnapshotOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container_count: int
    severity: Literal["low", "medium", "high", "critical"]
    summary: str
    containers: list[dict[str, Any]]


class DockerSnapshotSkill(BaseSkill):
    name = "docker_snapshot"
    description = "Containerlage und Health bewerten."
    allowed_tools = ["docker_status"]
    input_schema = DockerSnapshotInput
    output_schema = DockerSnapshotOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        del validated_input
        from app.models.tool_models import ToolExecutionContext

        tool_executor = ToolExecutor(timeout_seconds=10)
        context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="docker_status",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )
        result = asyncio.run(
            tool_executor.execute(
                "docker_status",
                {},
                allowed_tools=list(self.allowed_tools),
                context=context,
            )
        )
        if not result.success:
            return SkillResult(skill_name=self.name, success=False, error=result.error)

        output = result.output or {}
        containers = list(output.get("containers", []))
        severity: Literal["low", "medium", "high", "critical"] = "low"
        if any(str(container.get("health", "")).lower() not in {"healthy", "unknown"} for container in containers):
            severity = "medium"
        if any("exited" in str(container.get("status", "")).lower() for container in containers):
            severity = "high"

        snapshot = DockerSnapshotOutput(
            container_count=int(output.get("container_count", len(containers))),
            severity=severity,
            summary="Docker-Lage wurde erfasst.",
            containers=containers,
        )
        return SkillResult(skill_name=self.name, success=True, output=snapshot.model_dump(mode="json"))


class ServiceLogCorrelationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    log_limit: int = Field(default=10, ge=1, le=20)


class ServiceLogCorrelationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str
    severity: Literal["low", "medium", "high", "critical"]
    likely_cause: str
    service: dict[str, Any]
    logs: dict[str, Any]
    recommendations: list[str]


class ServiceLogCorrelationSkill(BaseSkill):
    name = "service_log_correlation"
    description = "Dienststatus und Loghinweise zusammenführen."
    allowed_tools = ["service_status", "router_logs"]
    input_schema = ServiceLogCorrelationInput
    output_schema = ServiceLogCorrelationOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        from app.models.tool_models import ToolExecutionContext

        tool_executor = ToolExecutor(timeout_seconds=10)
        service_context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="service_status",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )
        log_context = ToolExecutionContext(
            agent_name="skill_runner",
            tool_name="router_logs",
            step_number=1,
            request_id=None,
            allowed_tools=list(self.allowed_tools),
        )

        service_result = asyncio.run(
            tool_executor.execute(
                "service_status",
                {"service_name": getattr(validated_input, "service_name")},
                allowed_tools=list(self.allowed_tools),
                context=service_context,
            )
        )
        log_result = asyncio.run(
            tool_executor.execute(
                "router_logs",
                {"limit": getattr(validated_input, "log_limit")},
                allowed_tools=list(self.allowed_tools),
                context=log_context,
            )
        )
        if not service_result.success:
            return SkillResult(skill_name=self.name, success=False, error=service_result.error)
        if not log_result.success:
            return SkillResult(skill_name=self.name, success=False, error=log_result.error)

        service_state = service_result.output or {}
        logs_state = log_result.output or {}
        entries = list(logs_state.get("entries", []))
        service_name = getattr(validated_input, "service_name")
        related_hits = [
            entry
            for entry in entries
            if service_name.lower() in str(entry.get("message", "")).lower()
            or service_name.lower() in str(entry.get("source", "")).lower()
        ]
        severity: Literal["low", "medium", "high", "critical"] = "low"
        likely_cause = "Keine klare Korrelation erkennbar."
        recommendations = ["Weiter beobachten, wenn keine Wiederholung auftritt."]
        if str(service_state.get("active_state", "")).lower() != "active":
            severity = "high"
            likely_cause = "Dienstzustand ist nicht aktiv."
            recommendations = ["Dienststatus und Startprotokoll prüfen."]
        elif related_hits:
            severity = "medium"
            likely_cause = "Router-Logs zeigen Hinweise zum Dienst."
            recommendations = ["Betroffene Logeinträge und Dienstkonfiguration prüfen."]

        output = ServiceLogCorrelationOutput(
            service_name=service_name,
            severity=severity,
            likely_cause=likely_cause,
            service=service_state,
            logs={"entries": entries, "related_hits": related_hits},
            recommendations=recommendations,
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))


class IncidentSummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Incident Summary", min_length=1)
    findings: list[dict[str, Any]] = Field(default_factory=list)


class IncidentSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    severity: Literal["low", "medium", "high", "critical"]
    top_findings: list[str]
    recommendations: list[str]


class IncidentSummarySkill(BaseSkill):
    name = "incident_summary"
    description = "Mehrere Befunde zu einer priorisierten Gesamtlage verdichten."
    allowed_tools = []
    input_schema = IncidentSummaryInput
    output_schema = IncidentSummaryOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        findings = list(getattr(validated_input, "findings", []))
        top_findings: list[str] = []
        recommendations: list[str] = []
        severity: Literal["low", "medium", "high", "critical"] = "low"

        for finding in findings:
            summary = str(
                finding.get("summary")
                or finding.get("likely_cause")
                or finding.get("description")
                or ""
            ).strip()
            if summary:
                top_findings.append(summary)
            finding_severity = str(finding.get("severity", "low")).lower()
            if finding_severity == "critical":
                severity = "critical"
            elif finding_severity == "high" and severity != "critical":
                severity = "high"
            elif finding_severity == "medium" and severity == "low":
                severity = "medium"
            recs = finding.get("recommendations", [])
            if isinstance(recs, list):
                recommendations.extend(str(item) for item in recs if str(item).strip())

        if not top_findings:
            top_findings.append("Keine verwertbaren Befunde übergeben.")

        output = IncidentSummaryOutput(
            title=getattr(validated_input, "title"),
            severity=severity,
            top_findings=top_findings[:5],
            recommendations=recommendations[:5] or ["Keine unmittelbaren Maßnahmen erkannt."],
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))


class KidsControllerRepetitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict[str, Any]


class KidsControllerRepetitionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "ok",
        "warning",
        "anomaly_detected",
        "invariant_suspected",
        "recommend_review",
    ]
    message: str
    findings: list[str]
    recommendations: list[str]
    confidence: int | None = Field(default=None, ge=0, le=100)
    source: str
    observed_at: str | None = None


class KidsControllerRepetitionSkill(BaseSkill):
    name = "kids_controller_repetition_review"
    description = "Bewertet, ob eine Kids-Controller-Aufstellung in letzter Zeit auffällig oft vorkam."
    allowed_tools = []
    input_schema = KidsControllerRepetitionInput
    output_schema = KidsControllerRepetitionOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        observation = dict(getattr(validated_input, "observation", {}) or {})
        trend = dict(observation.get("trend") or {})
        arrangement = trend.get("arrangement_signature") or self._arrangement_signature(observation)
        comparable_count = self._safe_int(trend.get("comparable_draw_count"))
        same_count = self._safe_int(trend.get("same_arrangement_count"))
        ratio = self._safe_ratio(trend.get("same_arrangement_ratio"))
        repeated_arrangement = bool(trend.get("repeated_arrangement"))

        findings: list[str] = []
        recommendations: list[str] = []
        confidence: int | None = None
        status: Literal[
            "ok",
            "warning",
            "anomaly_detected",
            "invariant_suspected",
            "recommend_review",
        ] = "ok"

        if comparable_count < 3 or arrangement is None:
            message = (
                "Hallo Kids Controller, für diese Aufstellung gibt es noch zu wenig "
                "vergleichbare Historie für eine belastbare Wiederholungsaussage."
            )
            findings.append("insufficient_comparison_history")
            recommendations.append("Mehr vergleichbare Draws sammeln und dann erneut prüfen.")
            confidence = 35
        elif repeated_arrangement or (same_count >= 4 and ratio >= 0.5):
            status = "recommend_review"
            message = (
                "Hallo Kids Controller, diese Aufstellung war in letzter Zeit sehr oft "
                f"zu sehen: {same_count} von {comparable_count} vergleichbaren Draws "
                f"nutzten erneut {arrangement}."
            )
            findings.extend(
                [
                    "frequent_arrangement",
                    f"arrangement_signature:{arrangement}",
                    f"same_arrangement_count:{same_count}",
                ]
            )
            recommendations.extend(
                [
                    "Das Fairness-Fenster auf Wiederholungsmuster prüfen.",
                    "Vergleichen, ob alternative Aufstellungen zuletzt seltener gezogen wurden.",
                ]
            )
            confidence = 88
        elif same_count >= 3 and ratio >= 0.4:
            status = "warning"
            message = (
                "Hallo Kids Controller, diese Aufstellung tauchte zuletzt auffällig häufig auf: "
                f"{same_count} von {comparable_count} vergleichbaren Draws waren erneut {arrangement}."
            )
            findings.extend(
                [
                    "elevated_arrangement_repetition",
                    f"arrangement_signature:{arrangement}",
                ]
            )
            recommendations.append("Die nächsten Draws beobachten und bei weiterer Häufung prüfen.")
            confidence = 72
        else:
            message = (
                "Hallo Kids Controller, für diese Aufstellung sehe ich aktuell keine auffällige "
                "Häufung in der jüngsten Vergleichshistorie."
            )
            findings.append("no_repetition_concern")
            recommendations.append("Keine unmittelbare Maßnahme erforderlich.")
            confidence = 64

        output = KidsControllerRepetitionOutput(
            status=status,
            message=message,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            source=self.name,
            observed_at=self._normalize_observed_at(observation.get("observed_at")),
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))

    @staticmethod
    def _arrangement_signature(observation: dict[str, Any]) -> str | None:
        positions = [
            observation.get("pos1"),
            observation.get("pos2"),
            observation.get("pos3"),
        ]
        normalized = [position for position in positions if isinstance(position, int)]
        if not normalized:
            return None
        return "".join(str(position) for position in normalized)

    @staticmethod
    def _safe_int(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return max(value, 0)
        return 0

    @staticmethod
    def _safe_ratio(value: Any) -> float:
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return min(max(float(value), 0.0), 1.0)
        return 0.0

    @staticmethod
    def _normalize_observed_at(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        return None


class AgentHealthCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentHealthCheckOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_ok: bool
    tool_registry_ok: bool
    skill_registry_ok: bool
    policy_ok: bool
    persistence_ok: bool
    api_routes_ok: bool
    details: dict[str, Any]


class AgentHealthCheckSkill(BaseSkill):
    name = "agent_health_check"
    description = "Agentenplattform selbst prüfen."
    allowed_tools = []
    input_schema = AgentHealthCheckInput
    output_schema = AgentHealthCheckOutput
    read_only = True
    version = "1.0"

    def execute(self, validated_input: BaseModel) -> SkillResult:
        del validated_input
        from app.agents.store import AGENT_STORE_PATH
        from app.agents.registry import list_agents
        from app.api.routes_agents import router as agent_router
        from app.main import app as fastapi_app
        from app.skills.registry import list_skill_names
        from app.tools.registry import list_tool_names

        paths = {route.path for route in fastapi_app.routes}
        details = {
            "agents": [agent.name for agent in list_agents()],
            "tools": list_tool_names(),
            "skills": list_skill_names(),
            "store_exists": AGENT_STORE_PATH.exists(),
            "routes": sorted(paths),
            "agent_router_prefix": getattr(agent_router, "prefix", "/agents"),
        }
        agents = list_agents()
        output = AgentHealthCheckOutput(
            registry_ok=bool(agents),
            tool_registry_ok=bool(list_tool_names()),
            skill_registry_ok=bool(list_skill_names()),
            policy_ok=all(agent.settings.policy.read_only == agent.settings.read_only for agent in agents),
            persistence_ok=AGENT_STORE_PATH.exists(),
            api_routes_ok="/agents" in paths and "/agents/run" in paths and "/skills" in paths and "/actions" in paths,
            details=details,
        )
        return SkillResult(skill_name=self.name, success=True, output=output.model_dump(mode="json"))


def register_standard_skills() -> None:
    for skill in (
        SystemSnapshotSkill(),
        ServiceTriageSkill(),
        RouterLogReviewSkill(),
        DockerSnapshotSkill(),
        ServiceLogCorrelationSkill(),
        IncidentSummarySkill(),
        KidsControllerRepetitionSkill(),
        AgentHealthCheckSkill(),
    ):
        register_builtin_skill(skill)


register_standard_skills()
