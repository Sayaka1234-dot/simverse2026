"""Parse a cube2 model reply into the locked `FINAL_JSON: {"directions": [...]}` schema.

Per docs/EVAL_CONTRACT.md §3, every task implements:
    extract_final_json(raw_text) -> (final_json_text, parsed_dict)

This module also adds cube2-specific structural validation (direction tokens
restricted to N/S/E/W, sequence length within `DEFAULT_MAX_DIRECTION_STEPS`).
"""
from __future__ import annotations

import json
from typing import Any

from eval_common import (
    DEFAULT_MAX_DIRECTION_STEPS,
    ModelAnswer,
    ModelOutputParseError,
    VALID_DIRECTIONS,
)


FINAL_JSON_MARKER = "FINAL_JSON:"
_VALID_DIRECTIONS_SET = set(VALID_DIRECTIONS)


# ---------- generic FINAL_JSON extraction ----------

def _extract_balanced_json_object(text: str, *, start_index: int = 0) -> str | None:
    object_start = text.find("{", start_index)
    if object_start == -1:
        return None
    depth = 0
    in_string = False
    is_escaped = False
    for index in range(object_start, len(text)):
        char = text[index]
        if in_string:
            if is_escaped:
                is_escaped = False
            elif char == "\\":
                is_escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[object_start : index + 1]
    return None


def split_reasoning_and_final(raw_text: str) -> tuple[str, str]:
    stripped = raw_text.strip()
    marker_index = stripped.rfind(FINAL_JSON_MARKER)
    if marker_index == -1:
        return "", stripped
    return stripped[:marker_index].strip(), stripped[marker_index:].strip()


def extract_final_json(raw_text: str) -> tuple[str, dict[str, Any]]:
    stripped = raw_text.strip()
    marker_index = stripped.rfind(FINAL_JSON_MARKER)
    if marker_index != -1:
        candidate = _extract_balanced_json_object(
            stripped, start_index=marker_index + len(FINAL_JSON_MARKER)
        )
        if candidate is None:
            raise ModelOutputParseError(
                "FINAL_JSON: marker found but no balanced JSON object after it.",
                raw_text=raw_text,
            )
        try:
            return candidate, json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ModelOutputParseError(
                f"FINAL_JSON payload is not valid JSON: {exc}",
                raw_text=raw_text,
            ) from exc

    body = stripped
    if body.startswith("```"):
        for piece in body.split("```"):
            piece = piece.strip()
            if piece.startswith("{"):
                candidate = _extract_balanced_json_object(piece)
                if candidate is not None:
                    try:
                        return candidate, json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
    candidate = _extract_balanced_json_object(body)
    if candidate is not None:
        try:
            return candidate, json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ModelOutputParseError(
                f"Inline JSON payload is not valid JSON: {exc}",
                raw_text=raw_text,
            ) from exc

    raise ModelOutputParseError(
        "Model output does not contain a FINAL_JSON line nor a JSON object.",
        raw_text=raw_text,
    )


# ---------- cube2-specific structural validation ----------

def parse_cube2_answer(raw_text: str, sample_id: str) -> ModelAnswer:
    """Extract FINAL_JSON, then enforce the directions schema.

    Returns a ModelAnswer with normalized uppercase directions. Raises
    ModelOutputParseError on structural failure.
    """
    _, payload = extract_final_json(raw_text)
    if not isinstance(payload, dict):
        raise ModelOutputParseError("Top-level JSON must be an object.", raw_text=raw_text)
    if set(payload.keys()) != {"directions"}:
        raise ModelOutputParseError(
            "Top-level JSON must contain exactly one key: directions.",
            raw_text=raw_text,
        )
    directions = payload["directions"]
    if not isinstance(directions, list) or not directions:
        raise ModelOutputParseError(
            "directions must be a non-empty list.", raw_text=raw_text
        )
    if len(directions) > DEFAULT_MAX_DIRECTION_STEPS:
        raise ModelOutputParseError(
            f"directions length {len(directions)} exceeds the limit "
            f"{DEFAULT_MAX_DIRECTION_STEPS}.",
            raw_text=raw_text,
        )
    normalized: list[str] = []
    for index, item in enumerate(directions, start=1):
        token = str(item).strip().upper()
        if token not in _VALID_DIRECTIONS_SET:
            raise ModelOutputParseError(
                f"directions[{index - 1}] {item!r} is not in {sorted(_VALID_DIRECTIONS_SET)}.",
                raw_text=raw_text,
            )
        normalized.append(token)
    return ModelAnswer(sample_id=sample_id, directions=normalized, raw_text=raw_text)
