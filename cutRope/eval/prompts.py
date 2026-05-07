"""cutRope (Cut the Rope video → command script) prompt builder. Implements the
canonical 9-section user prompt and 5-section system prompt defined in
docs/PROMPT_SKELETON.md.

Exposes:
    build_system_prompt() -> str
    build_user_prompt(eval_item: dict) -> str
    build_messages(item_path, eval_item, *, retry_note=None, video_source="mp4",
                   video_part_type="video_url", video_detail=None,
                   video_max_frames=None, video_fps=None,
                   video_frame_width=960, video_frame_quality=0.85) -> list[dict]
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Reuse the existing video helpers (frame extraction, data URL packaging, etc.)
from eval_common import (
    SUPPORTED_OBJECT_LABELS,
    file_to_data_url,
    ensure_video_frame_paths,
    resolve_project_path,
    select_video_info,
)


def _read_cached_prompt(eval_item: Any) -> tuple[str | None, str | None]:
    """Return (system, user) from `eval_item.prompt` if present, else (None, None)."""
    if not isinstance(eval_item, dict):
        return None, None
    prompt = eval_item.get("prompt")
    if not isinstance(prompt, dict):
        return None, None
    sys_text = prompt.get("system") if isinstance(prompt.get("system"), str) else None
    user_text = prompt.get("user") if isinstance(prompt.get("user"), str) else None
    return sys_text, user_text


# ---------- system prompt (5 sections) ----------

def build_system_prompt(eval_item: Any = None) -> str:
    if eval_item is not None:
        cached_sys, _ = _read_cached_prompt(eval_item)
        if cached_sys:
            return cached_sys
    return _construct_system_prompt()


def _construct_system_prompt() -> str:
    return (
        # [1] ROLE
        "You are a Cut the Rope replayable-script solver. Given a short gameplay "
        "video of one Cut the Rope level (with a coordinate grid overlay) and a "
        "structured description of the level objects, you produce a deterministic "
        "command script that, replayed from the same initial state, wins the level.\n"
        "\n"
        # [2] INPUT
        "You will receive: (a) one short gameplay video of the level, (b) a "
        "structured text body listing the canvas size, the count of each gameplay "
        "object (candy, target, ropes, bubbles, pumps, gravity switches, stars), "
        "and the level metadata.\n"
        "\n"
        # [3] REASONING
        "You may reason step by step before the final answer. Place your final "
        "answer on the very last line of your reply, in the form: "
        "FINAL_JSON: <one-line JSON>\n"
        "\n"
        # [4] OUTPUT
        "The JSON object must follow the commands schema described in section 8 of "
        "the user prompt: keys `commands`, `reason`, `confidence`. Multiple winning "
        "scripts may be valid; output any one. Do NOT wrap FINAL_JSON in Markdown "
        "code fences. Do NOT write anything after the FINAL_JSON line. Emit exactly "
        "one FINAL_JSON line.\n"
        "\n"
        # [5] FAILSAFE
        "If you cannot reason out a confident solution, still emit a best-effort "
        "FINAL_JSON line with at least one command and a confidence value below 1.0. "
        "Never refuse, never return prose only."
    )


# ---------- user prompt (9 sections) ----------

def _format_object_counts(counts: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, label in SUPPORTED_OBJECT_LABELS.items():
        value = counts.get(key)
        if isinstance(value, int) and value > 0:
            parts.append(f"  - {label}: {value}")
    return "\n".join(parts) if parts else "  (no key gameplay objects of the supported set were detected)"


def _format_object_function_lines(counts: dict[str, Any], two_parts: bool) -> str:
    lines: list[str] = [
        "- Target (monster): the level is won when the candy reaches the monster's mouth. The target is usually fixed in place.",
    ]
    has_split_candy = two_parts or bool(counts.get("left_candy")) or bool(counts.get("right_candy"))
    if has_split_candy:
        lines.append(
            "- Split candy: the level starts with left_candy and right_candy halves. Before they merge, use left_candy_* and right_candy_* conditions. After they touch and merge, use candy_* for the complete candy."
        )
    else:
        lines.append(
            "- Candy: the candy is affected by gravity, ropes, bubbles, pumps, and other active objects. It must be delivered to the target."
        )
    if counts.get("grab_or_rope_anchor"):
        lines.append(
            "- Ropes / grabs: ropes constrain the candy or split-candy movement. `cut_rope N` cuts rope N; `cut_rope N,M,K` cuts multiple at once. If a grab can move, `move_grab N X` or `move_grab N X Y` repositions it."
        )
    if counts.get("star"):
        lines.append(
            "- Stars: candy or split-candy collects a star by passing through it. Prefer paths that collect 3 stars, but stable completion takes priority."
        )
    if counts.get("bubble"):
        lines.append(
            "- Bubbles: candy entering a bubble usually floats upward. `pop_bubble N` pops bubble N. In split-candy levels, `pop_bubble_left` / `pop_bubble_right` pop the bubble holding the corresponding half."
        )
    if counts.get("pump"):
        lines.append(
            "- Pumps: activating a pump pushes nearby objects. `activate_pump N`, optionally with `times`/`every`/`until` modifiers for repeated activation."
        )
    if counts.get("gravity_button"):
        lines.append(
            "- Gravity switch: `toggle_gravity` reverses or rotates gravity. Often triggered after the candy crosses a coordinate threshold."
        )
    return "\n".join(lines)


def build_user_prompt(eval_item: dict[str, Any]) -> str:
    _, cached_user = _read_cached_prompt(eval_item)
    if cached_user:
        return cached_user
    return _construct_user_prompt(eval_item)


def _construct_user_prompt(eval_item: dict[str, Any]) -> str:
    level = eval_item.get("prompt_level", {}) if isinstance(eval_item.get("prompt_level"), dict) else {}
    counts = level.get("object_counts", {}) if isinstance(level.get("object_counts"), dict) else {}
    two_parts = bool(level.get("two_parts"))
    canvas_w = level.get("canvas_width", 1920)
    canvas_h = level.get("canvas_height", 1080)
    object_counts_text = _format_object_counts(counts)
    object_function_text = _format_object_function_lines(counts, two_parts)
    level_id = eval_item.get("level_id", "(unknown)")

    return f"""## 1. TASK
Produce a replayable command script that wins the Cut the Rope level shown in the gameplay video. The script must be deterministic so that replaying it from the same initial state in the simulator produces a win.
The level is solved when the candy reaches the target monster's mouth. Three-star completion is preferred but stable winning is the first priority.

## 2. WORLD MODEL
- Candy: a physics object affected by gravity, ropes, bubbles, pumps, and other active objects. Must be delivered to the target.
- Target / monster: the level is won when the candy enters the target's mouth.
- Rope: a constraint between the candy (or a split-candy half) and an anchor. Cutting a rope releases the candy from that constraint. Ropes are zero-indexed.
- Grab: an anchor for a rope that can be repositioned during play. Zero-indexed.
- Bubble: when the candy enters a bubble, it usually floats upward. Pop the bubble to release the candy.
- Pump: a gust source that pushes objects. Each activation produces one impulse.
- Gravity switch: toggles gravity direction or magnitude.
- Star: collected by candy passing through its position. Up to 3 stars per level.
- Split candy: some levels start with two candy halves (`left_candy`, `right_candy`). Use the half-specific conditions before the halves merge; switch to `candy_*` conditions after they merge.

## 3. VISUAL LEGEND
- The video is a short clip showing the full level layout and a coordinate grid overlay.
- Coordinates: origin at the top-left corner. x increases to the right; y increases downward.
- Indices in the video are zero-based for ropes, bubbles, pumps, and grabs. Infer indices from object positions and the order they appear in the clip.

## 4. INPUT FIELDS
- level_id: {level_id}
- canvas_size: {canvas_w} x {canvas_h}
- two_parts (split candy): {two_parts}
- object_counts:
{object_counts_text}
- gameplay objects in this level:
{object_function_text}

## 5. ACTION VOCABULARY
A complete answer is one ordered command script (one command per line). Available actions:
- `cut_rope N`               — cut rope N
- `cut_rope N,M,K`           — cut several ropes simultaneously
- `pop_bubble N`             — pop bubble N
- `pop_bubble_left`          — pop the bubble holding the left split-candy half
- `pop_bubble_right`         — pop the bubble holding the right split-candy half
- `activate_pump N`          — fire pump N once
- `activate_pump N times C`  — fire C times back-to-back
- `activate_pump N times C every S` — fire C times spaced S seconds apart
- `activate_pump N every S until <CONDITION>` — fire repeatedly until CONDITION holds
- `move_grab N X`            — move grab N to x-coordinate X (y unchanged)
- `move_grab N X Y`          — move grab N to (X, Y)
- `kick_rope N`              — apply a one-shot impulse to rope N
- `toggle_gravity`           — toggle the gravity setting

Each command may be guarded by an optional `when <CONDITION>` clause. Available condition primitives:
- `candy_x > N`, `candy_x < N`, `candy_y > N`, `candy_y < N`
- `candy_near X,Y,R` — candy is within radius R of (X,Y); optional `for S` requires the predicate to hold for S seconds
- `candy_still for S` — candy speed is below threshold for S seconds (useful before cutting after a swing settles)
- `left_candy_*` and `right_candy_*` mirror the candy_* primitives for the corresponding split half
- `grab_x I > N`, `grab_y I < N`, `grab_near I,X,Y,R`
- `rope_cut N` — rope N has been cut
- `no_rope`, `candy_in_bubble`
- Conditions can be combined with `and`, `or`, and parentheses.

## 6. CONSTRAINTS
- One command per line in the `commands` string.
- Indices must be zero-based and consistent with the level video.
- `wait_frames` is NOT allowed in this benchmark version. Use condition-based waits.
- The script must be deterministic; do not output stochastic or "either-or" entries.
- The script must terminate without manual intervention; the simulator runs it from the initial state and decides win/loss.

## 7. SOLVING ADVICE
- Identify which ropes mainly control the candy first; choose a cut order that releases the candy along the shortest stable path to the target.
- When waiting for the candy to reach a place, prefer `candy_near` / `candy_y` / `candy_x` over fixed timing.
- For repeated pumping, use `activate_pump N times C every S` or `activate_pump N every S until CONDITION`.
- In split-candy levels, do NOT use `candy_still` / `candy_near` for the merged candy before the halves merge; use the `left_candy_*` / `right_candy_*` primitives instead.

## 8. OUTPUT SCHEMA
FINAL_JSON: {{"commands":"<command-script with \\n separators>","reason":"<one-sentence intent>","confidence":<0..1>}}
- commands: string. One command per line; lines separated by `\\n`.
- reason: short one-sentence explanation of the intended sequence.
- confidence: float in `[0, 1]`.

## 9. FINAL INSTRUCTION
You may include reasoning above, but the very last line of your reply must start with FINAL_JSON: followed by exactly one valid JSON object.
Do not wrap FINAL_JSON in code fences and do not write anything after it."""


# ---------- multimodal message assembly ----------

def build_messages(
    item_path: Path,
    eval_item: dict[str, Any],
    *,
    retry_note: str | None = None,
    video_source: str = "mp4",
    video_part_type: str = "video_url",
    video_detail: str | None = None,
    video_max_frames: int | None = None,
    video_fps: float | None = None,
    video_frame_width: int = 960,
    video_frame_quality: float = 0.85,
) -> list[dict[str, Any]]:
    user_text = build_user_prompt(eval_item)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    video_info = select_video_info(eval_item, video_source=video_source)
    video_path_text = video_info.get("path")
    if not isinstance(video_path_text, str) or not video_path_text:
        raise ValueError(f"{item_path.name} is missing video.path")
    video_path = resolve_project_path(video_path_text)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    user_content.append({
        "type": "text",
        "text": "Video: the full short gameplay clip for this level. Infer the replayable commands from the level layout and motion.",
    })

    if video_part_type == "image_frames":
        max_frames = video_max_frames or 8
        frame_paths = ensure_video_frame_paths(
            video_path,
            max_frames=max_frames,
            frame_width=video_frame_width,
            quality=video_frame_quality,
        )
        user_content.append({
            "type": "text",
            "text": "The video is delivered below as sampled frame images in chronological order. Infer the same replayable commands from these frames.",
        })
        for index, frame_path in enumerate(frame_paths, start=1):
            user_content.append({
                "type": "text",
                "text": f"Frame {index}/{len(frame_paths)} sampled from the gameplay video.",
            })
            user_content.append({
                "type": "image_url",
                "image_url": {"url": file_to_data_url(frame_path, fallback_mime_type="image/jpeg")},
            })
    else:
        mime_type = str(video_info.get("mime_type") or "video/mp4")
        video_url_payload: dict[str, Any] = {"url": file_to_data_url(video_path, fallback_mime_type=mime_type)}
        if video_detail:
            video_url_payload["detail"] = video_detail
        if video_max_frames is not None:
            video_url_payload["max_frames"] = video_max_frames
        if video_fps is not None:
            video_url_payload["fps"] = int(video_fps) if float(video_fps).is_integer() else video_fps
        if video_part_type == "input_video":
            user_content.append({"type": "input_video", "video_url": video_url_payload})
        else:
            user_content.append({"type": "video_url", "video_url": video_url_payload})

    if retry_note:
        user_content.append({"type": "text", "text": retry_note})

    return [
        {"role": "system", "content": build_system_prompt(eval_item)},
        {"role": "user", "content": user_content},
    ]
