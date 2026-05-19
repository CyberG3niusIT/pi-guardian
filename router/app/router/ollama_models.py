import logging

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_models() -> list[dict]:
    url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("ollama_models: Ollama nicht erreichbar: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama nicht erreichbar")

    models = []
    for m in data.get("models", []):
        size_bytes = m.get("size", 0)
        size_str = f"{size_bytes / (1024 ** 2):.0f} MB" if size_bytes else "–"
        models.append({
            "name": m.get("name", ""),
            "size": size_str,
            "modified_at": m.get("modified_at", ""),
            "digest": m.get("digest", ""),
        })
    return models


async def fetch_model_names() -> set[str]:
    return {model["name"] for model in await fetch_models() if model.get("name")}


async def delete_ollama_model(name: str) -> None:
    url = f"{settings.OLLAMA_BASE_URL}/api/delete"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, json={"name": name})
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Modell '{name}' nicht gefunden")
            response.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("ollama_models: delete fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama nicht erreichbar")


async def fetch_raw_tags() -> dict:
    url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.warning("ollama_models raw tags: Ollama nicht erreichbar: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama nicht erreichbar")
