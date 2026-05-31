from __future__ import annotations

import os

import httpx
from pydantic import BaseModel, ConfigDict

from app.models.agent_models import ToolResult
from app.tools.base import BaseTool


def _guardian_base_url() -> str:
    return os.getenv("GUARDIAN_BASE_URL", "http://127.0.0.1:8072").rstrip("/")


def _guardian_headers() -> dict[str, str]:
    api_key = os.getenv("GUARDIAN_API_KEY", "").strip()
    return {"X-API-Key": api_key} if api_key else {}


class GuardianStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GuardianStatusTool(BaseTool):
    name = "guardian_status"
    description = "Fragt den PI-Guardian-Watchdog nach dem aktuellen Gesamtzustand (read-only)."
    input_schema = GuardianStatusInput
    read_only = True
    category = "guardian"

    def execute(self, validated_input: BaseModel) -> ToolResult:
        del validated_input
        url = f"{_guardian_base_url()}/status"
        try:
            response = httpx.get(url, headers=_guardian_headers(), timeout=3.0)
        except httpx.HTTPError as exc:
            return ToolResult(tool_name=self.name, success=False, error=f"Guardian nicht erreichbar: {exc}")

        if response.status_code == 503:
            return ToolResult(tool_name=self.name, success=False, error="Guardian hat noch keinen Snapshot.")
        if response.status_code >= 400:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Guardian-Status HTTP {response.status_code}",
            )

        try:
            payload = response.json()
        except ValueError:
            return ToolResult(tool_name=self.name, success=False, error="Guardian lieferte ungueltiges JSON.")

        output = {
            "guardian_status": payload.get("guardian_status"),
            "router_status": payload.get("router_status"),
            "system_status": payload.get("system_status"),
            "systemd_status": payload.get("systemd_status"),
            "docker_status": payload.get("docker_status"),
            "overview_summary": payload.get("overview_summary"),
            "checked_at": payload.get("checked_at"),
        }
        return ToolResult(tool_name=self.name, success=True, output=output)
