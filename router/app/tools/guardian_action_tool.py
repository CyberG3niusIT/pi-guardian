from __future__ import annotations

import os

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_models import ToolResult
from app.tools.base import BaseTool
from app.tools.guardian_status_tool import _guardian_base_url, _guardian_headers


class GuardianActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(..., min_length=1, description="ID einer in Guardian gewhitelisteten Aktion")


class GuardianActionTool(BaseTool):
    """Triggers an allowed Guardian recovery action.

    The router can only *request* an action by id; Guardian remains the sole
    authority and still enforces its whitelist, cooldown and dry-run guards. A
    Guardian API key (GUARDIAN_API_KEY) is required when Guardian enforces auth.
    """

    name = "guardian_action"
    description = "Stoesst eine in Guardian erlaubte Recovery-Aktion an (Guardian entscheidet final)."
    input_schema = GuardianActionInput
    read_only = False
    category = "guardian"

    def execute(self, validated_input: BaseModel) -> ToolResult:
        action_id = getattr(validated_input, "action_id")
        url = f"{_guardian_base_url()}/actions/execute"
        try:
            response = httpx.post(
                url,
                headers={**_guardian_headers(), "Content-Type": "application/json"},
                json={"action_id": action_id},
                timeout=35.0,
            )
        except httpx.HTTPError as exc:
            return ToolResult(tool_name=self.name, success=False, error=f"Guardian nicht erreichbar: {exc}")

        if response.status_code in (401, 403):
            return ToolResult(tool_name=self.name, success=False, error="Guardian verweigerte die Aktion (Auth).")
        if response.status_code >= 400:
            return ToolResult(tool_name=self.name, success=False, error=f"Guardian-Action HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError:
            return ToolResult(tool_name=self.name, success=False, error="Guardian lieferte ungueltiges JSON.")

        return ToolResult(tool_name=self.name, success=True, output=payload)
