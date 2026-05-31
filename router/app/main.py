import json
import logging
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s \u2013 %(message)s")

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

level = logging.getLevelName(settings.LOG_LEVEL)

root_logger = logging.getLogger()
root_logger.setLevel(level)
root_logger.handlers.clear()
root_logger.addHandler(stream_handler)

try:
    Path("logs").mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        "logs/router.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
except OSError as exc:
    root_logger.warning("Datei-Logging deaktiviert: %s", exc)

for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    logging.getLogger(name).propagate = True

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session, select

from app.api.routes_agents import router as agents_router
from app.api.routes_actions import router as actions_router
from app.api.routes_agent_memory import router as agent_memory_router
from app.api.routes_auth import router as auth_router
from app.api.routes_memory import router as memory_router
from app.api.routes_skills import router as skills_router
from app.database import get_session, init_db
from app.models.client import Client
from app.router.auth import (
    authorize_protected_request,
    authorize_route_context,
    authorize_route_request,
)
from app.router.classifier import select_model_for_prompt
from app.router.clients import router as clients_router
from app.router.decision.classifier import classify_request
from app.router.decision.models import RequestClassification
from app.router.errors import RouterApiError
from app.router.history import create_route_history_entry, list_route_history
from app.router.model_registry import sync_model_registry
from app.api.routes_model_pull import router as model_pull_router
from app.router.log_reader import read_logs
from app.router.ollama_client import post_to_ollama, stream_to_ollama
from app.router.ollama_models import delete_ollama_model, fetch_model_names, fetch_models, fetch_raw_tags
from app.router.service import route_prompt
from app.router.settings_manager import (
    RouterSettingsUpdate,
    restart_router_service,
    set_default_model,
    update_runtime_settings,
)
from app.router.settings_reader import get_settings
from app.router.system_status import get_service_status
from app.api.routes_model_registry import router as model_registry_router
from app.router.inference import wrapper as inference_wrapper
from app.schemas.request_models import ModelSelectionRequest, RouteRequest
from app.schemas.response_models import (
    LogEntry,
    IntegrationGuide,
    OllamaModel,
    RouteHistoryEntry,
    RouteResponse,
    RouteErrorResponse,
    RouterSettings,
    SettingsUpdateResponse,
    ServiceStatus,
)


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    await inference_wrapper.init()
    yield
    await inference_wrapper.close()


app = FastAPI(
    title="PI Guardian Model Router",
    version="0.1.0",
    description="Lokaler FastAPI-Router für Ollama-Modelle auf dem Raspberry Pi",
    lifespan=lifespan,
)

app.include_router(clients_router)
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(agent_memory_router)
app.include_router(skills_router)
app.include_router(actions_router)
app.include_router(memory_router)
app.include_router(model_registry_router)
app.include_router(model_pull_router)
init_db()
ADMIN_ROUTES = {
    "/route",
    "/clients",
    "/history",
    "/logs",
    "/agents",
    "/skills",
    "/actions",
    "/memory",
    "/models",
    "/models/select",
    "/models/registry",
    "/models/pull",
    "/models/delete",
    "/settings",
    "/status/service",
    "/v1/models",
    "/v1/chat/completions",
}


def require_access(allowed_route: str):
    def dependency(
        request: Request,
        session: Session = Depends(get_session),
    ) -> None:
        authorize_protected_request(request, session, allowed_route)

    return dependency


def _has_active_admin_client(session: Session) -> bool:
    clients = session.exec(select(Client).where(Client.active == True)).all()
    for client in clients:
        if ADMIN_ROUTES.issubset(set(client.allowed_routes_list())):
            return True
    return False


def _prompt_preview(prompt: str, limit: int = 160) -> str:
    return " ".join(prompt.split())[:limit]


def _parse_json_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
    return []


def _parse_json_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _parse_json_records(value) -> list[dict]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _extract_text_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _prompt_from_chat_payload(payload: dict) -> str:
    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return ""

    user_messages: list[str] = []
    other_messages: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = _extract_text_content(message.get("content"))
        if not content:
            continue
        if message.get("role") == "user":
            user_messages.append(content)
        else:
            other_messages.append(content)

    if user_messages:
        return "\n".join(user_messages)
    return "\n".join(other_messages)


def _openai_messages_to_ollama(messages: list) -> list[dict]:
    ollama_messages: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = _extract_text_content(message.get("content"))
        if role not in {"system", "user", "assistant", "tool"} or not content:
            continue
        ollama_messages.append({"role": role, "content": content})
    return ollama_messages


def _openai_chat_response(ollama_result: dict, model: str) -> dict:
    content = ""
    message = ollama_result.get("message")
    if isinstance(message, dict):
        message_content = message.get("content")
        if isinstance(message_content, str):
            content = message_content
    if not content:
        response_text = ollama_result.get("response")
        if isinstance(response_text, str):
            content = response_text

    done_reason = ollama_result.get("done_reason")
    finish_reason = "stop" if done_reason in {None, "", "stop"} else str(done_reason)
    created = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": ollama_result.get("model") or model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


async def _proxy_to_ollama(
    path: str,
    payload: dict,
    prompt: str,
    session: Session,
    client_name: str | None,
):
    request_id = str(uuid.uuid4())
    decision = classify_request(RouteRequest(prompt=prompt))
    if decision.classification is RequestClassification.BLOCKED:
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=_prompt_preview(prompt),
            model=None,
            success=False,
            error_code="request_blocked",
            client_name=client_name,
            duration_ms=0,
            decision_classification=decision.classification.value,
            decision_reasons=decision.reasons,
            decision_tool_hints=decision.tool_hints,
            decision_internet_hints=decision.internet_hints,
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

    outgoing_payload = dict(payload)
    requested_model = outgoing_payload.get("model")
    selected_model = (
        requested_model.strip()
        if isinstance(requested_model, str) and requested_model.strip()
        else select_model_for_prompt(prompt)
    )
    outgoing_payload["model"] = selected_model
    stream = bool(outgoing_payload.get("stream"))
    started_at = time.perf_counter()

    if stream:
        async def streaming_iterator():
            try:
                async for chunk in stream_to_ollama(
                    path, outgoing_payload, request_id, selected_model
                ):
                    yield chunk
                create_route_history_entry(
                    session,
                    request_id=request_id,
                    prompt_preview=_prompt_preview(prompt),
                    model=selected_model,
                    success=True,
                    error_code=None,
                    client_name=client_name,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
            except RouterApiError as exc:
                create_route_history_entry(
                    session,
                    request_id=request_id,
                    prompt_preview=_prompt_preview(prompt),
                    model=selected_model,
                    success=False,
                    error_code=exc.code,
                    client_name=client_name,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
                raise

        return StreamingResponse(
            streaming_iterator(),
            media_type="application/x-ndjson",
        )

    try:
        result = await post_to_ollama(path, outgoing_payload, request_id, selected_model)
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=_prompt_preview(prompt),
            model=result.get("model", selected_model),
            success=True,
            error_code=None,
            client_name=client_name,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        return JSONResponse(content=result)
    except RouterApiError as exc:
        create_route_history_entry(
            session,
            request_id=request_id,
            prompt_preview=_prompt_preview(prompt),
            model=selected_model,
            success=False,
            error_code=exc.code,
            client_name=client_name,
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        raise


@app.exception_handler(RouterApiError)
async def handle_router_api_error(
    request: Request, exc: RouterApiError
) -> JSONResponse:
    payload = RouteErrorResponse(
        request_id=exc.request_id,
        model=exc.model,
        error={
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.get(
    "/api/tags",
    dependencies=[Depends(require_access("/api/tags"))],
)
async def ollama_tags() -> dict:
    return await fetch_raw_tags()


@app.post(
    "/api/generate",
    dependencies=[Depends(require_access("/api/generate"))],
)
async def ollama_generate(
    request: Request,
    session: Session = Depends(get_session),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON-Objekt erwartet")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=422, detail="Feld 'prompt' fehlt oder ist leer")
    client_name = authorize_protected_request(request, session, "/api/generate")
    return await _proxy_to_ollama("/api/generate", payload, prompt, session, client_name)


@app.post(
    "/api/chat",
    dependencies=[Depends(require_access("/api/chat"))],
)
async def ollama_chat(
    request: Request,
    session: Session = Depends(get_session),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON-Objekt erwartet")
    prompt = _prompt_from_chat_payload(payload)
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="Feld 'messages' enthält keinen nutzbaren Text")
    client_name = authorize_protected_request(request, session, "/api/chat")
    return await _proxy_to_ollama("/api/chat", payload, prompt, session, client_name)


@app.get(
    "/v1/models",
    dependencies=[Depends(require_access("/v1/models"))],
)
async def openai_models() -> dict:
    models = await fetch_models()
    return {
        "object": "list",
        "data": [
            {
                "id": model.get("name", ""),
                "object": "model",
                "created": 0,
                "owned_by": "pi-guardian",
            }
            for model in models
            if model.get("name")
        ],
    }


@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(require_access("/v1/chat/completions"))],
)
async def openai_chat_completions(
    request: Request,
    session: Session = Depends(get_session),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON-Objekt erwartet")
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=422, detail="Feld 'messages' fehlt oder ist ungültig")
    prompt = _prompt_from_chat_payload(payload)
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="Feld 'messages' enthält keinen nutzbaren Text")

    client_name = authorize_protected_request(request, session, "/v1/chat/completions")
    requested_model = payload.get("model")
    selected_model = (
        requested_model.strip()
        if isinstance(requested_model, str) and requested_model.strip()
        else select_model_for_prompt(prompt)
    )
    ollama_payload = {
        "model": selected_model,
        "prompt": prompt,
        "stream": False,
    }
    if "temperature" in payload:
        ollama_payload["options"] = {"temperature": payload["temperature"]}
    response = await _proxy_to_ollama(
        "/api/generate",
        ollama_payload,
        prompt,
        session,
        client_name,
    )
    if not isinstance(response, JSONResponse):
        raise HTTPException(status_code=422, detail="Streaming wird für OpenAI-Kompatibilität noch nicht unterstützt")
    ollama_result = json.loads(response.body.decode("utf-8"))
    return JSONResponse(content=_openai_chat_response(ollama_result, selected_model))


@app.get(
    "/status/service",
    response_model=ServiceStatus,
    dependencies=[Depends(require_access("/status/service"))],
)
async def service_status() -> ServiceStatus:
    return ServiceStatus(**get_service_status())


@app.get(
    "/logs",
    response_model=list[LogEntry],
    dependencies=[Depends(require_access("/logs"))],
)
async def logs(limit: int = Query(default=50, ge=1, le=200)) -> list[LogEntry]:
    return [LogEntry(**e) for e in read_logs(limit)]


@app.get(
    "/models",
    response_model=list[OllamaModel],
    dependencies=[Depends(require_access("/models"))],
)
async def models() -> list[OllamaModel]:
    return [OllamaModel(**m) for m in await fetch_models()]


@app.delete(
    "/models/delete/{model_name:path}",
    status_code=204,
    dependencies=[Depends(require_access("/models/delete"))],
)
async def model_delete(model_name: str) -> None:
    await delete_ollama_model(model_name)


@app.get(
    "/history",
    response_model=list[RouteHistoryEntry],
    dependencies=[Depends(require_access("/history"))],
)
async def history(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[RouteHistoryEntry]:
    return [
        RouteHistoryEntry(
            id=entry.id or 0,
            request_id=entry.request_id,
            prompt_preview=entry.prompt_preview,
            model=entry.model,
            success=entry.success,
            error_code=entry.error_code,
            client_name=entry.client_name,
            duration_ms=entry.duration_ms,
            decision_classification=entry.decision_classification or "llm_only",
            decision_reasons=_parse_json_list(entry.decision_reasons),
            decision_tool_hints=_parse_json_list(entry.decision_tool_hints),
            decision_internet_hints=_parse_json_list(entry.decision_internet_hints),
            fairness_review_attempted=bool(entry.fairness_review_attempted),
            fairness_review_used=bool(entry.fairness_review_used),
            fairness_risk=entry.fairness_risk or "unknown",
            fairness_review_override=bool(entry.fairness_review_override),
            escalation_threshold=entry.fairness_threshold,
            fairness_reasons=_parse_json_list(entry.fairness_reasons),
            fairness_notes=_parse_json_list(entry.fairness_notes),
            policy_trace=_parse_json_dict(entry.policy_trace),
            execution_mode=entry.execution_mode or "llm",
            execution_status=entry.execution_status or "not_executed",
            executed_tools=_parse_json_list(entry.executed_tools),
            tool_execution_records=_parse_json_records(entry.tool_execution_records),
            execution_error=entry.execution_error,
            created_at=entry.created_at.isoformat(),
        )
        for entry in list_route_history(session, limit=limit)
    ]


@app.get(
    "/settings",
    response_model=RouterSettings,
    dependencies=[Depends(require_access("/settings"))],
)
async def router_settings() -> RouterSettings:
    return RouterSettings(**get_settings())


@app.get(
    "/integration",
    response_model=IntegrationGuide,
    dependencies=[Depends(require_access("/settings"))],
)
async def integration_guide() -> IntegrationGuide:
    guide = get_settings()
    base_url = f"http://{guide['router_host']}:{guide['router_port']}"
    return IntegrationGuide(
        router_base_url=base_url,
        auth_header_name="X-API-Key",
        auth_header_example="X-API-Key: <client-api-key>",
        allowed_routes=[
            "/route",
            "/health",
            "/settings",
            "/status/service",
            "/clients",
            "/agents",
            "/skills",
            "/actions",
            "/history",
            "/logs",
            "/memory",
            "/api/tags",
            "/api/generate",
            "/api/chat",
            "/v1/models",
            "/v1/chat/completions",
            "/models/registry",
            "/models/pull",
        ],
        security_controls=[
            "API-Key pro Client",
            "IP-Allowlist pro Client",
            "Routen-Freigabe pro Client",
            f"Fairness-/Eskalationsschwelle: {guide['escalation_threshold']}",
        ],
        example_create_client={
            "name": "my-client",
            "description": "Integration fuer externen Dienst",
            "active": True,
            "allowed_ip": "192.168.50.0/24",
            "allowed_routes": [
                "/route",
                "/health",
                "/agents",
                "/skills",
                "/actions",
                "/api/tags",
                "/api/generate",
                "/api/chat",
                "/v1/models",
                "/v1/chat/completions",
                "/models/registry",
                "/models/pull",
            ],
        },
        example_curl=(
            f"curl -H 'X-API-Key: <client-api-key>' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"prompt\":\"Hallo\", \"stream\": false}}' "
            f"{base_url}/route"
        ),
    )


@app.put(
    "/settings",
    response_model=SettingsUpdateResponse,
    dependencies=[Depends(require_access("/settings"))],
)
async def update_settings(
    payload: RouterSettingsUpdate,
    session: Session = Depends(get_session),
) -> SettingsUpdateResponse:
    try:
        next_default_model = payload.default_model or settings.DEFAULT_MODEL
        next_large_model = payload.large_model or settings.LARGE_MODEL
        if next_default_model == next_large_model:
            raise HTTPException(
                status_code=422,
                detail="default_model und large_model müssen verschieden sein.",
            )
        if payload.require_api_key and not settings.REQUIRE_API_KEY:
            if not _has_active_admin_client(session):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "API-Key-Schutz kann erst aktiviert werden, wenn ein aktiver "
                        "Admin-Client mit Zugriff auf /route, /clients, /history, /logs, "
                        "/agents, /skills, /actions, /memory, /models, /models/select, "
                        "/models/registry, /models/pull, /settings und /status/service existiert."
                    ),
                )
        available_models = None
        if payload.default_model:
            if available_models is None:
                available_models = await fetch_model_names()
            if payload.default_model not in available_models:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unbekanntes Modell: {payload.default_model}",
                )
        if payload.large_model:
            if available_models is None:
                available_models = await fetch_model_names()
            if payload.large_model not in available_models:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unbekanntes Modell: {payload.large_model}",
                )
        update_runtime_settings(payload)
        sync_model_registry(session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    restart_requested = payload.restart_service
    restart_performed = False
    restart_message = None
    validation_warnings: list[str] = []

    if restart_requested:
        restart_performed, restart_message = restart_router_service()
        if not restart_performed and restart_message:
            validation_warnings.append(restart_message)

    return SettingsUpdateResponse(
        settings=RouterSettings(**get_settings()),
        restart_requested=restart_requested,
        restart_performed=restart_performed,
        restart_message=restart_message,
        validation_warnings=validation_warnings,
    )


@app.post(
    "/route",
    response_model=RouteResponse,
    responses={
        500: {"model": RouteErrorResponse},
        502: {"model": RouteErrorResponse},
        504: {"model": RouteErrorResponse},
    },
)
async def route(
    request: RouteRequest,
    http_request: Request,
    session: Session = Depends(get_session),
) -> RouteResponse:
    client_context = authorize_route_context(http_request, session)
    return await route_prompt(request, session=session, client_context=client_context)


@app.post(
    "/models/select",
    dependencies=[Depends(require_access("/models/select"))],
)
async def select_default_router_model(
    payload: ModelSelectionRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if payload.model == settings.LARGE_MODEL:
        raise HTTPException(
            status_code=422,
            detail="default_model und large_model müssen verschieden sein.",
        )
    available_models = await fetch_model_names()
    if payload.model not in available_models:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Modell: {payload.model}")
    set_default_model(payload.model)
    sync_model_registry(session)
    return {"model": payload.model}
