"""VOI (Text-VOI spatial logic puzzle) prompt builder. Implements the canonical
9-section user prompt and 5-section system prompt defined in docs/PROMPT_SKELETON.md.

Exposes:
    build_system_prompt() -> str
    build_user_prompt(level_data: dict) -> str
    build_messages(level_path: Path, level_data: dict) -> list[dict]
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from eval_common import resolve_level_asset_path


def _read_cached_prompt(level_data: Any) -> tuple[str | None, str | None]:
    """Return (system, user) from `level_data.prompt` if present, else (None, None)."""
    if not isinstance(level_data, dict):
        return None, None
    prompt = level_data.get("prompt")
    if not isinstance(prompt, dict):
        return None, None
    sys_text = prompt.get("system") if isinstance(prompt.get("system"), str) else None
    user_text = prompt.get("user") if isinstance(prompt.get("user"), str) else None
    return sys_text, user_text


# ---------- system prompt (5 sections) ----------

def build_system_prompt(level_data: Any = None) -> str:
    if level_data is not None:
        cached_sys, _ = _read_cached_prompt(level_data)
        if cached_sys:
            return cached_sys
    return _construct_system_prompt()


def _construct_system_prompt() -> str:
    return (
        # [1] ROLE
        "You are a Text-VOI spatial logic puzzle solver. Given a target pattern image and "
        "a set of base shapes, choose how to rotate and translate the shapes onto a grid "
        "so that their XOR-overlapping union matches the target pattern exactly.\n"
        "\n"
        # [2] INPUT
        "You will receive: (a) one target pattern image showing the goal silhouette on a "
        "labeled grid, (b) one image per available base shape with vertex labels, and "
        "(c) a structured text body listing each shape's vertex coordinates, the grid "
        "size, the difficulty tier, the required and distractor shape counts, and the "
        "XOR-overlap rule.\n"
        "\n"
        # [3] REASONING
        "You may reason step by step before the final answer. Place your final answer on "
        "the very last line of your reply, in the form: FINAL_JSON: <one-line JSON>\n"
        "\n"
        # [4] OUTPUT
        "The JSON object must follow the placements schema described in section 8 of the "
        "user prompt. Do NOT wrap FINAL_JSON in Markdown code fences. Do NOT write "
        "anything after the FINAL_JSON line. Emit exactly one FINAL_JSON line.\n"
        "\n"
        # [5] FAILSAFE
        "If you cannot reconstruct the target pattern with full confidence, still emit a "
        "best-effort FINAL_JSON line with at least one placement; the only structurally "
        "invalid output is no FINAL_JSON line at all. Never refuse, never return prose only."
    )


# ---------- user prompt (9 sections) ----------

def _format_inventory(level_data: dict[str, Any]) -> str:
    inventory = level_data.get("inventory", {})
    lines: list[str] = []
    for shape_id, vertices in inventory.items():
        vertex_text = ", ".join(
            f"{vertex_id}=[{point[0]},{point[1]}]"
            for vertex_id, point in sorted(vertices.items(), key=lambda item: int(item[0][1:]))
        )
        lines.append(f"- {shape_id}: {vertex_text}")
    return "\n".join(lines) if lines else "(no shapes provided)"


def build_user_prompt(level_data: dict[str, Any]) -> str:
    _, cached_user = _read_cached_prompt(level_data)
    if cached_user:
        return cached_user
    return _construct_user_prompt(level_data)


def _construct_user_prompt(level_data: dict[str, Any]) -> str:
    meta = level_data.get("meta", {})
    overlap_allowed = bool(meta.get("overlapAllowed"))
    overlap_rule = (
        "XOR overlap is allowed. Overlapping black areas cancel each other out."
        if overlap_allowed
        else "This level generally does not require XOR cancellation, but the engine still applies XOR semantics on overlapping regions."
    )

    inventory_text = _format_inventory(level_data)
    grid_size = level_data.get("gridSize", "?")
    difficulty_label = meta.get("difficultyLabel", "Unlabeled")
    required_shape_count = meta.get("requiredShapeCount", "Unknown")
    distractor_shape_count = meta.get("distractorShapeCount", "Unknown")
    level_id = level_data.get("ID") or level_data.get("name") or "(unknown)"

    return f"""## 1. TASK
Choose how to rotate and translate base shapes onto the grid so that their XOR-overlapped union exactly reproduces the target pattern.
The puzzle is solved when the rasterized pixel mask of the chosen placements equals the target pattern's pixel mask.

## 2. WORLD MODEL
- Grid: an integer grid of size `gridSize x gridSize`. The grid coordinate origin is the bottom-left corner; x increases to the right, y increases upward.
- Base shape: a polygon defined by a sequence of named vertices V1, V2, ... in the shape's local coordinate frame. The local origin is `[0, 0]`.
- Vertex id: the literal vertex name (e.g. "V1", "V2", ...) used to anchor a placement.
- Placement: pick one base shape, rotate it clockwise around its local origin by 0/90/180/270 degrees, then translate so a chosen post-rotation vertex lands on a chosen grid coordinate.
- XOR overlap: when shapes overlap, the overlapping region is removed (symmetric difference of pixel masks). {overlap_rule}
- Target pattern: the goal black region painted on the grid.

## 3. VISUAL LEGEND
- Image 1: the target pattern, drawn on the grid with coordinate labels visible.
- Image 2..N: one image per base shape, with vertex labels "V1, V2, ..." printed at each vertex and the local origin marked.
- All images share the same grid coordinate system (origin bottom-left, x right, y up).

## 4. INPUT FIELDS
- level_id: {level_id}
- grid_size: {grid_size}x{grid_size}
- difficulty_tier: {difficulty_label}
- minimum_required_shapes: {required_shape_count}
- distractor_shapes: {distractor_shape_count}
- xor_overlap_allowed: {overlap_allowed}
- inventory (each base shape's vertex coordinates):
{inventory_text}

## 5. ACTION VOCABULARY
A complete answer is one ordered list of `placement` objects:
- placement: {{"shape": <shape id>, "angle": 0|90|180|270, "vertex": <vertex id>, "grid": [<int>, <int>]}}
- `shape` is one of the inventory shape ids above.
- `angle` is the clockwise rotation in degrees, applied around the shape's local origin before translation.
- `vertex` is the post-rotation vertex of the chosen shape used as the placement anchor.
- `grid` is the global grid coordinate where the chosen anchor vertex lands.

## 6. CONSTRAINTS
- Each shape may be used at most once (no shape appears twice in the placements list).
- `angle` must be exactly one of {{0, 90, 180, 270}}.
- `vertex` must be a valid vertex id of the chosen shape (e.g. "V1" .. "Vk").
- `grid` coordinates may extend outside `[0, gridSize)` only if the resulting placement still fits the puzzle's framing — overshooting cells outside the target are scored as misses.
- The final XOR-union of all placement pixel masks must equal the target pattern's pixel mask for a perfect score.

## 7. SOLVING ADVICE
- Identify large unique shapes in the target first; small shapes are usually used to fill remaining gaps.
- When XOR overlap is allowed, two shapes overlapping each other can carve a hole — useful when the target has concavities the base shapes cannot reproduce alone.
- Anchor each placement to a corner vertex (V1 typically) when possible; it makes the translation reasoning easier to verify.

## 8. OUTPUT SCHEMA
FINAL_JSON: {{"placements":[{{"shape":"<id>","angle":<0|90|180|270>,"vertex":"<id>","grid":[<int>,<int>]}}, ...]}}
- placements: list of placement objects.
- shape: string, must be a key from the inventory.
- angle: integer in {{0, 90, 180, 270}}.
- vertex: string, a valid vertex id of the chosen shape.
- grid: array of two integers `[gridX, gridY]`.

## 9. FINAL INSTRUCTION
You may include reasoning above, but the very last line of your reply must start with FINAL_JSON: followed by exactly one valid JSON object.
Do not wrap FINAL_JSON in code fences and do not write anything after it."""


# ---------- multimodal message assembly ----------

def _encode_image(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def _image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{_encode_image(image_path)}"


def build_messages(level_path: Path, level_data: dict[str, Any]) -> list[dict[str, Any]]:
    user_text = build_user_prompt(level_data)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]

    image_assets = level_data.get("imageAssets", {})
    target_path = resolve_level_asset_path(level_path, image_assets["target"])
    user_content.append({
        "type": "text",
        "text": "Image 1: target pattern (the goal silhouette to reconstruct), drawn on the labeled grid.",
    })
    user_content.append({
        "type": "image_url",
        "image_url": {"url": _image_data_url(target_path)},
    })

    shape_assets = image_assets.get("shapes", {})
    for index, (shape_id, image_relative_path) in enumerate(shape_assets.items(), start=2):
        image_path = resolve_level_asset_path(level_path, image_relative_path)
        user_content.append({
            "type": "text",
            "text": f"Image {index}: base shape {shape_id} with its vertex labels and local origin marked.",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_path)},
        })

    return [
        {"role": "system", "content": build_system_prompt(level_data)},
        {"role": "user", "content": user_content},
    ]
