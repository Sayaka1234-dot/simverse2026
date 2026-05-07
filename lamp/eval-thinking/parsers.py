"""Parse a model reply into the lamp task's `FINAL_JSON: {...}` payload.

Per docs/EVAL_CONTRACT.md §3, every task implements `extract_final_json(raw_text)`
that returns `(final_json_text, parsed_dict)` and raises `ModelOutputParseError`
on malformed output. This module also adds lamp-specific structural validation.
"""
from __future__ import annotations

import json
from typing import Any

from eval_common.schemas import LampTask, ParsedAnswer


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
    """Returns (reasoning_text, final_block_starting_with_FINAL_JSON_marker)."""
    stripped = raw_text.strip()
    marker_index = stripped.rfind(FINAL_JSON_MARKER)
    if marker_index == -1:
        return "", stripped
    return stripped[:marker_index].strip(), stripped[marker_index:].strip()


def extract_final_json(raw_text: str) -> tuple[str, dict[str, Any]]:
    """Per docs/EVAL_CONTRACT.md §3.

    Returns (final_json_text, parsed_dict). final_json_text is the literal JSON
    portion (with the FINAL_JSON: prefix stripped, no surrounding code fences).
    """
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

    # Fallback: bare JSON object, possibly inside ``` fences.
    body = stripped
    if body.startswith("```"):
        parts = body.split("```")
        for part in parts:
            piece = part.strip()
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


# ---------- lamp-specific structural validation ----------

def _coerce_int(name: str, value: Any, raw_text: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ModelOutputParseError(
            f"{name} must be an integer.", raw_text=raw_text, error_kind="validation"
        ) from exc


def parse_lamp_answer(
    raw_text: str,
    task: LampTask,
    *,
    allow_missing_joints: bool = False,
    missing_joint_default_angle: int = 0,
) -> ParsedAnswer:
    """Extract FINAL_JSON, then enforce lamp's actions schema.

    On success returns a ParsedAnswer. On any structural failure raises
    ModelOutputParseError with `error_kind` set to "json_parse" or "validation".
    """
    _, payload = extract_final_json(raw_text)

    if set(payload.keys()) != {"actions"}:
        raise ModelOutputParseError(
            "Top-level JSON must contain exactly one key: actions.",
            raw_text=raw_text,
            error_kind="validation",
        )

    raw_actions = payload.get("actions")
    if not isinstance(raw_actions, list):
        raise ModelOutputParseError(
            "actions must be a list.", raw_text=raw_text, error_kind="validation"
        )

    segment_count = task.segment_count
    constraints = task.angle_constraints
    angle_min = int(constraints["min"])
    angle_max = int(constraints["max"])
    angle_step = int(constraints["step"])

    if allow_missing_joints:
        if len(raw_actions) > segment_count:
            raise ModelOutputParseError(
                "actions length cannot exceed segment_count.",
                raw_text=raw_text,
                error_kind="validation",
            )
    elif len(raw_actions) != segment_count:
        raise ModelOutputParseError(
            "actions length must match segment_count.",
            raw_text=raw_text,
            error_kind="validation",
        )

    normalized: list[dict[str, int]] = []
    seen_joints: set[int] = set()

    for item in raw_actions:
        if not isinstance(item, dict):
            raise ModelOutputParseError(
                "Each action must be an object.",
                raw_text=raw_text,
                error_kind="validation",
            )
        joint = _coerce_int("joint", item.get("joint"), raw_text)
        angle = _coerce_int("angle", item.get("angle"), raw_text)

        if joint < 1 or joint > segment_count:
            raise ModelOutputParseError(
                f"joint {joint} is outside 1..{segment_count}.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if joint in seen_joints:
            raise ModelOutputParseError(
                f"joint {joint} appears more than once.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if angle < angle_min or angle > angle_max:
            raise ModelOutputParseError(
                f"joint {joint} angle {angle} is outside [{angle_min}, {angle_max}].",
                raw_text=raw_text,
                error_kind="validation",
            )
        if (angle - angle_min) % angle_step != 0:
            raise ModelOutputParseError(
                f"joint {joint} angle {angle} does not match step {angle_step}.",
                raw_text=raw_text,
                error_kind="validation",
            )

        seen_joints.add(joint)
        normalized.append({"joint": joint, "angle": angle})

    if allow_missing_joints:
        default_angle = int(missing_joint_default_angle)
        if default_angle < angle_min or default_angle > angle_max:
            raise ModelOutputParseError(
                "missing-joint default angle is outside the allowed range.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if (default_angle - angle_min) % angle_step != 0:
            raise ModelOutputParseError(
                "missing-joint default angle does not match the allowed step.",
                raw_text=raw_text,
                error_kind="validation",
            )
        for joint in sorted(set(range(1, segment_count + 1)) - seen_joints):
            normalized.append({"joint": joint, "angle": default_angle})
    else:
        if seen_joints != set(range(1, segment_count + 1)):
            raise ModelOutputParseError(
                "actions must cover every joint exactly once.",
                raw_text=raw_text,
                error_kind="validation",
            )

    normalized.sort(key=lambda item: item["joint"])
    return ParsedAnswer(
        actions=normalized,
        angles=[item["angle"] for item in normalized],
        raw_text=raw_text,
    )
