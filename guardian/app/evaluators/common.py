from __future__ import annotations

# Re-export from core to keep a single definition while avoiding an import cycle
# between the evaluators package and the docker/systemd evaluator modules.
from guardian.app.core.evaluation import GuardianEvaluationReason

__all__ = ["GuardianEvaluationReason"]
