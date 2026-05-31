"""Load the Guardian operational configuration from YAML.

The YAML path defaults to ``guardian/config/guardian.yaml`` and can be
overridden with ``GUARDIAN_CONFIG_PATH``. A missing or empty file yields a
fully-defaulted :class:`GuardianConfig`, preserving the previous behaviour.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import yaml

from guardian.app.config.models import GuardianConfig

logger = logging.getLogger("guardian.config")

# guardian/app/config/loader.py -> parents[2] == guardian/
GUARDIAN_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = GUARDIAN_DIR / "config" / "guardian.yaml"


def config_path() -> Path:
    override = os.getenv("GUARDIAN_CONFIG_PATH", "").strip()
    return Path(override) if override else DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> GuardianConfig:
    """Read and validate the Guardian config; never raises on a missing file."""

    target = path or config_path()
    if not target.exists():
        logger.warning("Guardian-Konfiguration nicht gefunden (%s); nutze Defaults.", target)
        return GuardianConfig()

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.error("Guardian-Konfiguration konnte nicht gelesen werden (%s): %s", target, exc)
        return GuardianConfig()

    if not isinstance(raw, dict):
        logger.error("Guardian-Konfiguration hat ein ungueltiges Format (%s); nutze Defaults.", target)
        return GuardianConfig()

    try:
        config = GuardianConfig.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError and friends
        logger.error("Guardian-Konfiguration ist ungueltig (%s): %s; nutze Defaults.", target, exc)
        return GuardianConfig()

    logger.info("Guardian-Konfiguration geladen: %s", target)
    return config


@lru_cache(maxsize=1)
def get_config() -> GuardianConfig:
    """Process-wide cached config accessor used by the FastAPI app."""

    return load_config()
