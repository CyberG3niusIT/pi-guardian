from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from app.api.import_helpers import fetch_json_from_github, normalize_github_url
from app.agents.registry import get_agent
from app.database import get_session
from app.models.skill_models import (
    SkillCreateRequest,
    SkillDefinition,
    SkillImportRequest,
    SkillImportResponse,
    SkillUpdateRequest,
)
from app.skills.registry import (
    create_skill,
    delete_skill,
    disable_skill,
    enable_skill,
    get_skill,
    get_skill_any,
    is_skill_enabled,
    list_all_skills,
    update_skill,
)
from app.router.auth import authorize_protected_request

router = APIRouter(prefix="/skills", tags=["skills"])


def require_skills_access(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    authorize_protected_request(request, session, "/skills")


def _skill_definition(skill, *, enabled: bool = True) -> SkillDefinition:
    return SkillDefinition(
        name=skill.name,
        description=skill.description,
        skill_type=getattr(skill, "skill_type", "system"),
        allowed_tools=list(skill.allowed_tools),
        input_schema=getattr(skill, "input_schema_json", skill.input_schema.model_json_schema()),
        output_schema=getattr(skill, "output_schema_json", skill.output_schema.model_json_schema()),
        prompt_template=getattr(skill, "prompt_template", None),
        preferred_model=getattr(skill, "preferred_model", None),
        source_url=getattr(skill, "source_url", None),
        read_only=skill.read_only,
        version=skill.version,
        enabled=enabled,
    )


@router.get("", response_model=list[SkillDefinition], dependencies=[Depends(require_skills_access)])
async def skills_list() -> list[SkillDefinition]:
    return [
        _skill_definition(skill, enabled=is_skill_enabled(skill.name))
        for skill in list_all_skills()
    ]


@router.get(
    "/{skill_name}",
    response_model=SkillDefinition,
    dependencies=[Depends(require_skills_access)],
)
async def skill_detail(skill_name: str) -> SkillDefinition:
    skill = get_skill_any(skill_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill nicht gefunden")
    return _skill_definition(skill, enabled=is_skill_enabled(skill_name))


def _map_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    if "existiert bereits" in detail:
        status_code = status.HTTP_409_CONFLICT
    elif "nicht gefunden" in detail:
        status_code = status.HTTP_404_NOT_FOUND
    elif "dürfen nicht" in detail:
        status_code = status.HTTP_403_FORBIDDEN
    return HTTPException(status_code=status_code, detail=detail)


def _extract_skill_requests(payload: dict) -> list[SkillCreateRequest]:
    raw_skills = payload.get("skills")
    if isinstance(raw_skills, list):
        return [SkillCreateRequest.model_validate(item) for item in raw_skills]
    if {"name", "description", "prompt_template"}.issubset(payload.keys()):
        return [SkillCreateRequest.model_validate(payload)]
    raise ValueError("JSON muss entweder 'skills' oder eine einzelne Skill-Definition enthalten")


@router.post(
    "",
    response_model=SkillDefinition,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_skills_access)],
)
async def skill_create(payload: SkillCreateRequest) -> SkillDefinition:
    try:
        definition = create_skill(payload)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    skill = get_skill_any(definition.name)
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill wurde erstellt, konnte aber nicht geladen werden")
    return _skill_definition(skill, enabled=is_skill_enabled(definition.name))


@router.put(
    "/{skill_name}",
    response_model=SkillDefinition,
    dependencies=[Depends(require_skills_access)],
)
async def skill_update(skill_name: str, payload: SkillUpdateRequest) -> SkillDefinition:
    try:
        definition = update_skill(skill_name, payload)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    skill = get_skill_any(definition.name)
    if skill is None:
        raise HTTPException(status_code=500, detail="Skill wurde aktualisiert, konnte aber nicht geladen werden")
    return _skill_definition(skill, enabled=is_skill_enabled(definition.name))


@router.delete(
    "/{skill_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_skills_access)],
)
async def skill_delete(skill_name: str) -> Response:
    try:
        delete_skill(skill_name)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{skill_name}/enable",
    response_model=SkillDefinition,
    dependencies=[Depends(require_skills_access)],
)
async def skill_enable(skill_name: str) -> SkillDefinition:
    try:
        skill = get_skill_any(skill_name)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")
        enable_skill(skill_name)
        return _skill_definition(skill, enabled=True)
    except ValueError as exc:
        raise _map_value_error(exc) from exc


@router.post(
    "/{skill_name}/disable",
    response_model=SkillDefinition,
    dependencies=[Depends(require_skills_access)],
)
async def skill_disable(skill_name: str) -> SkillDefinition:
    try:
        skill = get_skill_any(skill_name)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill nicht gefunden")
        disable_skill(skill_name)
        return _skill_definition(skill, enabled=False)
    except ValueError as exc:
        raise _map_value_error(exc) from exc


@router.post(
    "/import/",
    response_model=SkillImportResponse,
    dependencies=[Depends(require_skills_access)],
)
async def skill_import(payload: SkillImportRequest) -> SkillImportResponse:
    if payload.github_url:
        try:
            raw_payload = fetch_json_from_github(payload.github_url)
            # Manifest-Logik: Falls es ein Manifest ist, Einträge nachladen
            if "entries" in raw_payload:
                requests = []
                branch = raw_payload.get("branch", "main")
                base_url = "/".join(payload.github_url.rstrip("/").rstrip(".git").split("/")[:5])
                for entry in raw_payload["entries"]:
                    if entry.get("type") == "skill":
                        file_url = f"{base_url}/blob/{branch}/{entry['path']}"
                        skill_data = fetch_json_from_github(file_url)
                        requests.append(SkillCreateRequest.model_validate(skill_data))
                source = normalize_github_url(payload.github_url)
                skill_type = "github_imported"
            else:
                requests = _extract_skill_requests(raw_payload)
                source = normalize_github_url(payload.github_url)
                skill_type = "github_imported"
        except ValueError as exc:
            raise _map_value_error(exc) from exc
    else:
        if not payload.skills:
            raise HTTPException(status_code=422, detail="Entweder github_url oder skills angeben")
        requests = payload.skills
        source = "manual"
        skill_type = "custom"

    imported: list[SkillDefinition] = []
    try:
        for request in requests:
            request_payload = request.model_copy(
                update={"source_url": source if source != "manual" else request.source_url}
            )
            definition = create_skill(request_payload, skill_type=skill_type)
            imported.append(definition)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    return SkillImportResponse(imported_skills=imported, source=source)
