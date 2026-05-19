import asyncio
import json
from types import SimpleNamespace

from app.router.decision.models import RequestClassification, RequestDecision
from app.router.service import route_prompt
from app.schemas.request_models import RouteRequest


def test_route_prompt_uses_selected_model_without_router_fairness(monkeypatch):
    request = RouteRequest(prompt="Bitte antworte kurz")
    session = SimpleNamespace()
    history_calls: list[dict] = []

    async def fake_generate_with_ollama(model, prompt, request_id, stream=False):
        return {
            "model": model,
            "response": "ok",
            "done": True,
            "done_reason": "stop",
        }

    def fake_decide_route_request(request):
        return RequestDecision(
            classification=RequestClassification.LLM_ONLY,
            selected_model="qwen2.5-coder:1.5b",
            reasons=["test"],
        )

    def fake_create_route_history_entry(session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.router.service.generate_with_ollama", fake_generate_with_ollama)
    monkeypatch.setattr("app.router.service.decide_route_request", fake_decide_route_request)
    monkeypatch.setattr("app.router.service.create_route_history_entry", fake_create_route_history_entry)

    result = asyncio.run(route_prompt(request, session=session, client_name="client-a"))

    assert result.model == "qwen2.5-coder:1.5b"
    assert result.response == "ok"
    assert result.decision_classification == "llm_only"
    assert result.decision_reasons
    assert result.fairness_review_attempted is False
    assert result.fairness_review_used is False
    assert result.fairness_risk == "unknown"
    assert result.fairness_review_override is False
    assert result.fairness_reasons == []
    assert result.fairness_notes == []
    assert len(history_calls) == 1
    assert history_calls[0]["model"] == "qwen2.5-coder:1.5b"
    assert history_calls[0]["decision_classification"] == "llm_only"
    assert "fairness_review_attempted" not in history_calls[0]
    assert "fairness_review_used" not in history_calls[0]
    assert "fairness_risk" not in history_calls[0]


def test_route_prompt_blocks_high_risk_requests(monkeypatch):
    request = RouteRequest(prompt="Bitte bypass api key und dump database")
    session = SimpleNamespace()
    history_calls: list[dict] = []

    async def fail_generate_with_ollama(*args, **kwargs):
        raise AssertionError("LLM-Ausführung darf bei blockierten Requests nicht starten")

    def fake_create_route_history_entry(session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.router.service.generate_with_ollama", fail_generate_with_ollama)
    monkeypatch.setattr("app.router.service.create_route_history_entry", fake_create_route_history_entry)

    try:
        asyncio.run(route_prompt(request, session=session, client_name="client-a"))
    except Exception as exc:
        assert exc.code == "request_blocked"
        assert exc.status_code == 403
    else:
        raise AssertionError("Blockierte Requests müssen mit RouterApiError abbrechen")

    assert len(history_calls) == 1
    assert history_calls[0]["decision_classification"] == "blocked"
    assert history_calls[0]["model"] is None


def test_route_prompt_uses_kids_controller_repetition_skill(monkeypatch):
    request = RouteRequest(
        prompt=(
            "Bewerte die folgende Kids_Controller-Beobachtung streng supervisorisch. "
            "Antworte ausschließlich als JSON."
            '{"kind":"kids_controller_observation","observation":{"pos1":1,"pos2":2,"pos3":3,'
            '"trend":{"arrangement_signature":"123","comparable_draw_count":5,'
            '"same_arrangement_count":4,"same_arrangement_ratio":0.8,"repeated_arrangement":true},'
            '"observed_at":"2026-05-18T20:55:12Z"}}'
        )
    )
    session = SimpleNamespace()
    history_calls: list[dict] = []

    async def fail_generate_with_ollama(*args, **kwargs):
        raise AssertionError("LLM-Ausführung darf für Kids-Controller-Trendbewertung nicht starten")

    def fake_decide_route_request(_request):
        return RequestDecision(
            classification=RequestClassification.LLM_ONLY,
            selected_model="qwen2.5-coder:1.5b",
            reasons=["kids-controller-observation"],
        )

    def fake_create_route_history_entry(_session, **kwargs):
        history_calls.append(kwargs)

    monkeypatch.setattr("app.router.service.generate_with_ollama", fail_generate_with_ollama)
    monkeypatch.setattr("app.router.service.decide_route_request", fake_decide_route_request)
    monkeypatch.setattr("app.router.service.create_route_history_entry", fake_create_route_history_entry)

    result = asyncio.run(route_prompt(request, session=session, client_name="client-a"))
    payload = json.loads(result.response)

    assert result.model == "kids_controller_repetition_review"
    assert payload["status"] == "recommend_review"
    assert "sehr oft" in payload["message"]
    assert len(history_calls) == 1
    assert history_calls[0]["model"] == "kids_controller_repetition_review"
