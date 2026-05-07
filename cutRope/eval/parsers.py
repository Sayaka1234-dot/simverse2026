"""Parse a cutRope model reply into the locked
`FINAL_JSON: {"commands": "...", "reason": "...", "confidence": 0..1}` schema.

Per docs/EVAL_CONTRACT.md §3, every task implements:
    extract_final_json(raw_text) -> (final_json_text, parsed_dict)

This module also adds cutRope-specific structural validation (commands string
non-empty, no `wait_frames`, confidence in [0, 1]).
"""
from __future__ import annotations

import json
from typing import Any


FINAL_JSON_MARKER = "FINAL_JSON:"


class ModelOutputParseError(Exception):
    def __init__(self, message: str, raw_text: str = "", *, error_kind: str = "validation") -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.error_kind = error_kind


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
                error_kind="json_parse",
            )
        try:
            return candidate, json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ModelOutputParseError(
                f"FINAL_JSON payload is not valid JSON: {exc}",
                raw_text=raw_text,
                error_kind="json_parse",
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
                error_kind="json_parse",
            ) from exc

    raise ModelOutputParseError(
        "Model output does not contain a FINAL_JSON line nor a JSON object.",
        raw_text=raw_text,
        error_kind="json_parse",
    )


# ---------- cutRope-specific structural validation ----------

def parse_cutrope_answer(raw_text: str) -> dict[str, Any]:
    """Extract FINAL_JSON, then enforce the cutRope schema.

    Returns the parsed dict {commands, reason, confidence}. Raises
    ModelOutputParseError on structural failure.
    """
    _, payload = extract_final_json(raw_text)
    if not isinstance(payload, dict):
        raise ModelOutputParseError(
            "Top-level JSON must be an object.", raw_text=raw_text, error_kind="validation"
        )

    commands_value = payload.get("commands")
    if isinstance(commands_value, list):
        commands = "\n".join(str(item).strip() for item in commands_value if str(item).strip())
    elif isinstance(commands_value, str):
        commands = commands_value.strip()
    else:
        raise ModelOutputParseError(
            'Top-level JSON must contain "commands" as a string or list of strings.',
            raw_text=raw_text,
            error_kind="validation",
        )
    if not commands:
        raise ModelOutputParseError(
            'Top-level JSON "commands" is empty.',
            raw_text=raw_text,
            error_kind="validation",
        )
    if "wait_frames" in commands:
        raise ModelOutputParseError(
            "wait_frames is not allowed in this benchmark version.",
            raw_text=raw_text,
            error_kind="validation",
        )

    reason = str(payload.get("reason") or "").strip()

    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError) as exc:
        raise ModelOutputParseError(
            "confidence must be a number in [0, 1].",
            raw_text=raw_text,
            error_kind="validation",
        ) from exc
    if not (0.0 <= confidence <= 1.0):
        raise ModelOutputParseError(
            f"confidence {confidence} is outside [0, 1].",
            raw_text=raw_text,
            error_kind="validation",
        )

    return {
        "commands": commands,
        "reason": reason,
        "confidence": confidence,
    }
