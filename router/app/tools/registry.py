from __future__ import annotations

from collections.abc import Iterable

from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        name = tool.name.strip()
        if not name:
            raise ValueError("Tool-Name darf nicht leer sein")
        if name in self._tools:
            raise ValueError(f"Tool bereits registriert: {name}")
        self._tools[name] = tool

    def get(self, tool_name: str) -> BaseTool | None:
        return self._tools.get(tool_name)

    def list_tools(self) -> list[BaseTool]:
        return [self._tools[name] for name in sorted(self._tools)]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def ensure_allowed(self, allowed_tools: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for name in allowed_tools:
            stripped = name.strip()
            if not stripped:
                raise ValueError("allowed_tools enthält leere Einträge")
            if stripped not in self._tools:
                raise ValueError(f"Unbekanntes Tool: {stripped}")
            if stripped not in normalized:
                normalized.append(stripped)
        return normalized


registry = ToolRegistry()


def register_tool(tool: BaseTool) -> None:
    registry.register(tool)


def get_tool(tool_name: str) -> BaseTool | None:
    return registry.get(tool_name)


def list_tools() -> list[BaseTool]:
    return registry.list_tools()


def list_tool_names() -> list[str]:
    return registry.names()


from app.tools.docker_status_tool import DockerStatusTool
from app.tools.guardian_action_tool import GuardianActionTool
from app.tools.guardian_status_tool import GuardianStatusTool
from app.tools.router_logs_tool import RouterLogsTool
from app.tools.service_status_tool import ServiceStatusTool
from app.tools.system_status_tool import SystemStatusTool


for _tool in (
    SystemStatusTool(),
    DockerStatusTool(),
    ServiceStatusTool(),
    RouterLogsTool(),
    GuardianStatusTool(),
    GuardianActionTool(),
):
    registry.register(_tool)
