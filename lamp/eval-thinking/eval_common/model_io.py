from __future__ import annotations

import json
from typing import Any

from eval_common.schemas import ParsedAnswer

FINAL_JSON_MARKER = "FINAL_JSON:"


class ModelOutputParseError(Exception):
    def __init__(self, message: str, raw_text: str = "", *, error_kind: str = "validation") -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.error_kind = error_kind


def _load_json_or_raise(candidate: str, raw_text: str) -> dict[str, Any]:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelOutputParseError(str(exc), raw_text=raw_text, error_kind="json_parse") from exc


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
            continue

        if char == "{":
            depth += 1
            continue

        if char == "}":
            depth -= 1
            if depth == 0:
                return text[object_start : index + 1]

    return None


def build_chat_completion_request(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
    }


def extract_reasoning_content(message: Any) -> str:
    if message is None:
        return ""

    reasoning_parts: list[str] = []

    def append_text(value: Any) -> None:
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            text = value["text"].strip()
            if text:
                reasoning_parts.append(text)
            return
        text = extract_text_content(value)
        if text:
            reasoning_parts.append(text)

    if isinstance(message, dict):
        for key in ("reasoning_content", "reasoning", "thinking", "thoughts"):
            if key in message:
                append_text(message.get(key))
    else:
        for attr in ("reasoning_content", "reasoning", "thinking", "thoughts"):
            value = getattr(message, attr, None)
            if value is not None:
                append_text(value)
        model_extra = getattr(message, "model_extra", None)
        if isinstance(model_extra, dict):
            for key in ("reasoning_content", "reasoning", "thinking", "thoughts"):
                if key in model_extra:
                    append_text(model_extra.get(key))

    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_type = str(item.get("type", "")).lower()
                if item_type in {"reasoning", "thinking", "thought", "reasoning_content"}:
                    append_text(item)
            else:
                item_type = str(getattr(item, "type", "")).lower()
                if item_type in {"reasoning", "thinking", "thought", "reasoning_content"}:
                    append_text(item)

    return "\n".join(part for part in reasoning_parts if part).strip()


def extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    final_json_marker_index = stripped.rfind(FINAL_JSON_MARKER)
    if final_json_marker_index != -1:
        candidate = _extract_balanced_json_object(
            stripped,
            start_index=final_json_marker_index + len(FINAL_JSON_MARKER),
        )
        if candidate is not None:
            return _load_json_or_raise(candidate, raw_text)

    if stripped.startswith("```"):
        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("{"):
                balanced_candidate = _extract_balanced_json_object(candidate)
                if balanced_candidate is not None:
                    return _load_json_or_raise(balanced_candidate, raw_text)
            if "\n" in candidate:
                maybe_json = candidate.split("\n", 1)[1].strip()
                if maybe_json.startswith("{"):
                    balanced_candidate = _extract_balanced_json_object(maybe_json)
                    if balanced_candidate is not None:
                        return _load_json_or_raise(balanced_candidate, raw_text)

    if stripped.startswith("{"):
        candidate = _extract_balanced_json_object(stripped)
        if candidate is not None:
            return _load_json_or_raise(candidate, raw_text)

    candidate = _extract_balanced_json_object(stripped)
    if candidate is not None:
        return _load_json_or_raise(candidate, raw_text)

    raise ModelOutputParseError(
        "Model output does not contain a valid JSON object.",
        raw_text=raw_text,
        error_kind="json_parse",
    )


def split_reasoning_and_final_output(raw_text: str) -> tuple[str, str]:
    stripped = raw_text.strip()
    final_json_marker_index = stripped.rfind(FINAL_JSON_MARKER)
    if final_json_marker_index == -1:
        return "", stripped

    reasoning_text = stripped[:final_json_marker_index].strip()
    final_content = stripped[final_json_marker_index:].strip()
    return reasoning_text, final_content


def _coerce_int(name: str, value: Any, raw_text: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ModelOutputParseError(f"{name} must be an integer.", raw_text=raw_text) from exc


def parse_model_answer(
    raw_text: str,
    *,
    segment_count: int,
    angle_min: int,
    angle_max: int,
    angle_step: int,
    allow_missing_joints: bool = False,
    missing_joint_default_angle: int = 0,
) -> ParsedAnswer:
    payload = extract_json_object(raw_text)

    if set(payload.keys()) != {"actions"}:
        raise ModelOutputParseError("Top-level JSON must contain exactly one key: actions.", raw_text=raw_text)

    raw_actions = payload.get("actions")
    if not isinstance(raw_actions, list):
        raise ModelOutputParseError("actions must be a list.", raw_text=raw_text)

    if allow_missing_joints:
        if len(raw_actions) > segment_count:
            raise ModelOutputParseError("actions length cannot exceed segment_count.", raw_text=raw_text)
    elif len(raw_actions) != segment_count:
        raise ModelOutputParseError("actions length must match segment_count.", raw_text=raw_text)

    normalized: list[dict[str, int]] = []
    seen_joints: set[int] = set()

    for item in raw_actions:
        if not isinstance(item, dict):
            raise ModelOutputParseError("Each action must be an object.", raw_text=raw_text)

        joint = _coerce_int("joint", item.get("joint"), raw_text)
        angle = _coerce_int("angle", item.get("angle"), raw_text)

        if joint < 1 or joint > segment_count:
            raise ModelOutputParseError(f"joint {joint} is outside 1..{segment_count}.", raw_text=raw_text)
        if joint in seen_joints:
            raise ModelOutputParseError(f"joint {joint} appears more than once.", raw_text=raw_text)
        if angle < angle_min or angle > angle_max:
            raise ModelOutputParseError(f"joint {joint} angle is outside the allowed range.", raw_text=raw_text)
        if (angle - angle_min) % angle_step != 0:
            raise ModelOutputParseError(f"joint {joint} angle does not match the allowed step.", raw_text=raw_text)

        seen_joints.add(joint)
        normalized.append({"joint": joint, "angle": angle})

    normalized.sort(key=lambda item: item["joint"])

    expected_joints = set(range(1, segment_count + 1))
    if seen_joints != expected_joints and not allow_missing_joints:
        raise ModelOutputParseError("actions must cover every joint exactly once.", raw_text=raw_text)

    if allow_missing_joints:
        default_angle = int(missing_joint_default_angle)
        if default_angle < angle_min or default_angle > angle_max:
            raise ModelOutputParseError("missing joint default angle is outside the allowed range.", raw_text=raw_text)
        if (default_angle - angle_min) % angle_step != 0:
            raise ModelOutputParseError("missing joint default angle does not match the allowed step.", raw_text=raw_text)

        for joint in sorted(expected_joints - seen_joints):
            normalized.append({"joint": joint, "angle": default_angle})
        normalized.sort(key=lambda item: item["joint"])

    return ParsedAnswer(
        actions=normalized,
        angles=[item["angle"] for item in normalized],
        raw_text=raw_text,
    )


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()
