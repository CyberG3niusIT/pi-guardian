from __future__ import annotations

from app.models.agent_models import AgentDefinition, AgentRunState
from app.actions.registry import list_action_names
from app.skills.registry import list_skills
from app.tools.registry import list_tools
from app.memory.agent_memory import get_agent_memories


def _render_history(state: AgentRunState) -> str:
    if not state.context_history:
        return "- Keine vorherigen Schritte."

    lines: list[str] = []
    for step in state.context_history:
        payload = step.tool_call_or_response
        lines.append(
            f"- Schritt {step.step_number} [{step.action}]: {payload} | Beobachtung: {step.observation or '-'}"
        )
    return "\n".join(lines)


def _render_tool_catalog(agent: AgentDefinition) -> str:
    lines: list[str] = []
    for tool in list_tools():
        if tool.name not in agent.allowed_tools:
            continue
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines) if lines else "- Keine Tools registriert."


def _render_skill_catalog(agent: AgentDefinition) -> str:
    lines: list[str] = []
    for skill in list_skills():
        if skill.name not in agent.settings.policy.allowed_skills:
            continue
        lines.append(f"- {skill.name}: {skill.description}")
    return "\n".join(lines) if lines else "- Keine Skills registriert."


def _render_memory(agent: AgentDefinition) -> str:
    memories = get_agent_memories(agent.name, limit=5)
    if not memories:
        return "- Keine gespeicherten Erfahrungen."
    lines = []
    type_labels = {
        "finding": "BEOBACHTUNG",
        "failure": "FEHLERMUSTER",
        "feedback": "FEEDBACK",
        "instruction": "HINWEIS",
    }
    for m in memories:
        label = type_labels.get(m.memory_type, m.memory_type.upper())
        confirmed = f" (bestätigt: {m.times_confirmed}x)" if m.times_confirmed > 0 else ""
        lines.append(f"- [{label}]{confirmed} {m.content}")
    return "\n".join(lines)


def _render_action_catalog(agent: AgentDefinition) -> str:
    lines: list[str] = []
    for action_name in list_action_names():
        if action_name not in agent.settings.policy.allowed_actions:
            continue
        lines.append(f"- {action_name}")
    return "\n".join(lines) if lines else "- Keine Actions registriert."


def build_system_prompt(agent: AgentDefinition) -> str:
    settings = agent.settings
    policy = settings.policy

    # Tool list with descriptions
    tool_lines = [
        f"  {tool.name}: {tool.description}"
        for tool in list_tools()
        if tool.name in agent.allowed_tools
    ]

    # Skill list with descriptions
    skill_lines = [
        f"  {skill.name}: {skill.description}"
        for skill in list_skills()
        if skill.name in policy.allowed_skills
    ]

    # Action list
    action_lines = [
        f"  {name}"
        for name in list_action_names()
        if name in policy.allowed_actions
    ]

    lines = [
        f"Du bist {agent.name}, ein PI-Guardian-Monitoring-Agent auf einem Raspberry Pi.",
        f"Aufgabe: {agent.description}",
        "",
        "Verfügbare Tools:",
    ]
    lines.extend(tool_lines or ["  (keine)"])

    lines += ["", "Verfügbare Skills:"]
    lines.extend(skill_lines or ["  (keine)"])

    if action_lines:
        lines += ["", "Verfügbare Actions (Freigabe immer erforderlich):"]
        lines.extend(action_lines)

    lines += [
        "",
        "Ausgaberegeln:",
        '- Tool aufrufen → nur dieses JSON ausgeben: {"tool_name":"NAME","arguments":{},"reason":"WARUM"}',
        '- Skill aufrufen → nur dieses JSON ausgeben: {"skill_name":"NAME","arguments":{},"reason":"WARUM"}',
    ]
    if policy.can_propose_actions:
        lines.append(
            '- Action vorschlagen → nur dieses JSON ausgeben: '
            '{"action_name":"NAME","arguments":{},"reason":"WARUM","target":"DIENST","requires_approval":true}'
        )
    lines += [
        "- Kein Text vor oder nach dem JSON-Objekt.",
        "- Abschließende Antwort als normaler Text ohne JSON.",
    ]

    if agent.name == "kids_controller_supervisor":
        lines += [
            "- Fuer diesen Agenten gilt: Im ersten inhaltlichen Schritt zuerst den Skill "
            '"kids_controller_repetition_review" aufrufen, keine freie Analyse als Erstantwort.',
            "- Nach einem erfolgreichen Skill-Resultat nur 1-2 kurze deutsche Saetze als Abschluss.",
            "- Keine Rubriken, keine LOGIC-Bloecke, keine Wiederholungen, keine Aufzaehlungen.",
        ]

    if settings.custom_instruction:
        lines += ["", "Arbeitshinweis:", settings.custom_instruction]

    return "\n".join(lines)


def build_prompt(
    agent: AgentDefinition,
    user_prompt: str,
    state: AgentRunState,
) -> str:
    return (
        f"=== SYSTEM ===\n{agent.system_prompt}\n\n"
        f"=== GEDÄCHTNIS ===\n{_render_memory(agent)}\n\n"
        f"=== TOOL CATALOG ===\n{_render_tool_catalog(agent)}\n\n"
        f"=== SKILL CATALOG ===\n{_render_skill_catalog(agent)}\n\n"
        f"=== ACTION CATALOG ===\n{_render_action_catalog(agent)}\n\n"
        f"=== STEP STATE ===\n"
        f"- Aktueller Schritt: {state.current_step}/{state.max_steps}\n"
        f"- Tool-Aufrufe bisher: {state.tool_call_count}\n"
        f"- Skill-Aufrufe bisher: {state.skill_call_count}\n"
        f"- Abgeschlossen: {state.completed}\n\n"
        f"=== HISTORY ===\n{_render_history(state)}\n\n"
        f"=== USER REQUEST ===\n{user_prompt}\n\n"
        "=== OUTPUT RULES ===\n"
        "- Wenn du ein Tool aufrufen willst, antworte nur mit dem JSON-Objekt.\n"
        "- Wenn du einen Skill aufrufen willst, antworte nur mit dem JSON-Objekt.\n"
        "- Wenn du fertig bist, antworte in normalem Klartext ohne JSON.\n"
        "- Keine weiteren Metadaten, keine Codeblöcke, keine Prosa vor oder nach dem JSON.\n"
    )
