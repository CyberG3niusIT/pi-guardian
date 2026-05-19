from app.router.inference import wrapper
from app.router.inference.wrapper import TIMEOUT_AGENT, TIMEOUT_ROUTE


async def generate_with_ollama(
    model: str,
    prompt: str,
    request_id: str,
    stream: bool = False,
    timeout: float = TIMEOUT_ROUTE,
    session_id: str | None = None,
    format: str | None = None,
    response_format: str | None = None,
    required_json_keys: list[str] | None = None,
) -> dict:
    return await wrapper.generate(
        model,
        prompt,
        request_id,
        stream=stream,
        timeout=timeout,
        session_id=session_id,
        format=format,
        response_format=response_format,
        required_json_keys=required_json_keys,
    )


async def post_to_ollama(
    path: str,
    payload: dict,
    request_id: str,
    model: str,
    timeout: float = TIMEOUT_ROUTE,
) -> dict:
    return await wrapper.post(path, payload, request_id, model, timeout=timeout)


def stream_to_ollama(
    path: str,
    payload: dict,
    request_id: str,
    model: str,
    timeout: float = TIMEOUT_AGENT,
):
    return wrapper.stream_response(path, payload, request_id, model, timeout=timeout)
