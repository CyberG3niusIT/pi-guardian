"""Shared evaluation primitives.

Lives in ``core`` (depending only on :mod:`guardian.app.core.domain`) so that
every evaluator — including the docker/systemd ones imported by the evaluators
package — can use it without creating an import cycle through
``guardian.app.evaluators``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from guardian.app.core.domain import GuardianSeverity, GuardianSignalSource


class GuardianEvaluationReason(BaseModel):
    code: str
    summary: str
    severity: GuardianSeverity
    source: GuardianSignalSource
    detail: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
