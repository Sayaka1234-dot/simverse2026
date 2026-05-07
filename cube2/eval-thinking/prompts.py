"""Cube2 (cube goal-roll, top face) prompt builder. Implements the canonical
9-section user prompt and 5-section system prompt defined in docs/PROMPT_SKELETON.md.

Exposes:
    build_system_prompt() -> str
    build_user_prompt(task: GoalRollTask) -> str
    build_messages(task: GoalRollTask, *, project_root: Path) -> list[dict]
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from eval_common import (
    DEFAULT_MAX_DIRECTION_STEPS,
    GoalRollTask,
    NetCell,
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
        "You are a cube-rolling sequence solver. Given a cube whose initial outer-surface "
        "configuration is shown as a cross net and a target top-face image, output one "
        "valid sequence of N/S/E/W rolls so that the cube's top face after the sequence "
        "matches the target.\n"
        "\n"
        # [2] INPUT
        "You will receive: (a) one initial cross-net image showing the visible faces of "
        "the unfolded cube with their patternIds and rotations, (b) one target top-face "
        "image showing the desired final top-face pattern and orientation, and (c) a "
        "structured text body listing every visible net cell, the target patternId+rotation, "
        "the direction vocabulary, and the maximum allowed sequence length.\n"
        "\n"
        # [3] REASONING
        "You may reason step by step before the final answer. Place your final answer on "
        "the very last line of your reply, in the form: FINAL_JSON: <one-line JSON>\n"
        "\n"
        # [4] OUTPUT
        "The JSON object must follow the directions schema described in section 8 of the "
        "user prompt. Multiple sequences may be valid — output any one that solves the "
        "puzzle. Do NOT wrap FINAL_JSON in Markdown code fences. Do NOT write anything "
        "after the FINAL_JSON line. Emit exactly one FINAL_JSON line.\n"
        "\n"
        # [5] FAILSAFE
        "If you cannot reason out a confident sequence, still output your best-effort "
        "FINAL_JSON line with at least one direction token; the only structurally invalid "
        "output is no FINAL_JSON line at all. Never refuse, never return prose only."
    )


# ---------- user prompt (9 sections) ----------

def _format_net_layout(task: GoalRollTask) -> str:
    cells_by_key = {cell.faceKey: cell for cell in task.net_cells}

    def cell_text(cell: NetCell | None) -> str:
        if cell is None:
            return "[empty]"
        return f"[{cell.faceKey}: patternId={cell.patternId}, rotation={cell.rotation}]"

    rows = [
        f"  {cell_text(cells_by_key.get('BACK'))}",
        f"{cell_text(cells_by_key.get('LEFT'))} {cell_text(cells_by_key.get('TOP'))} {cell_text(cells_by_key.get('RIGHT'))}",
        f"  {cell_text(cells_by_key.get('FRONT'))}",
        f"  {cell_text(cells_by_key.get('BOTTOM'))}",
    ]
    return "\n".join(rows)


def _format_net_cells_list(task: GoalRollTask) -> str:
    ordered = sorted(task.net_cells, key=lambda item: (item.row, item.col, item.faceKey))
    return "\n".join(
        f"- {cell.faceKey}: patternId={cell.patternId}, rotation={cell.rotation}"
        for cell in ordered
    )


def build_user_prompt(task: GoalRollTask) -> str:
    _, cached_user = _read_cached_prompt(task)
    if cached_user:
        return cached_user
    return _construct_user_prompt(task)


def _construct_user_prompt(task: GoalRollTask) -> str:
    target = task.target_top_face
    metadata = task.metadata or {}

    return f"""## 1. TASK
Output one sequence of rolls so that, at the end of the sequence, the cube's top face seen from above matches the target top face exactly (both patternId and rotation).
The puzzle is solved when the engine simulates your sequence on the initial cube and the resulting top-face pattern equals the target.

## 2. WORLD MODEL
- Cube: a unit cube with one pattern printed on each of its six outer faces. The faces are named TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT in the world frame.
- Cross net: the unfolded outer surface laid flat. Each cell is one face; its label tells you which face it is and its number under the patternId is the clockwise rotation in degrees from the original upright pattern.
- Roll: tipping the cube 90° about one of its bottom edges into an adjacent grid cell. After a roll, the face that was on the side becomes the new top, the previous top moves to the opposite side, and so on.
- Direction tokens: N (roll up / north), S (roll down / south), E (roll right / east), W (roll left / west). The direction is always relative to the world frame, not the cube's current orientation.
- Target top face: the desired patternId and rotation of whichever face ends up on top after the sequence.

## 3. VISUAL LEGEND
- Image 1: initial cross-net of the cube. The TOP/BOTTOM/FRONT/BACK/LEFT/RIGHT cells are arranged in a cross. Each visible face shows its patternId and a number indicating the clockwise rotation in degrees from the upright orientation.
- Image 2: the target top-face image, showing the patternId and rotation the cube's top face must reach.
- Coordinates: the cube starts at (0, 0). N decrements y (up on screen), S increments y, E increments x (right), W decrements x.

## 4. INPUT FIELDS
- sample_id: {task.sample_id}
- task_type: roll_to_target_top_face
- difficulty: {metadata.get('difficulty', 'unspecified')}
- target_top_face: patternId={target.patternId}, rotation={target.rotation}
- max_direction_steps: {DEFAULT_MAX_DIRECTION_STEPS}
- initial_net_layout (text view, with the BACK / LEFT-TOP-RIGHT / FRONT / BOTTOM rows of the cross):
{_format_net_layout(task)}
- initial_net_cells (explicit list of every visible face):
{_format_net_cells_list(task)}

## 5. ACTION VOCABULARY
A complete answer is one ordered list of direction tokens:
- direction: one of {{"N", "S", "E", "W"}}.
- Sequence length is the number of rolls. The maximum allowed length for this task is `max_direction_steps`.
- Multiple sequences may produce the same target top face; any one of them counts as correct.

## 6. CONSTRAINTS
- Each direction token must be exactly one of N, S, E, W (uppercase).
- The sequence length must be between 1 and `max_direction_steps` inclusive.
- The sequence must be deterministic: no probabilistic or "either-or" entries. One direction per step.
- The engine evaluates by simulating your sequence on the initial cube; do not output any other JSON keys.

## 7. SOLVING ADVICE
- Track which face is currently on top after each roll. A roll N moves the FRONT face to the new TOP, S moves BACK to TOP, E moves LEFT to TOP, W moves RIGHT to TOP (with appropriate rotation).
- Confirm the rotation of the target top face — getting the patternId right but the rotation wrong is still a fail. Each roll N or S adjusts the cube's local-frame rotation by 0/180; each roll E or W adjusts it by ±90.
- A reference sequence may be inferable from the imprint history if the data includes one, but you do not need to copy it; output any valid sequence.

## 8. OUTPUT SCHEMA
FINAL_JSON: {{"directions":["<N|S|E|W>", ...]}}
- directions: array of direction tokens.
- Each token: one of `"N"`, `"S"`, `"E"`, `"W"`.
- Length: 1..{DEFAULT_MAX_DIRECTION_STEPS}.

## 9. FINAL INSTRUCTION
You may include reasoning above, but the very last line of your reply must start with FINAL_JSON: followed by exactly one valid JSON object.
Do not wrap FINAL_JSON in code fences and do not write anything after it."""


# ---------- multimodal message assembly ----------

def _encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{_encode_image(image_path)}"


def _resolve_image(project_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    # imagePaths in the dataset are relative to data2/ (e.g. "../images/C001/initial_net.png")
    return (project_root / "data2" / path).resolve()


def build_messages(task: GoalRollTask, *, project_root: Path) -> list[dict[str, Any]]:
    user_text = build_user_prompt(task)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    initial_path = _resolve_image(project_root, task.image_paths.initialNetImage)
    target_path = _resolve_image(project_root, task.image_paths.targetTopFaceImage)

    for label, image_path in [
        ("Image 1: initial cross net of the cube (visible faces with patternIds and rotations).", initial_path),
        ("Image 2: target top face — the desired patternId and rotation of the cube's top face after the sequence.", target_path),
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
