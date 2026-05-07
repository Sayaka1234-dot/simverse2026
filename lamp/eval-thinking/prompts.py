"""Lamp prompt builder. Implements the canonical 9-section user prompt and 5-section
system prompt defined in docs/PROMPT_SKELETON.md.

Exposes:
    build_system_prompt(task=None) -> str
    build_user_prompt(task) -> str
    build_messages(task, *, project_root) -> list[dict]

If the task's underlying JSON carries a `prompt: {"system": "...", "user": "..."}`
field (added by populate_prompts.py — done so HF dataset downloads are fully
self-contained), the cached strings are returned. Otherwise the prompt is
constructed from scratch on each call.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from eval_common.schemas import LampTask


def _read_cached_prompt(task: Any) -> tuple[str | None, str | None]:
    """Return (system, user) text from `task.prompt` if present, else (None, None)."""
    raw: Any = None
    if isinstance(task, dict):
        raw = task
    else:
        for attr in ("payload", "raw_payload", "_raw"):
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
        "You are a mechanical-arm lamp targeting solver. Given a multi-segment robotic "
        "arm anchored at a fixed base, choose one absolute angle for every joint so that "
        "the bulb at the arm's tip illuminates the target point.\n"
        "\n"
        # [2] INPUT
        "You will receive: (a) one rendered image of the workspace showing the arm base, "
        "joints, segments, target, and any striped wall obstacles, and (b) a structured "
        "text body containing every numeric parameter (segment count, segment lengths, "
        "target coordinates, allowed angle range, allowed angle step, light radius, "
        "obstacle rectangles).\n"
        "\n"
        # [3] REASONING
        "You may reason step by step before the final answer. Place your final answer on "
        "the very last line of your reply, in the form: FINAL_JSON: <one-line JSON>\n"
        "\n"
        # [4] OUTPUT
        "The JSON object must follow the actions schema described in section 8 of the user "
        "prompt. Do NOT wrap FINAL_JSON in Markdown code fences. Do NOT write anything "
        "after the FINAL_JSON line. Emit exactly one FINAL_JSON line.\n"
        "\n"
        # [5] FAILSAFE
        "If the information is insufficient to choose a confident value for some joint, "
        "still output a complete FINAL_JSON line covering every joint (use the closest "
        "allowed angle from the allowed range). Never refuse, never return prose only."
    )


# ---------- user prompt (9 sections) ----------

def _format_obstacles(task: LampTask) -> str:
    obstacles = task.obstacles
    if not obstacles:
        return "(none for this task)"
    lines: list[str] = []
    for obstacle in obstacles:
        obstacle_id = obstacle.get("id", "wall")
        obstacle_type = obstacle.get("type", "wall")
        pattern = obstacle.get("pattern", "warning_stripes")
        parts = obstacle.get("parts", [])
        lines.append(f"- {obstacle_id}: type={obstacle_type}, pattern={pattern}")
        for index, part in enumerate(parts, start=1):
            lines.append(
                "  "
                f"part {index}: x={part.get('x')}, y={part.get('y')}, "
                f"width={part.get('width')}, height={part.get('height')}"
            )
    return "\n".join(lines)


def _format_segments(task: LampTask) -> str:
    segments = task.arm.get("segments", [])
    if not segments:
        return "(no segments)"
    return "\n".join(
        f"- joint {index}: length={int(segment.get('length', 0))}"
        for index, segment in enumerate(segments, start=1)
    )


def build_user_prompt(task: LampTask) -> str:
    _, cached_user = _read_cached_prompt(task)
    if cached_user:
        return cached_user
    return _construct_user_prompt(task)


def _construct_user_prompt(task: LampTask) -> str:
    target = task.target
    arm_base = task.arm_base
    constraints = task.angle_constraints
    segments_text = _format_segments(task)
    obstacles_text = _format_obstacles(task)

    return f"""## 1. TASK
Choose one absolute angle for every joint of a fixed-base mechanical arm so that the bulb at the tip illuminates the target point.
The level is solved when the bulb's light radius covers the target AND no rod segment intersects any obstacle.

## 2. WORLD MODEL
- Arm base: the fixed mounting point of the arm. It does NOT move regardless of joint choices.
- Joint: a pivot point connecting consecutive arm segments. There is one joint per segment, indexed 1..segment_count.
- Segment / rod: a rigid white bar of fixed length attached to its joint.
- Bulb: the light source rigidly attached to the tip of the last segment. Its position is the cumulative endpoint after applying all joint angles to the segments.
- Light radius: the radius around the bulb within which the target counts as illuminated.
- Target: the single point the bulb must illuminate.
- Obstacle: an axis-aligned rectangle (or set of rectangles) the rods must NOT intersect.

## 3. VISUAL LEGEND
- Orange diamond: arm base (fixed).
- White lines: arm segments (rods).
- Blue small circles: joints.
- Yellow circle: lamp bulb.
- Pale yellow translucent disc: the lamp's light coverage radius.
- Orange circle: target point.
- Amber rectangles with diagonal stripes: obstacles. Rods may not intersect them.
- Coordinate system: origin (0,0) marked on the grid; x increases to the right, y increases upward.

## 4. INPUT FIELDS
- sample_id: {task.sample_id}
- segment_count: {task.segment_count}
- arm_base: ({arm_base['x']}, {arm_base['y']})
- target: ({target['x']}, {target['y']})
- light_radius: {task.light_radius}
- angle_min: {constraints['min']}
- angle_max: {constraints['max']}
- angle_step: {constraints['step']}
- segments:
{segments_text}
- obstacles:
{obstacles_text}

## 5. ACTION VOCABULARY
A complete answer is one list of `action` objects, exactly one per joint:
- action: {{"joint": <int 1..segment_count>, "angle": <int degrees>}}
- `joint` is 1-indexed and identifies which segment this angle controls.
- `angle` is the absolute angle of that segment measured counterclockwise from the positive x-axis. Positive values rotate counterclockwise; negative values rotate clockwise.

## 6. CONSTRAINTS
- The actions list must contain exactly `segment_count` items, one per joint, with no duplicates.
- Each `angle` is an integer in `[angle_min, angle_max]` that is also a multiple of `angle_step` offset from `angle_min`.
- Angles are NOT cumulative across joints — each joint's angle is independent of the previous joint.
- The first segment starts at the arm base. Each subsequent segment starts where the previous one ends.
- No rod segment may intersect any obstacle rectangle.
- The level is solved iff the final bulb position is within `light_radius` of the target AND no rod intersects any obstacle.

## 7. SOLVING ADVICE
- Identify a coarse joint configuration that points the tip toward the target, then refine each angle independently.
- When obstacles are present, prefer paths that route the rod chain around them; an angle that produces a visually shorter path is not always feasible.
- The light radius can be tight (often 20–30 units), so even a 5° error on a single joint can miss the target.

## 8. OUTPUT SCHEMA
FINAL_JSON: {{"actions":[{{"joint":1,"angle":<int>}},{{"joint":2,"angle":<int>}}, ...]}}
- actions: list of length `segment_count`, joints `1..segment_count` each appearing exactly once.
- joint: integer in `1..segment_count`.
- angle: integer in `[angle_min, angle_max]`, multiple of `angle_step`.

## 9. FINAL INSTRUCTION
You may include reasoning above, but the very last line of your reply must start with FINAL_JSON: followed by exactly one valid JSON object.
Do not wrap FINAL_JSON in code fences and do not write anything after it."""


# ---------- multimodal message assembly ----------

def _encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{_encode_image(image_path)}"


def build_messages(task: LampTask, *, project_root: Path) -> list[dict[str, Any]]:
    user_text = build_user_prompt(task)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    image_path = (project_root / task.image_path).resolve()
    if image_path.exists():
        user_content.append({
            "type": "text",
            "text": "Image: rendered workspace for this level (arm base, segments, joints, target, obstacles).",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_path)},
        })
    else:
        user_content.append({
            "type": "text",
            "text": f"(Image not found at {image_path.as_posix()}; proceed with text fields only.)",
        })

    return [
        {"role": "system", "content": build_system_prompt(task)},
        {"role": "user", "content": user_content},
    ]
