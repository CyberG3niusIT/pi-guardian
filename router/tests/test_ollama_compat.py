import asyncio

import pytest

from app.main import (
    _extract_text_content,
    _openai_chat_response,
    _openai_messages_to_ollama,
    _prompt_from_chat_payload,
)
from app.router.classifier import select_model_for_prompt
from app.main import _proxy_to_ollama
from app.router.errors import RouterApiError
from app.router.settings_reader import get_settings


def _collect_stream_body(response) -> list[bytes]:
    async def collect() -> list[bytes]:
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return chunks

    return asyncio.run(collect())


def test_select_model_for_prompt_uses_large_model_for_complex_keywords():
    model = select_model_for_prompt("Bitte architektur analysieren und debuggen")
    assert model == get_settings()["large_model"]


def test_select_model_for_prompt_uses_default_model_for_simple_prompt():
    model = select_model_for_prompt("Antworte nur mit OK")
    assert model == get_settings()["default_model"]


def test_extract_text_content_handles_string_and_part_list():
    assert _extract_text_content("Hallo") == "Hallo"
    assert _extract_text_content(
        [
            {"type": "text", "text": "Teil 1"},
            {"type": "image", "image_url": "x"},
            {"type": "text", "text": "Teil 2"},
        ]
    ) == "Teil 1\nTeil 2"


def test_prompt_from_chat_payload_prefers_user_messages():
    payload = {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Erste Frage"},
            {"role": "assistant", "content": "Antwort"},
            {"role": "user", "content": [{"type": "text", "text": "Zweite Frage"}]},
        ]
    }
    assert _prompt_from_chat_payload(payload) == "Erste Frage\nZweite Frage"


def test_openai_messages_to_ollama_keeps_text_content_only():
    messages = [
        {"role": "system", "content": "Du bist kurz."},
        {"role": "user", "content": [{"type": "text", "text": "Hallo"}]},
        {"role": "developer", "content": "ignorieren"},
        {"role": "assistant", "content": ""},
    ]

    assert _openai_messages_to_ollama(messages) == [
        {"role": "system", "content": "Du bist kurz."},
        {"role": "user", "content": "Hallo"},
    ]


def test_openai_chat_response_wraps_ollama_chat_result():
    response = _openai_chat_response(
        {"model": "fast", "message": {"role": "assistant", "content": "OK"}, "done": True},
        "fallback",
    )

    assert response["object"] == "chat.completion"
    assert response["model"] == "fast"
    assert response["choices"][0]["message"] == {"role": "assistant", "content": "OK"}
    assert response["choices"][0]["finish_reason"] == "stop"


def test_get_settings_exposes_large_model():
    settings = get_settings()
    assert settings["large_model"]


def test_proxy_to_ollama_stream_logs_history(monkeypatch):
    history_calls: list[dict] = []

    async def fake_stream_to_ollama(path, payload, request_id, model):
        yield b'{"response":"ok"}\n'

    def fake_select_model_for_prompt(prompt: str) -> str:
        return "test-model"

    def fake_create_route_history_entry(session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.main.stream_to_ollama", fake_stream_to_ollama)
    monkeypatch.setattr("app.main.select_model_for_prompt", fake_select_model_for_prompt)
    monkeypatch.setattr("app.main.create_route_history_entry", fake_create_route_history_entry)

    response = asyncio.run(
        _proxy_to_ollama(
            "/api/generate",
            {"prompt": "Hallo", "stream": True},
            "Hallo",
            session=object(),
            client_name="client-a",
        )
    )

    assert _collect_stream_body(response) == [b'{"response":"ok"}\n']
    assert len(history_calls) == 1
    assert history_calls[0]["success"] is True
    assert history_calls[0]["model"] == "test-model"
    assert history_calls[0]["client_name"] == "client-a"


def test_proxy_to_ollama_preserves_requested_model(monkeypatch):
    post_calls: list[dict] = []
    history_calls: list[dict] = []

    async def fake_post_to_ollama(path, payload, request_id, model):
        post_calls.append(
            {
                "path": path,
                "payload": payload,
                "request_id": request_id,
                "model": model,
            }
        )
        return {"model": model, "response": "ok", "done": True}

    def fail_select_model_for_prompt(prompt: str) -> str:
        raise AssertionError("Explicit proxy models must not be overwritten")

    def fake_create_route_history_entry(session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.main.post_to_ollama", fake_post_to_ollama)
    monkeypatch.setattr("app.main.select_model_for_prompt", fail_select_model_for_prompt)
    monkeypatch.setattr("app.main.create_route_history_entry", fake_create_route_history_entry)

    response = asyncio.run(
        _proxy_to_ollama(
            "/api/generate",
            {"model": "fast", "prompt": "Hallo", "stream": False},
            "Hallo",
            session=object(),
            client_name="client-a",
        )
    )

    assert response.body == b'{"model":"fast","response":"ok","done":true}'
    assert post_calls[0]["payload"]["model"] == "fast"
    assert post_calls[0]["model"] == "fast"
    assert history_calls[0]["model"] == "fast"


def test_proxy_to_ollama_blocks_destructive_prompt_before_forwarding(monkeypatch):
    history_calls: list[dict] = []

    async def fail_post_to_ollama(*args, **kwargs):
        raise AssertionError("Blocked proxy prompts must not reach inference")

    def fake_create_route_history_entry(session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.main.post_to_ollama", fail_post_to_ollama)
    monkeypatch.setattr("app.main.create_route_history_entry", fake_create_route_history_entry)

    with pytest.raises(RouterApiError) as raised:
        asyncio.run(
            _proxy_to_ollama(
                "/api/generate",
                {"prompt": "Bitte rm -rf /tmp/test ausführen", "stream": False},
                "Bitte rm -rf /tmp/test ausführen",
                session=object(),
                client_name="client-a",
            )
        )

    assert raised.value.code == "request_blocked"
    assert raised.value.status_code == 403
    assert len(history_calls) == 1
    assert history_calls[0]["success"] is False
    assert history_calls[0]["error_code"] == "request_blocked"
