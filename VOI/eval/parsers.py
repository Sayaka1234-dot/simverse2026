"""Parse a VOI model reply into the locked `FINAL_JSON: {"placements": [...]}` schema.

Per docs/EVAL_CONTRACT.md §3, every task implements:
    extract_final_json(raw_text) -> (final_json_text, parsed_dict)

This module also adds VOI-specific structural validation and a placements ⇒ DSL
helper that lets us feed the legacy pixel engine without changing its parser.
"""
from __future__ import annotations

import json
from typing import Any


FINAL_JSON_MARKER = "FINAL_JSON:"
VALID_ANGLES = {0, 90, 180, 270}


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


# ---------- VOI-specific structural validation ----------

def parse_voi_answer(raw_text: str, level_data: dict[str, Any]) -> dict[str, Any]:
    """Extract FINAL_JSON, then enforce the placements schema.

    Returns the parsed `{"placements": [...]}` dict on success.
    Raises ModelOutputParseError on structural failure.
    """
    _, payload = extract_final_json(raw_text)
    if not isinstance(payload, dict):
        raise ModelOutputParseError(
            "Top-level JSON must be an object.", raw_text=raw_text, error_kind="validation"
        )
    if set(payload.keys()) != {"placements"}:
        raise ModelOutputParseError(
            "Top-level JSON must contain exactly one key: placements.",
            raw_text=raw_text,
            error_kind="validation",
        )
    placements = payload["placements"]
    if not isinstance(placements, list) or not placements:
        raise ModelOutputParseError(
            "placements must be a non-empty list.",
            raw_text=raw_text,
            error_kind="validation",
        )

    inventory = level_data.get("inventory", {})
    used_shapes: set[str] = set()
    for index, item in enumerate(placements, start=1):
        if not isinstance(item, dict):
            raise ModelOutputParseError(
                f"Placement {index} must be an object.",
                raw_text=raw_text,
                error_kind="validation",
            )
        try:
            shape = str(item["shape"])
            angle = int(item["angle"])
            vertex = str(item["vertex"])
            grid = item["grid"]
        except (KeyError, ValueError, TypeError) as exc:
            raise ModelOutputParseError(
                f"Placement {index} payload is malformed: {exc}",
                raw_text=raw_text,
                error_kind="validation",
            ) from exc

        if shape not in inventory:
            raise ModelOutputParseError(
                f"Placement {index} references unknown shape {shape!r}.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if shape in used_shapes:
            raise ModelOutputParseError(
                f"Shape {shape} is reused; each shape may be used at most once.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if angle not in VALID_ANGLES:
            raise ModelOutputParseError(
                f"Placement {index} angle {angle} is not in {sorted(VALID_ANGLES)}.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if vertex not in inventory[shape]:
            raise ModelOutputParseError(
                f"Placement {index} vertex {vertex!r} is not a vertex of {shape}.",
                raw_text=raw_text,
                error_kind="validation",
            )
        if not (isinstance(grid, list) and len(grid) == 2):
            raise ModelOutputParseError(
                f"Placement {index} grid must be a [x, y] pair.",
                raw_text=raw_text,
                error_kind="validation",
            )
        try:
            int(grid[0])
            int(grid[1])
        except (ValueError, TypeError) as exc:
            raise ModelOutputParseError(
                f"Placement {index} grid coordinates must be integers.",
                raw_text=raw_text,
                error_kind="validation",
            ) from exc
        used_shapes.add(shape)

    return payload


# ---------- placements <-> DSL helpers (engine-side compatibility) ----------

def placements_to_dsl(placements: list[dict[str, Any]]) -> str:
    """Convert a placements list to the legacy text DSL the pixel engine accepts."""
    return "\n".join(
        f"{p['shape']} {int(p['angle'])} {p['vertex']} [{int(p['grid'][0])},{int(p['grid'][1])}]"
        for p in placements
    )
