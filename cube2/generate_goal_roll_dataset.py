from __future__ import annotations

import json
import random
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


NEWCUBE_ROOT = Path(__file__).resolve().parent
SOURCE_TASKS_DIR = NEWCUBE_ROOT / "source_data" / "task_jsons"
TARGET_DATA_DIR = NEWCUBE_ROOT / "data2"
TARGET_TASK_DIR = TARGET_DATA_DIR / "task_jsons"
TARGET_MANIFEST_DIR = TARGET_DATA_DIR / "manifests"
TARGET_MANIFEST_PATH = TARGET_MANIFEST_DIR / "goal_roll_tasks.jsonl"
SAMPLED_MANIFEST_PATH = TARGET_MANIFEST_DIR / "sampled_150_seed20260425.jsonl"
TARGET_INDEX_PATH = TARGET_DATA_DIR / "index.json"
TARGET_README_PATH = TARGET_DATA_DIR / "README.md"
TARGET_IMAGE_DIR = NEWCUBE_ROOT / "images"
SEED = 20260425
SAMPLED_COUNT = 150

sys.path.insert(0, str((NEWCUBE_ROOT / "eval-thinking").resolve()))
from engine_interface import cube_from_solution_faces, observe_top_face  # noqa: E402


FACE_ORDER = ["TOP", "FRONT", "RIGHT", "BACK", "LEFT", "BOTTOM"]
FACE_LABELS = {
    "TOP": "TOP",
    "BOTTOM": "BOTTOM",
    "FRONT": "FRONT",
    "BACK": "BACK",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
}
RECONSTRUCTION_NET_POSITIONS = {
    "BACK": {"row": 0, "col": 1},
    "LEFT": {"row": 1, "col": 0},
    "TOP": {"row": 1, "col": 1},
    "RIGHT": {"row": 1, "col": 2},
    "FRONT": {"row": 2, "col": 1},
    "BOTTOM": {"row": 3, "col": 1},
}
DIRECTION_LABELS = {
    "N": "Up",
    "S": "Down",
    "W": "Left",
    "E": "Right",
}

TEXT_COLORS = [
    "#FFE66D", "#A8E6CF", "#DDA0DD", "#87CEEB", "#F0E68C",
    "#FFB347", "#FF8A80", "#82B1FF", "#B9F6CA", "#FFCC80",
    "#E6EE9C", "#80DEEA", "#CE93D8", "#FFAB91", "#90CAF9",
    "#B39DDB", "#FFCDD2", "#C5E1A5", "#9FA8DA", "#80CBC4",
    "#FFECB3", "#F48FB1", "#A5D6A7", "#81D4FA", "#D1C4E9",
    "#FFCCBC", "#DCEDC8", "#CFD8DC", "#F8BBD0", "#B2EBF2",
    "#C8E6C9", "#FFF59D", "#EF9A9A", "#9CCC65", "#4DD0E1",
]
PATTERN_COLORS = {
    "arrow_up": "#FF6B6B",
    "arrow_right": "#4ECDC4",
    "arrow_down": "#FF9F43",
    "arrow_left": "#5DADE2",
    "star": "#FFD700",
    "heart": "#FF4757",
    "smile": "#FFD93D",
    "circle": "#A0E7E5",
    "triangle": "#FFE66D",
    "square": "#74B9FF",
    "diamond": "#FFB4A2",
    "plus": "#C77DFF",
}
CANVAS_BG = "#17132B"
CARD_BG = "#1A1634"
FACE_BG = "#231F48"
CARD_BORDER = "#22D3EE"
TEXT_SOFT = "#D7D2FF"
TEXT_WARM = "#FFBF69"
IMAGE_WIDTH = 760
IMAGE_HEIGHT = 1040
OUTER_PADDING = 38
NET_CELL_W = 176
NET_CELL_H = 214
NET_GAP = 22
FACE_BOX_SIZE = 104
TARGET_FACE_IMAGE_SIZE = 512


@dataclass
class GeneratedTask:
    code: str
    payload: dict[str, Any]


def get_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/arialbd.ttf"),
                Path("C:/Windows/Fonts/segoeuib.ttf"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/arial.ttf"),
                Path("C:/Windows/Fonts/segoeui.ttf"),
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_face(face: dict[str, Any]) -> dict[str, Any]:
    return {
        "patternId": str(face.get("patternId", "?")),
        "rotation": int(face.get("rotation", 0)) % 360,
    }


def normalize_visible_solution_face(face: dict[str, Any]) -> dict[str, Any]:
    return {
        "patternId": str(face.get("patternId", "?")),
        "rotation": int(face.get("rotation", 0)) % 360,
    }


def get_text_pattern_color(text: str) -> str:
    if not text:
        return "#FFFFFF"
    if text.isdigit():
        index = max(0, min(8, int(text) - 1))
        return TEXT_COLORS[index]
    if len(text) == 1 and text.isalpha():
        index = (ord(text.upper()) - ord("A") + 9) % len(TEXT_COLORS)
        return TEXT_COLORS[index]
    return "#FFFFFF"


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = left + (right - left - width) / 2
    y = top + (bottom - top - height) / 2 - 2
    draw.text((x, y), text, font=font, fill=fill)


def draw_arrow(draw: ImageDraw.ImageDraw, size: int, color: str, direction: str) -> None:
    cx = size / 2
    cy = size / 2
    s = size * 0.35
    if direction == "up":
        points = [
            (cx, cy - s),
            (cx + s * 0.7, cy + s * 0.3),
            (cx + s * 0.25, cy + s * 0.3),
            (cx + s * 0.25, cy + s),
            (cx - s * 0.25, cy + s),
            (cx - s * 0.25, cy + s * 0.3),
            (cx - s * 0.7, cy + s * 0.3),
        ]
    elif direction == "right":
        points = [
            (cx + s, cy),
            (cx - s * 0.3, cy - s * 0.7),
            (cx - s * 0.3, cy - s * 0.25),
            (cx - s, cy - s * 0.25),
            (cx - s, cy + s * 0.25),
            (cx - s * 0.3, cy + s * 0.25),
            (cx - s * 0.3, cy + s * 0.7),
        ]
    elif direction == "down":
        points = [
            (cx, cy + s),
            (cx + s * 0.7, cy - s * 0.3),
            (cx + s * 0.25, cy - s * 0.3),
            (cx + s * 0.25, cy - s),
            (cx - s * 0.25, cy - s),
            (cx - s * 0.25, cy - s * 0.3),
            (cx - s * 0.7, cy - s * 0.3),
        ]
    else:
        points = [
            (cx - s, cy),
            (cx + s * 0.3, cy - s * 0.7),
            (cx + s * 0.3, cy - s * 0.25),
            (cx + s, cy - s * 0.25),
            (cx + s, cy + s * 0.25),
            (cx + s * 0.3, cy + s * 0.25),
            (cx + s * 0.3, cy + s * 0.7),
        ]
    draw.polygon(points, fill=color)


def draw_star(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    import math

    cx = size / 2
    cy = size / 2
    outer_r = size * 0.33
    inner_r = outer_r * 0.4
    points: list[tuple[float, float]] = []
    for index in range(5):
        outer_angle = math.radians(index * 72 - 90)
        inner_angle = math.radians(index * 72 - 54)
        points.append((cx + outer_r * math.cos(outer_angle), cy + outer_r * math.sin(outer_angle)))
        points.append((cx + inner_r * math.cos(inner_angle), cy + inner_r * math.sin(inner_angle)))
    draw.polygon(points, fill=color)


def draw_heart(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    import math

    points: list[tuple[float, float]] = []
    scale = size / 32
    offset_x = size / 2
    offset_y = size / 2 + size * 0.04
    for step in range(0, 361, 6):
        theta = math.radians(step)
        x = 16 * math.sin(theta) ** 3
        y = (
            13 * math.cos(theta)
            - 5 * math.cos(2 * theta)
            - 2 * math.cos(3 * theta)
            - math.cos(4 * theta)
        )
        points.append((offset_x + x * scale * 0.75, offset_y - y * scale * 0.75))
    draw.polygon(points, fill=color)


def draw_smile(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    draw.ellipse((size * 0.18, size * 0.18, size * 0.82, size * 0.82), fill=color)
    eye_color = "#3B2F2F"
    draw.ellipse((size * 0.36, size * 0.38, size * 0.42, size * 0.44), fill=eye_color)
    draw.ellipse((size * 0.58, size * 0.38, size * 0.64, size * 0.44), fill=eye_color)
    draw.arc((size * 0.34, size * 0.42, size * 0.66, size * 0.7), start=18, end=162, fill=eye_color, width=max(2, size // 18))


def draw_circle(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    margin = size * 0.23
    draw.ellipse((margin, margin, size - margin, size - margin), fill=color)


def draw_triangle(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    cx = size / 2
    top = size * 0.2
    bottom = size * 0.8
    half_base = size * 0.24
    draw.polygon([(cx, top), (cx + half_base, bottom), (cx - half_base, bottom)], fill=color)


def draw_square(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    side = size * 0.54
    offset = (size - side) / 2
    draw.rectangle((offset, offset, offset + side, offset + side), fill=color)


def draw_diamond(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    cx = size / 2
    cy = size / 2
    radius = size * 0.3
    draw.polygon([(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)], fill=color)


def draw_plus(draw: ImageDraw.ImageDraw, size: int, color: str) -> None:
    thickness = size * 0.16
    length = size * 0.62
    cx = size / 2
    cy = size / 2
    draw.rectangle((cx - thickness / 2, cy - length / 2, cx + thickness / 2, cy + length / 2), fill=color)
    draw.rectangle((cx - length / 2, cy - thickness / 2, cx + length / 2, cy + thickness / 2), fill=color)


def render_pattern_square(face: dict[str, Any], size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), FACE_BG)
    draw = ImageDraw.Draw(image)
    pattern_id = str(face.get("patternId", "?"))

    if pattern_id == "?":
        draw_centered_text(draw, (0, 0, size, size), "?", font=get_font(int(size * 0.56), bold=True), fill="#FFFFFF")
    elif pattern_id in "123456789" or (len(pattern_id) == 1 and pattern_id.isalpha()):
        draw_centered_text(
            draw,
            (0, 0, size, size),
            pattern_id,
            font=get_font(int(size * 0.56), bold=True),
            fill=get_text_pattern_color(pattern_id),
        )
    elif pattern_id == "arrow_up":
        draw_arrow(draw, size, PATTERN_COLORS[pattern_id], "up")
    elif pattern_id == "arrow_right":
        draw_arrow(draw, size, PATTERN_COLORS[pattern_id], "right")
    elif pattern_id == "arrow_down":
        draw_arrow(draw, size, PATTERN_COLORS[pattern_id], "down")
    elif pattern_id == "arrow_left":
        draw_arrow(draw, size, PATTERN_COLORS[pattern_id], "left")
    elif pattern_id == "star":
        draw_star(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "heart":
        draw_heart(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "smile":
        draw_smile(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "circle":
        draw_circle(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "triangle":
        draw_triangle(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "square":
        draw_square(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "diamond":
        draw_diamond(draw, size, PATTERN_COLORS[pattern_id])
    elif pattern_id == "plus":
        draw_plus(draw, size, PATTERN_COLORS[pattern_id])
    else:
        draw_centered_text(draw, (0, 0, size, size), pattern_id, font=get_font(int(size * 0.42), bold=True), fill="#FFFFFF")

    rotation = int(face.get("rotation", 0) or 0)
    if rotation:
        image = image.rotate(-rotation, resample=Image.Resampling.BICUBIC)

    return image


def build_level_image_dir(code: str) -> Path:
    return TARGET_IMAGE_DIR / code


def build_initial_net_image_relative_path(code: str) -> str:
    return f"../images/{code}/initial_net.png"


def build_target_top_face_image_relative_path(code: str) -> str:
    return f"../images/{code}/target_top_face.png"


def render_initial_net_image(task_payload: dict[str, Any], output_path: Path) -> None:
    canvas = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), CANVAS_BG)
    draw = ImageDraw.Draw(canvas)

    title_font = get_font(34, bold=True)
    subtitle_font = get_font(18)
    label_font = get_font(22, bold=True)
    angle_font = get_font(20, bold=True)

    draw.text((OUTER_PADDING, 22), f"{task_payload['code']} INITIAL CROSS NET", font=title_font, fill="#F5F3FF")
    draw.text(
        (OUTER_PADDING, 68),
        "This is the unfolded outer surface of the folded cube.",
        font=subtitle_font,
        fill=TEXT_SOFT,
    )
    draw.text(
        (OUTER_PADDING, 92),
        "The number under each face is the clockwise rotation in degrees from the original upright pattern.",
        font=subtitle_font,
        fill=TEXT_SOFT,
    )

    cells = task_payload["initialCube"]["net"]["cells"]
    for cell in cells:
        row = int(cell["row"])
        col = int(cell["col"])
        left = OUTER_PADDING + col * (NET_CELL_W + NET_GAP)
        top = 146 + row * (NET_CELL_H + NET_GAP)
        right = left + NET_CELL_W
        bottom = top + NET_CELL_H

        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=18,
            fill=CARD_BG,
            outline=CARD_BORDER,
            width=3,
        )

        label = str(cell["faceKey"])
        draw_centered_text(draw, (left, top + 10, right, top + 42), label, font=label_font, fill=TEXT_SOFT)

        face_square = render_pattern_square(cell, FACE_BOX_SIZE)
        face_left = int(left + (NET_CELL_W - FACE_BOX_SIZE) / 2)
        face_top = int(top + 48)
        canvas.alpha_composite(face_square, (face_left, face_top))

        angle_text = "?" if str(cell.get("patternId", "?")) == "?" else str(int(cell.get("rotation", 0)))
        draw_centered_text(draw, (left, bottom - 38, right, bottom - 10), angle_text, font=angle_font, fill=TEXT_WARM)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG")


def render_target_top_face_image(task_payload: dict[str, Any], output_path: Path) -> None:
    canvas = Image.new("RGBA", (TARGET_FACE_IMAGE_SIZE, TARGET_FACE_IMAGE_SIZE), CANVAS_BG)
    draw = ImageDraw.Draw(canvas)
    title_font = get_font(28, bold=True)
    subtitle_font = get_font(18)
    angle_font = get_font(26, bold=True)

    draw.text((28, 24), f"{task_payload['code']} TARGET TOP FACE", font=title_font, fill="#F5F3FF")
    draw.text((28, 60), "Viewed from above after the sequence ends.", font=subtitle_font, fill=TEXT_SOFT)

    target_face = task_payload["targetTopFace"]
    face_square = render_pattern_square(target_face, 220)
    canvas.alpha_composite(face_square, (146, 120))
    draw_centered_text(draw, (100, 364, 412, 404), str(int(target_face.get("rotation", 0))), font=angle_font, fill=TEXT_WARM)
    draw_centered_text(draw, (60, 416, 452, 454), "Clockwise rotation from the original upright pattern", font=subtitle_font, fill=TEXT_SOFT)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG")


def build_initial_net(solution_faces: dict[str, Any]) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for face_key in FACE_ORDER:
        face = normalize_face(solution_faces.get(face_key, {"patternId": "?", "rotation": 0}))
        position = RECONSTRUCTION_NET_POSITIONS[face_key]
        cells.append(
            {
                "faceKey": face_key,
                "faceLabelZh": FACE_LABELS[face_key],
                "row": position["row"],
                "col": position["col"],
                **face,
            }
        )

    return {
        "layout": "reconstruction_cross",
        "faceOrder": FACE_ORDER,
        "cells": cells,
    }


def build_top_face_trace(solution_faces: dict[str, Any], directions: list[str]) -> list[dict[str, Any]]:
    cube = cube_from_solution_faces(solution_faces)
    trace: list[dict[str, Any]] = []
    for direction in directions:
        cube.roll(direction)
        trace.append(normalize_face(observe_top_face(cube)))
    return trace


def build_visible_pattern_set(solution_faces: dict[str, Any]) -> set[str]:
    return {
        str(face.get("patternId", "?"))
        for face in solution_faces.values()
        if str(face.get("patternId", "?")) != "?"
    }


def face_key(face: dict[str, Any]) -> tuple[str, int]:
    normalized = normalize_face(face)
    return (
        normalized["patternId"],
        normalized["rotation"],
    )


def cube_state_key(cube: Any) -> tuple[Any, ...]:
    return tuple(face_key(face) for face in cube.faces)


def find_visible_target_via_bfs(
    solution_faces: dict[str, Any],
    visible_patterns: set[str],
    *,
    max_depth: int = 10,
) -> tuple[dict[str, Any], list[str]] | None:
    if not visible_patterns:
        return None

    start = cube_from_solution_faces(solution_faces)
    queue: deque[tuple[Any, list[str]]] = deque([(start, [])])
    visited = {cube_state_key(start)}

    while queue:
        cube, path = queue.popleft()
        if len(path) >= max_depth:
            continue

        for direction in DIRECTION_LABELS:
            next_cube = cube.clone()
            next_cube.roll(direction)
            key = cube_state_key(next_cube)
            if key in visited:
                continue
            visited.add(key)

            next_path = path + [direction]
            observed = normalize_face(observe_top_face(next_cube))
            if observed["patternId"] in visible_patterns:
                return observed, next_path

            queue.append((next_cube, next_path))

    return None


def choose_target_face_and_directions(
    observed_faces: list[dict[str, Any]],
    directions: list[str],
    visible_patterns: set[str],
    solution_faces: dict[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], list[str], int]:
    if visible_patterns:
        visible_indices = [
            index
            for index, face in enumerate(observed_faces)
            if face.get("patternId") in visible_patterns
        ]
        if visible_indices:
            target_index = rng.choice(visible_indices)
            return observed_faces[target_index], directions[: target_index + 1], target_index

    fallback = find_visible_target_via_bfs(solution_faces, visible_patterns)
    if fallback is not None:
        target_face, answer_directions = fallback
        return target_face, answer_directions, len(answer_directions) - 1

    raise ValueError("Could not find a reachable top-face target using a visible pattern from the initial net.")


def build_task(task_path: Path, source_task: dict[str, Any], rng: random.Random) -> GeneratedTask:
    metadata = dict(source_task.get("metadata", {}))
    code = str(source_task.get("level_code") or source_task.get("sample_id") or task_path.stem)
    directions = [str(item) for item in source_task.get("roll_sequence", [])]
    solution_faces = dict(source_task.get("expected_answer", {}))
    top_faces = build_top_face_trace(solution_faces, directions)
    visible_patterns = build_visible_pattern_set(solution_faces)
    target_face, answer_directions, target_index = choose_target_face_and_directions(
        top_faces,
        directions,
        visible_patterns,
        solution_faces,
        rng,
    )

    payload = {
        "taskType": "roll_to_target_top_face",
        "code": code,
        "name": f"Goal Roll {code}",
        "description": (
            "Given the initial cross net and the target top-face image, "
            "output a roll sequence that moves the cube to the target state."
        ),
        "instructions": {
            "en": (
                "You are given the initial state of the cube as a cross-shaped net. "
                "This net is the unfolded outer surface of the folded cube. "
                "Each visible cell is labeled as TOP, BOTTOM, FRONT, BACK, LEFT, or RIGHT. "
                "The number under each visible face is the clockwise rotation in degrees from the original upright pattern. "
                "Output a roll sequence so that, at the end, the cube's top face seen from above exactly matches the target image."
            ),
            "directionVocabulary": DIRECTION_LABELS,
        },
        "initialCube": {
            "net": build_initial_net(solution_faces),
            "solutionFaces": {
                face_key: normalize_visible_solution_face(
                    solution_faces.get(face_key, {"patternId": "?", "rotation": 0})
                )
                for face_key in FACE_ORDER
            },
        },
        "targetTopFace": {
            "sourceObservationIndex": target_index,
            "stepNumber": target_index + 1,
            "patternId": target_face["patternId"],
            "rotation": target_face["rotation"],
        },
        "answers": {
            "directions": answer_directions,
            "moveCount": len(answer_directions),
        },
        "imagePaths": {
            "initialNetImage": build_initial_net_image_relative_path(code),
            "targetTopFaceImage": build_target_top_face_image_relative_path(code),
        },
        "metadata": {
            "difficulty": int(metadata.get("difficulty", 0) or 0),
            "tier": int(metadata.get("tier", 0) or 0),
            "targetStepNumber": target_index + 1,
        },
    }

    return GeneratedTask(code=code, payload=payload)


def write_task(task: GeneratedTask) -> Path:
    output_path = TARGET_TASK_DIR / f"{task.code}.json"
    output_path.write_text(json.dumps(task.payload, ensure_ascii=False, indent=2), encoding="utf-8")
    initial_image_path = TARGET_DATA_DIR / task.payload["imagePaths"]["initialNetImage"]
    target_image_path = TARGET_DATA_DIR / task.payload["imagePaths"]["targetTopFaceImage"]
    render_initial_net_image(task.payload, initial_image_path)
    render_target_top_face_image(task.payload, target_image_path)
    return output_path


def write_manifest(tasks: list[GeneratedTask]) -> None:
    with TARGET_MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task.payload, ensure_ascii=False) + "\n")


def write_sampled_manifest(tasks: list[GeneratedTask], sample_count: int, seed: int) -> None:
    rng = random.Random(seed)
    sample_size = min(sample_count, len(tasks))
    sampled = rng.sample(tasks, sample_size)
    sampled.sort(key=lambda task: task.code)

    with SAMPLED_MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        for task in sampled:
            handle.write(json.dumps(task.payload, ensure_ascii=False) + "\n")


def write_index(tasks: list[GeneratedTask]) -> None:
    payload = {
        "taskType": "roll_to_target_top_face",
        "seed": SEED,
        "totalTasks": len(tasks),
        "taskCodes": [task.code for task in tasks],
        "taskDir": str(TARGET_TASK_DIR.relative_to(NEWCUBE_ROOT).as_posix()),
        "manifestPath": str(TARGET_MANIFEST_PATH.relative_to(NEWCUBE_ROOT).as_posix()),
        "imageDir": str(TARGET_IMAGE_DIR.relative_to(NEWCUBE_ROOT).as_posix()),
    }
    TARGET_INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme() -> None:
    content = """# data2

This directory stores the regenerated `cube2` tasks for the top-face target gameplay.

## Task definition

- Input: the visible cross net of the cube's unfolded outer surface.
- The number under each visible face is the clockwise rotation in degrees from the original upright pattern.
- Goal: output a roll sequence so that the cube's top face, seen from above, matches the target image exactly.
- Multiple sequences may be valid. The validator decides correctness.

## Directory structure

- `task_jsons/`: one JSON file per task.
- `manifests/goal_roll_tasks.jsonl`: the full task manifest.
- `manifests/sampled_150_seed20260425.jsonl`: the fixed sampled manifest used for evaluation.
- `index.json`: dataset overview for the web app.
- `../images/<LEVEL_CODE>/`: the paired initial-net and target-top-face images.
- `../source_data/task_jsons/`: the bundled source snapshot used to rebuild the dataset.

## Regeneration

```powershell
python cube2\\generate_goal_roll_dataset.py
python cube2\\retarget_data2_dataset.py
```
"""
    TARGET_README_PATH.write_text(content, encoding="utf-8")


def ensure_dirs() -> None:
    TARGET_TASK_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def generate_dataset() -> list[GeneratedTask]:
    rng = random.Random(SEED)
    tasks: list[GeneratedTask] = []
    for task_path in sorted(SOURCE_TASKS_DIR.glob("C*.json")):
        source_task = load_json(task_path)
        tasks.append(build_task(task_path, source_task, rng))
    return tasks


def main() -> None:
    ensure_dirs()
    tasks = generate_dataset()

    for task in tasks:
        build_level_image_dir(task.code).mkdir(parents=True, exist_ok=True)
        write_task(task)

    write_manifest(tasks)
    write_sampled_manifest(tasks, SAMPLED_COUNT, SEED)
    write_index(tasks)
    write_readme()

    print(f"Generated {len(tasks)} top-face goal-roll tasks into: {TARGET_DATA_DIR}")


if __name__ == "__main__":
    main()
