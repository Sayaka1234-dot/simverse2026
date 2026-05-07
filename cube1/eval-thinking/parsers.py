"""Parse a cube1 model reply into the locked `FINAL_JSON: {"faces": {...}}` schema.

Per docs/EVAL_CONTRACT.md §3, every task implements:
    extract_final_json(raw_text) -> (final_json_text, parsed_dict)

This module also adds cube1-specific structural validation (six required face keys,
rotation in {0,90,180,270}, patternId restricted to the allowed set or the "?" sentinel).
"""
from __future__ import annotations

import json
from typing import Any

from eval_common import (
    ANSWER_FACE_ORDER,
    FaceAnswer,
    ModelAnswer,
    ModelOutputParseError,
    PuzzleTask,
    collect_allowed_pattern_ids_for_prompt,
)


FINAL_JSON_MARKER = "FINAL_JSON:"
VALID_ROTATIONS = {0, 90, 180, 270}


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

    # Fallback: bare or fenced JSON object
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


# ---------- cube1-specific structural validation ----------

def parse_cube1_answer(raw_text: str, task: PuzzleTask) -> ModelAnswer:
    """Extract FINAL_JSON, then enforce the v1 faces schema.

    Accepts both the new envelope `{"faces": {...}}` and the legacy bare face map
    `{"TOP": {...}, ...}` so model outputs from older runs still parse.
    """
    _, payload = extract_final_json(raw_text)
    if not isinstance(payload, dict):
        raise ModelOutputParseError("Top-level JSON must be an object.", raw_text=raw_text)

    if "faces" in payload and isinstance(payload["faces"], dict):
        faces = payload["faces"]
    elif all(face_key in payload for face_key in ANSWER_FACE_ORDER):
        faces = payload
    else:
        raise ModelOutputParseError(
            "Top-level JSON must contain a `faces` object (or the six face keys).",
            raw_text=raw_text,
        )

    allowed = set(collect_allowed_pattern_ids_for_prompt(task))
    answer: dict[str, FaceAnswer] = {}
    for face_key in ANSWER_FACE_ORDER:
        if face_key not in faces:
            raise ModelOutputParseError(
                f"Missing answer face: {face_key}.", raw_text=raw_text
            )
        face_payload = faces[face_key]
        if not isinstance(face_payload, dict):
            raise ModelOutputParseError(
                f"Face {face_key} must be an object with patternId and rotation.",
                raw_text=raw_text,
            )
        try:
            pattern_id = str(face_payload["patternId"])
            rotation = int(face_payload["rotation"]) % 360
        except (KeyError, ValueError, TypeError) as exc:
            raise ModelOutputParseError(
                f"Face {face_key} payload is malformed: {exc}", raw_text=raw_text
            ) from exc
        if rotation not in VALID_ROTATIONS:
            raise ModelOutputParseError(
                f"Face {face_key} rotation {rotation} is not in {sorted(VALID_ROTATIONS)}.",
                raw_text=raw_text,
            )
        if pattern_id not in allowed and pattern_id != "?":
            raise ModelOutputParseError(
                f"Face {face_key} patternId {pattern_id!r} is not in the allowed list.",
                raw_text=raw_text,
            )
        if pattern_id == "?" and rotation != 0:
            # Sentinel pair rule: when "?" the rotation is forced to 0.
            rotation = 0
        answer[face_key] = FaceAnswer(patternId=pattern_id, rotation=rotation)

    return ModelAnswer(sample_id=task.sample_id, answer=answer, raw_text=raw_text)
