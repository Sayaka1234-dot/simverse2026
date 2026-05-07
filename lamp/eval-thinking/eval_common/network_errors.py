from __future__ import annotations

from typing import Iterator

import httpx


def iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_openai_api_connection_error(exc: BaseException) -> bool:
    try:
        from openai import APIConnectionError
    except ModuleNotFoundError:
        return False

    return isinstance(exc, APIConnectionError)


def is_network_skip_error(exc: BaseException) -> bool:
    for current in iter_exception_chain(exc):
        if isinstance(current, (httpx.TimeoutException, httpx.RequestError)):
            return True
        if is_openai_api_connection_error(current):
            return True
    return False


def format_network_skip_message(sample_id: str, exc: BaseException) -> str:
    return f"[{sample_id}] network_error: {type(exc).__name__}: {exc}"


def format_skip_message(sample_id: str, exc: BaseException) -> str:
    if is_network_skip_error(exc):
        return format_network_skip_message(sample_id, exc)
    return f"[{sample_id}] error: {type(exc).__name__}: {exc}"


def extract_raw_model_output(exc: BaseException) -> str:
    raw_text = getattr(exc, "raw_text", "")
    if isinstance(raw_text, str):
        return raw_text.strip()
    return ""
