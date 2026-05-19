from __future__ import annotations

import re

from app.router.classifier import select_model
from app.router.decision.models import RequestClassification, RequestDecision
from app.schemas.request_models import RouteRequest

_BLOCK_KEYWORDS = (
    "bypass api key",
    "disable security",
    "steal password",
    "dump database",
    "delete database",
    "exfiltrate",
)

_INTERNET_KEYWORDS = (
    "internet",
    "online",
    "web",
    "website",
    "recherchiere",
    "suche im netz",
    "browse",
    "url",
    "http://",
    "https://",
)

_TOOL_HINTS = {
    "system_status": ("systemstatus", "system status", "cpu", "ram", "speicher", "last"),
    "docker_status": ("docker", "container", "compose", "image", "images"),
    "service_status": ("service", "dienst", "systemd", "service-status", "dienststatus", "uptime", "pid"),
    "router_logs": ("log", "logs", "journal", "fehlermeldung", "traceback"),
}


def _contains_tool_keyword(prompt_lower: str, keyword: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(keyword)}(?![\w-])", prompt_lower) is not None


def classify_request(request: RouteRequest) -> RequestDecision:
    prompt = request.prompt.strip()
    prompt_lower = prompt.lower()

    for keyword in _BLOCK_KEYWORDS:
        if keyword in prompt_lower:
            return RequestDecision(
                classification=RequestClassification.BLOCKED,
                selected_model=None,
                blocked=True,
                reasons=[
                    "Anfrage fällt in eine geblockte Hochrisiko-Kategorie",
                    f"Treffer auf Block-Keyword: {keyword}",
                ],
            )

    if any(keyword in prompt_lower for keyword in _INTERNET_KEYWORDS):
        return RequestDecision(
            classification=RequestClassification.INTERNET_REQUIRED,
            selected_model=select_model(request),
            reasons=[
                "Anfrage deutet auf externen Wissens- oder Web-Bedarf hin",
            ],
            internet_hints=["web_lookup"],
        )

    matched_tools: list[str] = []
    for tool_name, keywords in _TOOL_HINTS.items():
        if any(_contains_tool_keyword(prompt_lower, keyword) for keyword in keywords):
            matched_tools.append(tool_name)

    if matched_tools:
        return RequestDecision(
            classification=RequestClassification.TOOL_REQUIRED,
            selected_model=select_model(request),
            reasons=[
                "Anfrage enthält starke Signale für lokale System- oder Router-Werkzeuge",
            ],
            tool_hints=matched_tools,
        )

    return RequestDecision(
        classification=RequestClassification.LLM_ONLY,
        selected_model=select_model(request),
        reasons=["Anfrage kann ohne Tool- oder Internetzugriff beantwortet werden"],
    )
