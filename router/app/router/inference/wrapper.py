"""Persistenter HTTP-Client für den Inference-Server (AirPI / Ollama).

Vorteile gegenüber einem neuen AsyncClient pro Request:
- Wiederverwendung der TCP-Verbindung (kein Handshake-Overhead)
- Retry bei ConnectError / 5xx (0 s → 2 s → 5 s)
- Separate Timeouts: TIMEOUT_ROUTE (60 s) für /route, TIMEOUT_AGENT (180 s) für Agenten-Steps
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings
from app.router.errors import RouterApiError

logger = logging.getLogger(__name__)

TIMEOUT_ROUTE: float = 60.0
TIMEOUT_AGENT: float = 180.0

_client: httpx.AsyncClient | None = None


async def init() -> None:
    global _client
    _client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        timeout=None,
    )
    logger.info("inference wrapper ready: base_url=%s", settings.OLLAMA_BASE_URL)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("inference wrapper closed")


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("inference wrapper not initialized — call init() first")
    return _client


async def _post_with_retry(
    url: str,
    payload: dict,
    timeout: float,
    request_id: str,
    model: str,
) -> httpx.Response:
    delays = (0.0, 2.0, 5.0)
    client = _get_client()
    last_exc: Exception | None = None

    for attempt, delay in enumerate(delays):
        if delay:
            await asyncio.sleep(delay)
        try:
            response = await client.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise RouterApiError(
                message=f"Inference-Server hat nicht innerhalb von {timeout:.0f}s geantwortet.",
                status_code=504,
                code="ollama_timeout",
                request_id=request_id,
                model=model,
                retryable=True,
            ) from exc
        except httpx.ConnectError as exc:
            last_exc = exc
            logger.warning("inference connect error (attempt %d/3): %s", attempt + 1, exc)
        except httpx.HTTPStatusError as exc:
            if 500 <= exc.response.status_code < 600:
                last_exc = exc
                logger.warning(
                    "inference 5xx (attempt %d/3): status=%s",
                    attempt + 1,
                    exc.response.status_code,
                )
            else:
                detail = exc.response.text.strip() or exc.response.reason_phrase
                logger.warning("inference 4xx: status=%s detail=%s", exc.response.status_code, detail[:200])
                raise RouterApiError(
                    message=f"Inference-Server hat mit HTTP {exc.response.status_code} geantwortet.",
                    status_code=502,
                    code="ollama_http_error",
                    request_id=request_id,
                    model=model,
                    retryable=False,
                ) from exc

    if isinstance(last_exc, httpx.ConnectError):
        raise RouterApiError(
            message="Inference-Server ist nicht erreichbar.",
            status_code=502,
            code="ollama_unreachable",
            request_id=request_id,
            model=model,
            retryable=True,
        ) from last_exc

    raise RouterApiError(
        message="Inference-Server hat wiederholt mit 5xx geantwortet.",
        status_code=502,
        code="ollama_http_error",
        request_id=request_id,
        model=model,
        retryable=True,
    ) from last_exc


async def generate(
    model: str,
    prompt: str,
    request_id: str,
    stream: bool = False,
    timeout: float = TIMEOUT_ROUTE,
    session_id: str | None = None,
) -> dict:
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload: dict = {"model": model, "prompt": prompt, "stream": stream}
    if session_id is not None:
        payload["session_id"] = session_id
    response = await _post_with_retry(url, payload, timeout, request_id, model)
    return response.json()


async def post(
    path: str,
    payload: dict,
    request_id: str,
    model: str,
    timeout: float = TIMEOUT_ROUTE,
) -> dict:
    url = f"{settings.OLLAMA_BASE_URL}{path}"
    response = await _post_with_retry(url, payload, timeout, request_id, model)
    return response.json()


def stream_response(
    path: str,
    payload: dict,
    request_id: str,
    model: str,
    timeout: float = TIMEOUT_AGENT,
):
    url = f"{settings.OLLAMA_BASE_URL}{path}"

    async def iterator():
        client = _get_client()
        try:
            async with client.stream("POST", url, json=payload, timeout=timeout) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
        except httpx.TimeoutException as exc:
            raise RouterApiError(
                message=f"Inference-Server hat nicht innerhalb von {timeout:.0f}s geantwortet.",
                status_code=504,
                code="ollama_timeout",
                request_id=request_id,
                model=model,
                retryable=True,
            ) from exc
        except httpx.ConnectError as exc:
            raise RouterApiError(
                message="Inference-Server ist nicht erreichbar.",
                status_code=502,
                code="ollama_unreachable",
                request_id=request_id,
                model=model,
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            logger.warning(
                "inference stream HTTP error: status=%s detail=%s",
                exc.response.status_code,
                detail[:200],
            )
            raise RouterApiError(
                message=f"Inference-Server hat mit HTTP {exc.response.status_code} geantwortet.",
                status_code=502,
                code="ollama_http_error",
                request_id=request_id,
                model=model,
                retryable=500 <= exc.response.status_code < 600,
            ) from exc

    return iterator()
