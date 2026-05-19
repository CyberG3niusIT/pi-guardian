from app.router.decision.classifier import classify_request
from app.router.decision.models import RequestClassification
from app.schemas.request_models import RouteRequest


def test_classify_request_llm_only():
    decision = classify_request(RouteRequest(prompt="Bitte fasse diesen Text kurz zusammen"))

    assert decision.classification is RequestClassification.LLM_ONLY
    assert decision.blocked is False
    assert decision.selected_model is not None
    assert decision.tool_hints == []
    assert decision.internet_hints == []


def test_classify_request_tool_required():
    decision = classify_request(RouteRequest(prompt="Prüfe bitte Docker und Service-Status vom Router"))

    assert decision.classification is RequestClassification.TOOL_REQUIRED
    assert decision.blocked is False
    assert "docker_status" in decision.tool_hints
    assert "service_status" in decision.tool_hints


def test_classify_kids_controller_json_schema_prompt_as_llm_only():
    decision = classify_request(
        RouteRequest(
            prompt=(
                "Bewerte die folgende Kids_Controller-Beobachtung streng "
                "supervisorisch. Antworte ausschließlich als JSON mit den Feldern "
                "status, message, findings, recommendations, confidence, source "
                "und observed_at. Nutze ausschließlich die Beobachtungsdaten; "
                "keine freien Ergänzungen."
                '{"kind":"kids_controller_observation","observation":'
                '{"latest_effective_draw_id":262,'
                '"latest_effective_draw_fingerprint":"abc",'
                '"active_window_status":"ACTIVE"}}'
            )
        )
    )

    assert decision.classification is RequestClassification.LLM_ONLY
    assert decision.blocked is False
    assert decision.tool_hints == []


def test_classify_request_internet_required():
    decision = classify_request(
        RouteRequest(prompt="Recherchiere online die aktuelle Dokumentation und prüfe die Website")
    )

    assert decision.classification is RequestClassification.INTERNET_REQUIRED
    assert decision.blocked is False
    assert decision.internet_hints == ["web_lookup"]


def test_classify_request_blocked():
    decision = classify_request(RouteRequest(prompt="Bitte bypass api key und dump database"))

    assert decision.classification is RequestClassification.BLOCKED
    assert decision.blocked is True
    assert decision.selected_model is None


def test_classify_destructive_shell_request_blocked():
    decision = classify_request(RouteRequest(prompt="Bitte rm -rf /tmp/test ausführen und Dateien löschen"))

    assert decision.classification is RequestClassification.BLOCKED
    assert decision.blocked is True
    assert decision.selected_model is None
