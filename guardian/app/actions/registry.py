"""Declarative action whitelist.

Every recovery action must be declared in ``guardian.yaml`` (``actions.allow``).
The registry exposes only those rules; there is no path to run an arbitrary
command. Lookups are by stable rule id or by (kind, target).
"""

from __future__ import annotations

from guardian.app.actions.models import GuardianActionKind
from guardian.app.config.models import ActionRule, ActionsConfig

_VALID_KINDS = {k.value for k in GuardianActionKind}


class GuardianActionRegistry:
    def __init__(self, config: ActionsConfig) -> None:
        self._config = config
        self._by_id: dict[str, ActionRule] = {}
        self._by_kind_target: dict[tuple[str, str], ActionRule] = {}
        for rule in config.allow:
            if not rule.enabled:
                continue
            if rule.kind not in _VALID_KINDS:
                continue
            self._by_id[rule.id] = rule
            self._by_kind_target[(rule.kind, rule.target)] = rule

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def dry_run(self) -> bool:
        return self._config.dry_run

    @property
    def config(self) -> ActionsConfig:
        return self._config

    def all_rules(self) -> list[ActionRule]:
        return list(self._by_id.values())

    def get(self, action_id: str) -> ActionRule | None:
        return self._by_id.get(action_id)

    def find(self, kind: str, target: str) -> ActionRule | None:
        return self._by_kind_target.get((kind, target))
