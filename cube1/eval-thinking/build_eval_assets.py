from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from eval_common import FaceAnswer, FaceObservation, PuzzleTask, TaskImages


REPO_ROOT = Path(__file__).resolve().parent.parent
LEVELS_DIR = REPO_ROOT / "levels" / "reconstruct"
DATA_DIR = REPO_ROOT / "data"
TASK_JSON_DIR = DATA_DIR / "task_jsons"
IMAGE_DIR = DATA_DIR / "images"
BLANK_NET_IMAGE_DIR = IMAGE_DIR / "blank_nets"
PATH_SEQUENCE_IMAGE_DIR = IMAGE_DIR / "path_sequences"
MANIFEST_DIR = DATA_DIR / "manifests"
MANIFEST_PATH = MANIFEST_DIR / "reconstruct_tasks.jsonl"
SHARED_BLANK_NET_IMAGE_PATH = BLANK_NET_IMAGE_DIR / "open.png"

CARD_WIDTH = 132
CARD_HEIGHT = 184
CARD_GAP = 18
PADDING_X = 28
PADDING_Y = 26
TILE_SIZE = 76
TITLE_HEIGHT = 44
DIR_CHIP_HEIGHT = 42
DIR_CHIP_GAP_X = 10
DIR_CHIP_GAP_Y = 12
OBSERVED_COLS = 7
DIR_COLS = 5

BG_COLOR = (18, 22, 48, 255)
CARD_BG = (35, 41, 82, 255)
CARD_BORDER = (66, 220, 201, 255)
TEXT_PRIMARY = (238, 242, 255, 255)
TEXT_SECONDARY = (176, 188, 214, 255)
TILE_BG = (28, 33, 69, 255)
DIR_CHIP_BG = (56, 52, 105, 255)
DIR_CHIP_BORDER = (101, 97, 163, 255)
DIR_CHIP_TEXT = (234, 236, 255, 255)
DIR_CHIP_MUTED = (206, 211, 255, 255)

TEXT_COLORS = [
    (255, 230, 109, 255), (168, 230, 207, 255), (221, 160, 221, 255), (135, 206, 235, 255),
    (240, 230, 140, 255), (255, 179, 71, 255), (255, 138, 128, 255), (130, 177, 255, 255),
    (185, 246, 202, 255), (255, 204, 128, 255), (230, 238, 156, 255), (128, 222, 234, 255),
    (206, 147, 216, 255), (255, 171, 145, 255), (144, 202, 249, 255), (179, 157, 219, 255),
    (255, 205, 210, 255), (197, 225, 165, 255), (159, 168, 218, 255), (128, 203, 196, 255),
    (255, 236, 179, 255), (244, 143, 177, 255), (165, 214, 167, 255), (129, 212, 250, 255),
    (209, 196, 233, 255), (255, 204, 188, 255), (220, 237, 200, 255), (207, 216, 220, 255),
    (248, 187, 208, 255), (178, 235, 242, 255), (200, 230, 201, 255), (255, 245, 157, 255),
    (239, 154, 154, 255), (156, 204, 101, 255), (77, 208, 225, 255),
]

PATTERN_COLORS = {
    "arrow_up": (255, 107, 107, 255),
    "arrow_right": (78, 205, 196, 255),
    "arrow_down": (255, 159, 67, 255),
    "arrow_left": (93, 173, 226, 255),
    "star": (255, 215, 0, 255),
    "heart": (255, 71, 87, 255),
    "smile": (255, 217, 61, 255),
    "circle": (168, 230, 207, 255),
    "triangle": (247, 220, 111, 255),
    "square": (248, 196, 113, 255),
    "diamond": (187, 143, 206, 255),
    "plus": (241, 148, 138, 255),
    "?": (215, 223, 245, 255),
}

DIR_META = {
    "N": {"arrow": "↑", "label": "Up"},
    "S": {"arrow": "↓", "label": "Down"},
    "E": {"arrow": "→", "label": "Right"},
    "W": {"arrow": "←", "label": "Left"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model-eval JSON plus path sequence images from level JSON.")
    parser.add_argument(
        "--input",
        type=Path,
        default=LEVELS_DIR,
        help="Path to one level JSON file or a directory of level JSON files.",
    )
    return parser.parse_args()


def ensure_directories() -> None:
    for path in [
        DATA_DIR,
        TASK_JSON_DIR,
        IMAGE_DIR,
        BLANK_NET_IMAGE_DIR,
        PATH_SEQUENCE_IMAGE_DIR,
        MANIFEST_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def iter_level_paths(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.json"))


def load_level(level_path: Path) -> Dict[str, object]:
    with level_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def relative_posix(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def relative_to_data(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: List[Path | str] = []
    windows_fonts = Path("C:/Windows/Fonts")
    if bold:
        candidates.extend(
            [
                windows_fonts / "msyhbd.ttc",
                windows_fonts / "msyh.ttf",
                windows_fonts / "simhei.ttf",
                windows_fonts / "simsun.ttc",
                windows_fonts / "arialbd.ttf",
                windows_fonts / "seguisb.ttf",
                windows_fonts / "calibrib.ttf",
                "msyhbd.ttc",
                "msyh.ttf",
                "simhei.ttf",
                "arialbd.ttf",
                "DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                windows_fonts / "msyh.ttf",
                windows_fonts / "simsun.ttc",
                windows_fonts / "simhei.ttf",
                windows_fonts / "arial.ttf",
                windows_fonts / "segoeui.ttf",
                windows_fonts / "calibri.ttf",
                "msyh.ttf",
                "simsun.ttc",
                "simhei.ttf",
                "arial.ttf",
                "DejaVuSans.ttf",
            ]
        )

    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue

    return ImageFont.load_default()


FONT_TITLE = load_font(24, bold=True)
FONT_STEP = load_font(18, bold=True)
FONT_DIR = load_font(16, bold=True)
FONT_TEXT = load_font(15, bold=False)
FONT_SYMBOL = load_font(44, bold=True)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: Sequence[float],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = left + ((right - left) - width) / 2
    y = top + ((bottom - top) - height) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def draw_polygon_star(draw: ImageDraw.ImageDraw, size: int, color: Tuple[int, int, int, int]) -> None:
    cx = size / 2
    cy = size / 2
    outer_r = size * 0.3
    inner_r = outer_r * 0.42
    points: List[Tuple[float, float]] = []
    for index in range(10):
        angle = math.radians(-90 + index * 36)
        radius = outer_r if index % 2 == 0 else inner_r
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=color)


def draw_arrow(draw: ImageDraw.ImageDraw, size: int, direction: str, color: Tuple[int, int, int, int]) -> None:
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


def draw_smile(draw: ImageDraw.ImageDraw, size: int, color: Tuple[int, int, int, int]) -> None:
    cx = size / 2
    cy = size / 2
    r = size * 0.3
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    eye_r = size * 0.03
    eye_color = (45, 48, 58, 255)
    draw.ellipse((cx - r * 0.38 - eye_r, cy - r * 0.18 - eye_r, cx - r * 0.38 + eye_r, cy - r * 0.18 + eye_r), fill=eye_color)
    draw.ellipse((cx + r * 0.38 - eye_r, cy - r * 0.18 - eye_r, cx + r * 0.38 + eye_r, cy - r * 0.18 + eye_r), fill=eye_color)
    smile_box = (cx - r * 0.48, cy - r * 0.05, cx + r * 0.48, cy + r * 0.55)
    draw.arc(smile_box, start=15, end=165, fill=eye_color, width=max(1, int(size * 0.03)))


def draw_heart(draw: ImageDraw.ImageDraw, size: int, color: Tuple[int, int, int, int]) -> None:
    left_circle = (size * 0.24, size * 0.2, size * 0.52, size * 0.48)
    right_circle = (size * 0.48, size * 0.2, size * 0.76, size * 0.48)
    draw.ellipse(left_circle, fill=color)
    draw.ellipse(right_circle, fill=color)
    draw.polygon(
        [
            (size * 0.2, size * 0.34),
            (size * 0.8, size * 0.34),
            (size * 0.5, size * 0.82),
        ],
        fill=color,
    )


def draw_text_pattern(draw: ImageDraw.ImageDraw, size: int, text: str, color: Tuple[int, int, int, int]) -> None:
    draw_centered_text(draw, (0, 0, size, size), text, FONT_SYMBOL, color)


def get_pattern_color(pattern_id: str) -> Tuple[int, int, int, int]:
    if pattern_id.isdigit() and pattern_id != "0":
        return TEXT_COLORS[int(pattern_id) - 1]
    if len(pattern_id) == 1 and pattern_id.isalpha():
        index = (ord(pattern_id.upper()) - ord("A") + 9) % len(TEXT_COLORS)
        return TEXT_COLORS[index]
    return PATTERN_COLORS.get(pattern_id, (229, 233, 255, 255))


def draw_pattern(pattern_id: str, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = get_pattern_color(pattern_id)

    if pattern_id.isdigit() or (len(pattern_id) == 1 and pattern_id.isalpha()):
        draw_text_pattern(draw, size, pattern_id, color)
    elif pattern_id == "star":
        draw_polygon_star(draw, size, color)
    elif pattern_id == "heart":
        draw_heart(draw, size, color)
    elif pattern_id == "smile":
        draw_smile(draw, size, color)
    elif pattern_id == "arrow_up":
        draw_arrow(draw, size, "up", color)
    elif pattern_id == "arrow_right":
        draw_arrow(draw, size, "right", color)
    elif pattern_id == "arrow_down":
        draw_arrow(draw, size, "down", color)
    elif pattern_id == "arrow_left":
        draw_arrow(draw, size, "left", color)
    elif pattern_id == "circle":
        r = size * 0.26
        cx = size / 2
        cy = size / 2
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    elif pattern_id == "square":
        side = size * 0.52
        offset = (size - side) / 2
        draw.rounded_rectangle((offset, offset, offset + side, offset + side), radius=size * 0.06, fill=color)
    elif pattern_id == "triangle":
        draw.polygon(
            [
                (size / 2, size * 0.18),
                (size * 0.76, size * 0.78),
                (size * 0.24, size * 0.78),
            ],
            fill=color,
        )
    elif pattern_id == "diamond":
        draw.polygon(
            [
                (size / 2, size * 0.18),
                (size * 0.82, size / 2),
                (size / 2, size * 0.82),
                (size * 0.18, size / 2),
            ],
            fill=color,
        )
    elif pattern_id == "plus":
        thickness = size * 0.16
        length = size * 0.58
        cx = size / 2
        cy = size / 2
        draw.rounded_rectangle(
            (cx - thickness / 2, cy - length / 2, cx + thickness / 2, cy + length / 2),
            radius=thickness / 2,
            fill=color,
        )
        draw.rounded_rectangle(
            (cx - length / 2, cy - thickness / 2, cx + length / 2, cy + thickness / 2),
            radius=thickness / 2,
            fill=color,
        )
    else:
        draw_text_pattern(draw, size, pattern_id, color)

    return image


def render_pattern_tile(face: Dict[str, object], tile_size: int = TILE_SIZE) -> Image.Image:
    tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    draw.rounded_rectangle((0, 0, tile_size - 1, tile_size - 1), radius=14, fill=TILE_BG)

    pattern_layer = draw_pattern(str(face["patternId"]), tile_size)

    rotation = int(face.get("rotation", 0)) % 360
    if rotation:
        pattern_layer = pattern_layer.rotate(-rotation, resample=Image.Resampling.BICUBIC)

    if face.get("flipHorizontal"):
        pattern_layer = ImageOps.mirror(pattern_layer)
    if face.get("flipVertical"):
        pattern_layer = ImageOps.flip(pattern_layer)

    tile.alpha_composite(pattern_layer)
    return tile


def chip_width(text: str) -> int:
    temp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    bbox = draw.textbbox((0, 0), text, font=FONT_DIR)
    return max(96, (bbox[2] - bbox[0]) + 34)


def render_direction_chips(
    draw: ImageDraw.ImageDraw,
    directions: Sequence[str],
    start_y: int,
    content_width: int,
) -> int:
    draw_centered_text(draw, (0, start_y, content_width, start_y + 34), "Roll Sequence", FONT_TITLE, TEXT_PRIMARY)
    y = start_y + 52
    chip_widths = [chip_width(f"{index + 1}.{DIR_META[direction]['arrow']}{DIR_META[direction]['label']}") for index, direction in enumerate(directions)]
    max_per_row = DIR_COLS
    for row_start in range(0, len(directions), max_per_row):
        row_directions = directions[row_start:row_start + max_per_row]
        row_widths = chip_widths[row_start:row_start + max_per_row]
        total_row_width = sum(row_widths) + DIR_CHIP_GAP_X * max(0, len(row_widths) - 1)
        x = max(PADDING_X, int((content_width - total_row_width) / 2))
        for index, direction in enumerate(row_directions, start=row_start):
            width = row_widths[index - row_start]
            text = f"{index + 1}.{DIR_META[direction]['arrow']}{DIR_META[direction]['label']}"
            draw.rounded_rectangle(
                (x, y, x + width, y + DIR_CHIP_HEIGHT),
                radius=DIR_CHIP_HEIGHT // 2,
                fill=DIR_CHIP_BG,
                outline=DIR_CHIP_BORDER,
                width=2,
            )
            draw_centered_text(draw, (x, y, x + width, y + DIR_CHIP_HEIGHT), text, FONT_DIR, DIR_CHIP_TEXT)
            x += width + DIR_CHIP_GAP_X
        y += DIR_CHIP_HEIGHT + DIR_CHIP_GAP_Y
    return y


def render_observed_cards(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    observed_faces: Sequence[Dict[str, object]],
    start_y: int,
    content_width: int,
) -> None:
    draw_centered_text(draw, (0, start_y, content_width, start_y + 34), "Path-View Patterns", FONT_TITLE, TEXT_PRIMARY)
    y = start_y + 54
    cols = min(OBSERVED_COLS, max(1, len(observed_faces)))
    card_w = 86
    card_h = 108
    tile_size = 50
    gap_x = 14
    gap_y = 14

    for row_start in range(0, len(observed_faces), cols):
        row_faces = observed_faces[row_start:row_start + cols]
        total_row_width = len(row_faces) * card_w + max(0, len(row_faces) - 1) * gap_x
        x = max(PADDING_X, int((content_width - total_row_width) / 2))

        for index, face in enumerate(row_faces, start=row_start):
            left = x
            top = y
            draw.rounded_rectangle(
                (left, top, left + card_w, top + card_h),
                radius=14,
                fill=CARD_BG,
                outline=CARD_BORDER,
                width=2,
            )
            draw_centered_text(
                draw,
                (left, top + 8, left + card_w, top + 32),
                f"Obs {index + 1}",
                FONT_STEP,
                TEXT_SECONDARY,
            )
            tile = render_pattern_tile(face, tile_size)
            tile_left = int(left + (card_w - tile_size) / 2)
            tile_top = int(top + 46)
            image.alpha_composite(tile, (tile_left, tile_top))
            x += card_w + gap_x
        y += card_h + gap_y


def render_path_sequence_image(level: Dict[str, object], output_path: Path) -> None:
    observed_faces = level["prompt"]["observedPathFaces"]
    directions = level["prompt"]["directions"]
    content_width = max(700, PADDING_X * 2 + min(max(1, len(observed_faces)), OBSERVED_COLS) * 100)
    direction_rows = max(1, math.ceil(len(directions) / DIR_COLS))
    observed_rows = max(1, math.ceil(len(observed_faces) / OBSERVED_COLS))
    height = (
        PADDING_Y * 2
        + 36
        + direction_rows * (DIR_CHIP_HEIGHT + DIR_CHIP_GAP_Y)
        + 30
        + 40
        + observed_rows * (108 + 14)
        + 24
    )
    width = content_width

    image = Image.new("RGBA", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(image)

    next_y = render_direction_chips(draw, directions, PADDING_Y, width)
    render_observed_cards(image, draw, observed_faces, next_y + 8, width)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output_path)


def build_text_description(level: Dict[str, object]) -> str:
    directions = " -> ".join(level["prompt"]["directions"])
    return (
        "Task: reconstruct the six outer faces of the cube from the blank cross net image and the path-view observation image.\n"
        "The net uses the fixed face names TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT.\n"
        "If a face cannot be uniquely determined, output patternId='?' and rotation=0.\n"
        f"Roll sequence: {directions}\n"
        "The puzzle image already shows the observed path-face state after each roll."
    )


def build_task(level: Dict[str, object], level_path: Path) -> PuzzleTask:
    code = str(level["code"])
    path_sequence_image_path = PATH_SEQUENCE_IMAGE_DIR / f"{code}_path_sequence.png"
    blank_net_image_path = BLANK_NET_IMAGE_DIR / f"{code}_blank_net.png"
    observed_faces = [
        FaceObservation.from_dict(face)
        for face in level["prompt"]["observedPathFaces"]
    ]
    answer = {
        key: FaceAnswer.from_dict(value)
        for key, value in level["answers"]["solutionFaces"].items()
    }

    return PuzzleTask(
        sample_id=code,
        text_description=build_text_description_for_eval(level),
        net_layout=str(level.get("netLayout", "standard_cross")),
        roll_sequence=[str(item) for item in level["prompt"]["directions"]],
        observed_path_faces=observed_faces,
        image_paths=TaskImages(
            blank_net_image=relative_to_data(SHARED_BLANK_NET_IMAGE_PATH),
            path_sequence_image=relative_to_data(path_sequence_image_path),
        ),
        answer=answer,
        metadata={
            "level_id": level["id"],
            "name": level["name"],
            "difficulty": level["difficulty"],
            "move_count": level["moveCount"],
            "tier": level["tier"],
            "source_level_path": relative_posix(level_path),
        },
    )


def build_text_description_for_eval(level: Dict[str, object]) -> str:
    directions = " -> ".join(level["prompt"]["directions"])
    # 中文对照：
    # - 任务：根据空白十字展开图和路径俯视图案，还原立方体六个面的图案和旋转角度。
    # - 展开图固定使用 TOP、BOTTOM、FRONT、BACK、LEFT、RIGHT 六个面位。
    # - 无法唯一确定的面可以输出 patternId='?' 且 rotation=0。
    # - 题面图片里已经展示了滚动路径和路径上的图案状态。
    return (
        "Task: reconstruct the six outer faces of the cube from the blank cross net "
        "image and the path-view observation image.\n"
        "The net uses the fixed face names TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT.\n"
        "If a face cannot be uniquely determined, output patternId='?' and rotation=0.\n"
        f"Roll sequence: {directions}\n"
        "The puzzle images already show the roll path and the observed path-face states."
    )


def write_task_json(task: PuzzleTask) -> Path:
    output_path = TASK_JSON_DIR / f"{task.sample_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(task.to_dict(), handle, ensure_ascii=False, indent=2)
    return output_path


def write_manifest(tasks: Iterable[PuzzleTask]) -> None:
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")


def build_assets_for_level(level_path: Path) -> PuzzleTask:
    level = load_level(level_path)
    task = build_task(level, level_path)
    render_path_sequence_image(level, REPO_ROOT / task.image_paths.path_sequence_image)
    write_task_json(task)
    return task


def main() -> None:
    args = parse_args()
    ensure_directories()
    level_paths = iter_level_paths(args.input)
    tasks = [build_assets_for_level(level_path) for level_path in level_paths]
    write_manifest(tasks)
    print(
        f"Generated {len(tasks)} task json files in {TASK_JSON_DIR} "
        f"and path sequence images in {PATH_SEQUENCE_IMAGE_DIR}"
    )


if __name__ == "__main__":
    main()
