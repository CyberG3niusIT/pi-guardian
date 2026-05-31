import json
import time
import uuid
from typing import Any

from sqlmodel import Session

from app.config import settings
from app.router.execution.service import (
    build_route_tool_plan,
    create_policy_trace,
    render_route_tool_response,
    route_execution_service,
)
from app.router.auth import AuthorizedClientContext
from app.router.decision.models import RequestClassification
from app.router.decision.service import decide_route_request
from app.router.errors import RouterApiError
from app.router.history import create_route_history_entry
from app.router.policy import apply_client_policy
from app.router.ollama_client import generate_with_ollama
from app.schemas.request_models import RouteRequest
from app.schemas.response_models import RouteResponse


_FAST_MODEL_ALIASES = {"fast", "fast-lane", "airpi-fast"}
_ROUTE_JSON_KEYS = ["decision", "risk", "reason"]
_ALLOWED_ROUTE_DECISIONS = {"allow", "block", "review", "tool_required"}
_ALLOWED_ROUTE_RISKS = {"low", "medium", "high"}
_BLOCK_ROUTE_DECISIONS = {"block", "review", "tool_required"}
_BLOCK_ROUTE_RISKS = {"high"}


def _prompt_preview(prompt: str, limit: int = 160) -> str:
    return " ".join(prompt.split())[:limit]


def _default_policy_trace(classification: str) -> dict:
    return create_policy_trace(
        can_use_llm=True,
        can_use_tools=False,
        can_use_internet=False,
        decision_classification=classification,
    ).model_dump(mode="json")


def _extract_kids_controller_observation(prompt: str) -> dict | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(prompt):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(prompt[index:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("kind") == "kids_controller_observation"
            and isinstance(payload.get("observation"), dict)
        ):
            return payload["observation"]
    return None


def _run_kids_controller_repetition_review(observation: dict) -> dict | None:
    from app.skills.registry import get_skill

    skill = get_skill("kids_controller_repetition_review")
    if skill is None:
        return None
    validated = skill.validate_arguments({"observation": observation})
    result = skill.execute(validated)
    if not result.success or not isinstance(result.output, dict):
        return None
    return result.output


def _is_fast_lane_model(model: str) -> bool:
    configured_fast = getattr(settings, "FAST_MODEL", "fast")
    return model.lower() in _FAST_MODEL_ALIASES or model == configured_fast


def _parse_route_json(raw_response: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if any(key not in parsed for key in _ROUTE_JSON_KEYS):
        return None
    decision = str(parsed.get("decision", "")).lower()
    risk = str(parsed.get("risk", "")).lower()
    if decision not in _ALLOWED_ROUTE_DECISIONS or risk not in _ALLOWED_ROUTE_RISKS:
        return None
    return {
        "decision": decision,
        "risk": risk,
        "reason": str(parsed.get("reason", "")),
    }


def _route_json_requires_block(route_json: dict[str, Any]) -> bool:
    decision = str(route_json.get("decision", "")).lower()
    risk = str(route_json.get("risk", "")).lower()
    return decision in _BLOCK_ROUTE_DECISIONS or risk in _BLOCK_ROUTE_RISKS


async def _generate_llm_response(
    *,
    model: str,
    prompt: str,
    request_id: str,
    stream: bool,
) -> tuple[dict, bool, dict[str, Any] | None]:
    if not _is_fast_lane_model(model):
        result = await generate_with_ollama(
            model=model,
            prompt=prompt,
            request_id=request_id,
            stream=stream,
        )
        return result, False, None

    try:
        result = await generate_with_ollama(
            model=model,
            prompt=prompt,
            request_id=request_id,
            stream=False,
            format="json",
            required_json_keys=_ROUTE_JSON_KEYS,
        )
    except RouterApiError:
        fallback = await generate_with_ollama(
            model=settings.DEFAULT_MODEL,
            prompt=prompt,
            request_id=request_id,
            stream=False,
        )
        return fallback, True, None

    route_json = _parse_route_json(str(result.get("response", "")))
    if route_json is None:
        fallback = await generate_with_ollama(
            model=settings.DEFAULT_MODEL,
            prompt=prompt,
            request_id=request_id,
            stream=False,
        )
        return fallback, True, None
    return result, False, route_json


async def route_prompt(
    request: RouteRequest,
    session: Session,
    client_context: AuthorizedClientContext | None = None,
    client_name: str | None = None,
) -> RouteResponse:
    request_id = str(uuid.uuid4())
    started_at = time.perf_counter()
    preview = _prompt_preview(request.prompt)
    resolved_client_name = client_context.name if client_context is not None else client_name
    decision = decide_route_request(request)
    policy_trace = (
        create_policy_trace(
            can_use_llm=bool(client_context.policy.can_use_llm),
            can_use_tools=bool(client_context.policy.can_use_tools),
            can_use_internet=bool(client_context.policy.can_use_internet),
            decision_classification=decision.classification.value,
        ).model_dump(mode="json")
        if client_context is not None
        else _default_policy_trace(decision.classification.value)
    )
    decision = apply_client_policy(
        decision,
        client_context.policy if client_context is not None else None,
    )
    selected_model = decision.selected_model or settings.DEFAULT_MODEL
    observation = _extract_kids_controller_observation(request.prompt)

    if decision.classification is RequestClassification.BLOCKED:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=preview,
            model=None,
            success=False,
            error_code="request_blocked",
            client_name=resolved_client_name,
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            policy_trace=policy_trace,
            execution_mode="llm",
            execution_status="failed",
            execution_error="request_blocked",
        )
        raise RouterApiError(
            message="Anfrage wurde durch die vorgelagerte Entscheidungslogik blockiert",
            status_code=403,
            code="request_blocked",
            request_id=request_id,
            retryable=False,
        )

    if decision.classification is RequestClassification.INTERNET_REQUIRED:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=preview,
            model=None,
            success=False,
            error_code="internet_execution_unavailable",
            client_name=resolved_client_name,
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            policy_trace=policy_trace,
            execution_mode="internet_pending",
            execution_status="failed",
            execution_error=(
                "Internet-Zugriff ist architektonisch klassifiziert, aber im "
                "normalen `/route`-Pfad noch nicht kontrolliert aktiviert."
            ),
        )
        raise RouterApiError(
            message=(
                "Internet-Anfragen werden erkannt, aber im normalen `/route`-Pfad "
                "noch nicht kontrolliert ausgeführt."
            ),
            status_code=501,
            code="internet_execution_unavailable",
            request_id=request_id,
            retryable=False,
        )

    if decision.classification is RequestClassification.TOOL_REQUIRED:
        plans = build_route_tool_plan(request.prompt, decision.tool_hints)
        if not plans:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            create_route_history_entry(
                session,
                request_id=request_id,
                prompt_preview=preview,
                model=None,
                success=False,
                error_code="tool_execution_not_supported",
                client_name=resolved_client_name,
                duration_ms=duration_ms,
                decision_classification=decision.classification.value,
                decision_reasons=decision.reasons,
                decision_tool_hints=decision.tool_hints,
                decision_internet_hints=decision.internet_hints,
                policy_trace=policy_trace,
                execution_mode="tool",
                execution_status="failed",
                executed_tools=[],
                execution_error=(
                    "Für diese Tool-Hinweise ist im normalen `/route`-Pfad noch "
                    "kein kontrolliert ausführbares Tool verdrahtet."
                ),
            )
            raise RouterApiError(
                message=(
                    "Tool-Bedarf wurde erkannt, aber für diese Anfrage ist im "
                    "normalen `/route`-Pfad noch kein kontrolliert ausführbares Tool "
                    "verdrahtet."
                ),
                status_code=422,
                code="tool_execution_not_supported",
                request_id=request_id,
                retryable=False,
            )

        tool_executions = await route_execution_service.execute_tools(
            plans=plans,
            request_id=request_id,
            policy_trace=create_policy_trace(
                can_use_llm=policy_trace["can_use_llm"],
                can_use_tools=policy_trace["can_use_tools"],
                can_use_internet=policy_trace["can_use_internet"],
                decision_classification=policy_trace["decision_classification"],
            ),
        )
        execution_error = None
        success = any(execution.success for execution in tool_executions)
        if not success:
            execution_error = "Alle geplanten Tools sind fehlgeschlagen."

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=preview,
            model=None,
            success=success,
            error_code=None if success else "tool_execution_failed",
            client_name=resolved_client_name,
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            policy_trace=policy_trace,
            execution_mode="tool",
            execution_status="succeeded" if success else "failed",
            executed_tools=[execution.tool_name for execution in tool_executions],
            tool_execution_records=[
                execution.model_dump(mode="json") for execution in tool_executions
            ],
            execution_error=execution_error,
        )
        if not success:
            raise RouterApiError(
                message="Geplante Tool-Ausführung ist fehlgeschlagen.",
                status_code=502,
                code="tool_execution_failed",
                request_id=request_id,
                retryable=False,
            )

        return RouteResponse(
            request_id=request_id,
            model="tool_executor",
            response=render_route_tool_response(tool_executions),
            done=True,
            done_reason="tool_execution_completed",
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            execution_mode="tool",
            policy_trace=policy_trace,
            tool_executions=[
                execution.model_dump(mode="json") for execution in tool_executions
            ],
            execution_error=execution_error,
        )

    if observation is not None:
        reviewed = _run_kids_controller_repetition_review(observation)
        if reviewed is not None:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            create_route_history_entry(
                session,
                request_id=request_id,
                prompt_preview=preview,
                model="kids_controller_repetition_review",
                success=True,
                error_code=None,
                client_name=resolved_client_name,
                duration_ms=duration_ms,
                decision_classification=decision.classification.value,
                decision_reasons=decision.reasons,
                decision_tool_hints=decision.tool_hints,
                decision_internet_hints=decision.internet_hints,
                policy_trace=policy_trace,
                execution_mode="llm",
                execution_status="succeeded",
            )
            return RouteResponse(
                request_id=request_id,
                model="kids_controller_repetition_review",
                response=json.dumps(reviewed, ensure_ascii=False),
                done=True,
                done_reason="skill_completed",
                duration_ms=duration_ms,
                decision_classification=decision.classification.value,
                decision_reasons=decision.reasons,
                decision_tool_hints=decision.tool_hints,
                decision_internet_hints=decision.internet_hints,
                execution_mode="llm",
                policy_trace=policy_trace,
            )

    try:
        result, escalated_from_fast_lane, route_json = await _generate_llm_response(
            model=selected_model,
            prompt=request.prompt,
            request_id=request_id,
            stream=request.stream,
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        resolved_model = result.get("model", selected_model)
        decision_reasons = list(decision.reasons)
        execution_status = "not_executed"
        execution_error = None
        success = True

        if escalated_from_fast_lane:
            decision_reasons.append("Fast-Lane-JSON ungueltig, auf Default-Modell eskaliert")
            resolved_model = result.get("model", settings.DEFAULT_MODEL)

        if route_json is not None:
            decision_reasons.append(
                f"Fast-Lane-JSON validiert: decision={route_json['decision']} risk={route_json['risk']}"
            )
            if _route_json_requires_block(route_json):
                success = False
                execution_status = "failed"
                execution_error = "fast_lane_policy_block"

        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=preview,
            model=resolved_model,
            success=success,
            error_code=None if success else "fast_lane_policy_block",
            client_name=resolved_client_name,
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision_reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            policy_trace=policy_trace,
            execution_mode="llm",
            execution_status=execution_status,
            execution_error=execution_error,
        )
        if not success:
            raise RouterApiError(
                message="Fast-Lane-Routing hat die Anfrage sicherheitshalber blockiert.",
                status_code=403,
                code="fast_lane_policy_block",
                request_id=request_id,
                model=resolved_model,
                retryable=False,
            )

        return RouteResponse(
            request_id=request_id,
            model=resolved_model,
            response=result.get("response", ""),
            done=result.get("done", False),
            done_reason=result.get("done_reason"),
            duration_ms=duration_ms,
            decision_classification=decision.classification.value,
            decision_reasons=decision_reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            execution_mode="llm",
            policy_trace=policy_trace,
            execution_error=execution_error,
        )
    except RouterApiError as exc:
        if exc.code == "fast_lane_policy_block":
            raise
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=preview,
            model=selected_model,
            success=False,
            error_code=exc.code,
            client_name=resolved_client_name,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
            policy_trace=policy_trace,
            execution_mode="llm",
            execution_status="failed",
            execution_error=exc.code,
        )
        raise
