"""Cube1 (cube reconstruction) prompt builder. Implements the canonical 9-section
user prompt and 5-section system prompt defined in docs/PROMPT_SKELETON.md.

Exposes:
    build_system_prompt() -> str
    build_user_prompt(task: PuzzleTask) -> str
    build_messages(task: PuzzleTask, *, project_root: Path) -> list[dict]
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from eval_common import (
    ANSWER_FACE_ORDER,
    PuzzleTask,
    collect_allowed_pattern_ids_for_prompt,
    resolve_repo_path,
)


def _read_cached_prompt(task: Any) -> tuple[str | None, str | None]:
    """Return (system, user) from `task.prompt` if present, else (None, None)."""
    raw: Any = None
    if isinstance(task, dict):
        raw = task
    else:
        for attr in ("raw_payload", "payload", "_raw"):
            candidate = getattr(task, attr, None)
            if isinstance(candidate, dict):
                raw = candidate
                break
    if not isinstance(raw, dict):
        return None, None
    prompt = raw.get("prompt")
    if not isinstance(prompt, dict):
        return None, None
    sys_text = prompt.get("system") if isinstance(prompt.get("system"), str) else None
    user_text = prompt.get("user") if isinstance(prompt.get("user"), str) else None
    return sys_text, user_text


# ---------- system prompt (5 sections) ----------

def build_system_prompt(task: Any = None) -> str:
    if task is not None:
        cached_sys, _ = _read_cached_prompt(task)
        if cached_sys:
            return cached_sys
    return _construct_system_prompt()


def _construct_system_prompt() -> str:
    return (
        # [1] ROLE
        "You are a cube-reconstruction puzzle solver. Given a blank cross net of a cube "
        "and a top-down path image showing the bottom-face imprints stamped onto the road "
        "as the cube rolls, you reconstruct the patternId and rotation of every outer face.\n"
        "\n"
        # [2] INPUT
        "You will receive: (a) one blank cross-net image (the unfolded outer surface, with "
        "the six face slots TOP/BOTTOM/FRONT/BACK/LEFT/RIGHT), (b) one path-sequence image "
        "(top-down view of the cube's roll path with the bottom-face imprints visible), and "
        "(c) a structured text body listing the roll sequence, observed path faces, and the "
        "allowed patternId values for this task.\n"
        "\n"
        # [3] REASONING
        "You may reason step by step before the final answer. Place your final answer on "
        "the very last line of your reply, in the form: FINAL_JSON: <one-line JSON>\n"
        "\n"
        # [4] OUTPUT
        "The JSON object must follow the faces schema described in section 8 of the user "
        "prompt. Do NOT wrap FINAL_JSON in Markdown code fences. Do NOT write anything "
        "after the FINAL_JSON line. Emit exactly one FINAL_JSON line.\n"
        "\n"
        # [5] FAILSAFE
        "If a face cannot be uniquely determined from the inputs, output patternId=\"?\" "
        "and rotation=0 for that face. Always emit a complete FINAL_JSON line covering "
        "all six face keys; never refuse, never return prose only."
    )


# ---------- user prompt (9 sections) ----------

def _format_observed_faces(task: PuzzleTask) -> str:
    if not task.observed_path_faces:
        return "(none for this task)"
    lines: list[str] = []
    for index, face in enumerate(task.observed_path_faces, start=1):
        flags: list[str] = []
        if face.flipHorizontal:
            flags.append("flipHorizontal=true")
        if face.flipVertical:
            flags.append("flipVertical=true")
        flag_text = ", ".join(flags) if flags else "no_flip"
        lines.append(
            f"- step {index}: patternId={face.patternId}, rotation={face.rotation}, {flag_text}"
        )
    return "\n".join(lines)


def build_user_prompt(task: PuzzleTask) -> str:
    _, cached_user = _read_cached_prompt(task)
    if cached_user:
        return cached_user
    return _construct_user_prompt(task)


def _construct_user_prompt(task: PuzzleTask) -> str:
    allowed_pattern_ids = ", ".join(collect_allowed_pattern_ids_for_prompt(task))
    roll_sequence = " -> ".join(task.roll_sequence) if task.roll_sequence else "(empty)"
    observed_faces_text = _format_observed_faces(task)
    metadata = task.metadata or {}

    return f"""## 1. TASK
Reconstruct the patternId and absolute rotation of every face of a cube from a roll-trace image.
The puzzle is solved when every output face matches the cube's true outer-surface configuration; faces that cannot be uniquely determined are reported with patternId="?" and rotation=0.

## 2. WORLD MODEL
- Cube: a unit cube with one pattern printed on each of its six outer faces. Faces are named by their orientation in the world frame: TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT.
- Cross net: the unfolded outer surface laid flat in a cross shape. Each cell of the cross is one face of the cube.
- Roll: tipping the cube 90° about one of its bottom edges into an adjacent grid cell.
- Path imprint / bottom-face stamp: as the cube rolls, the face touching the ground stamps that face's pattern (rotated according to the roll) onto the grid cell it lay on. The path-sequence image shows these imprints from a top-down view.
- patternId: the symbolic name of a face's printed pattern (e.g. "smile", "triangle", "5"). The literal string "?" denotes "cannot be uniquely determined".
- rotation: an integer in {{0, 90, 180, 270}} measured clockwise from the pattern's upright orientation when the face is viewed from outside the cube.

## 3. VISUAL LEGEND
- Blank cross net image: shows the six face slots arranged in a cross with TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT labelled.
- Path sequence image: a top-down grid showing the cube's start cell, the roll path, and the bottom-face imprints stamped along the path. Each imprint is the bottom-face pattern at the moment the cube rested on that cell, viewed from above (NOT viewed from underneath looking up).
- Coordinate system: top-down, with grid cell positions used to locate imprints; rotations are expressed in degrees clockwise.

## 4. INPUT FIELDS
- sample_id: {task.sample_id}
- net_layout: {task.net_layout}
- difficulty: {metadata.get('difficulty', 'unspecified')}
- move_count: {metadata.get('move_count', 'unspecified')}
- roll_sequence (N=up, S=down, W=left, E=right): {roll_sequence}
- observed_path_faces (one entry per stamped imprint, in roll order):
{observed_faces_text}
- allowed patternId values for this task: {allowed_pattern_ids}

## 5. ACTION VOCABULARY
A complete answer is one map from face name to its `(patternId, rotation)` pair:
- face: one of {{"TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"}}.
- patternId: a string drawn from the allowed list above, or the literal "?" sentinel.
- rotation: integer in {{0, 90, 180, 270}}.
A face is "uniquely determined" iff the inputs (roll sequence, observed imprints, blank net) constrain its pattern and rotation to exactly one possibility.

## 6. CONSTRAINTS
- The output must list all six face keys exactly: TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT (no extras, no omissions).
- Each `patternId` must come from the allowed list, or be the literal "?".
- When `patternId == "?"`, `rotation` must be 0.
- Each rotation must be one of 0, 90, 180, 270.
- Do not invent new patternIds. The model is scored only against the listed allowed values plus "?".

## 7. SOLVING ADVICE
- Trace the roll one step at a time: which face becomes the bottom after each roll? The path imprint at that step records that face.
- When a stamped imprint is rotated relative to the original pattern's upright orientation, infer the cumulative rotation that the rolling chain has applied to that face.
- Faces that never touch the ground may not appear in the imprints; if no other constraint pins them, they are "?".

## 8. OUTPUT SCHEMA
FINAL_JSON: {{"faces":{{"TOP":{{"patternId":<string>,"rotation":<int>}},"BOTTOM":{{...}},"FRONT":{{...}},"BACK":{{...}},"LEFT":{{...}},"RIGHT":{{...}}}}}}
- faces: object with exactly six keys TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT.
- patternId: string from the allowed list, or "?".
- rotation: integer in {{0, 90, 180, 270}}; 0 when patternId is "?".

## 9. FINAL INSTRUCTION
You may include reasoning above, but the very last line of your reply must start with FINAL_JSON: followed by exactly one valid JSON object.
Do not wrap FINAL_JSON in code fences and do not write anything after it."""


# ---------- multimodal message assembly ----------

def _encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{_encode_image(image_path)}"


def build_messages(task: PuzzleTask, *, project_root: Path | None = None) -> list[dict[str, Any]]:
    blank_net_path = resolve_repo_path(task.image_paths.blank_net_image)
    path_sequence_path = resolve_repo_path(task.image_paths.path_sequence_image)

    user_text = build_user_prompt(task)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    for label, image_path in [
        ("Image 1: blank cross net showing the six face slots.", blank_net_path),
        ("Image 2: top-down path sequence with bottom-face imprints stamped along the roll path.", path_sequence_path),
    ]:
        if image_path.exists():
            user_content.append({"type": "text", "text": label})
            user_content.append({
                "type": "image_url",
                "image_url": {"url": _image_data_url(image_path)},
            })
        else:
            user_content.append({
                "type": "text",
                "text": f"({label} | image file not found at {image_path.as_posix()}; proceed with text fields only.)",
            })

    return [
        {"role": "system", "content": build_system_prompt(task)},
        {"role": "user", "content": user_content},
    ]
