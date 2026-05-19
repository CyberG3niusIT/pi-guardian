# Router AirPI Fast Lane

## Purpose

The router can use AirPI's `fast` model alias for low-latency LLM-only requests.

The fast lane is a latency feature. It is not a policy authority.

## Safety Rules

- Deterministic block rules run before every `/route` model call.
- The Ollama-compatible proxy paths `/api/generate` and `/api/chat` also run the deterministic block gate before forwarding to AirPI/Ollama.
- Fast-lane route decisions must be valid JSON with `decision`, `risk` and `reason`.
- Invalid fast-lane JSON escalates once to `DEFAULT_MODEL`.
- Valid fast-lane JSON with `decision=block`, `decision=review`, `decision=tool_required` or `risk=high` is blocked with `fast_lane_policy_block`.
- Destructive-action blocking must stay deterministic and must not depend on model output.

## Operational Notes

The default model remains the quality fallback.

Fast-lane failures should be treated as inference-quality issues, not as authorization to proceed.

