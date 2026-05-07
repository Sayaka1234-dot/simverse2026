from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


TARGET_CELL_SIZE = 36
TARGET_PADDING = {"top": 36, "right": 24, "bottom": 56, "left": 56}
SHAPE_PADDING = {"top": 40, "right": 24, "bottom": 48, "left": 48}
MIN_SHAPE_GRID_EXTENT = 4
SHAPE_MAX_CANVAS_SIZE = 320
BACKGROUND_COLOR = "#FFFFFF"
GRID_COLOR = "#D9D9D9"
AXIS_COLOR = "#111111"
TICK_COLOR = "#A5A5A5"
FILL_COLOR = (0, 0, 0)
TARGET_IMAGE_NAME = "target.png"
SHAPE_IMAGE_PREFIX = "shape_"
IMAGE_ASSET_FIELD = "imageAssets"


@dataclass(frozen=True)
class CanvasSpec:
    width: int
    height: int
    origin_x: int
    origin_y: int
    cell_size: int
    grid_extent: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render Text-VOI target and shape reference images for all levels."
    )
    parser.add_argument("--levels-dir", default="levels", type=Path)
    parser.add_argument("--images-dir", default="images", type=Path)
    return parser.parse_args()


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]

    for font_path in font_candidates:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_SMALL = load_font(12)
FONT_MEDIUM = load_font(14)
FONT_LARGE = load_font(18)


def build_target_spec(grid_size: int) -> CanvasSpec:
    width = TARGET_PADDING["left"] + grid_size * TARGET_CELL_SIZE + TARGET_PADDING["right"]
    height = TARGET_PADDING["top"] + grid_size * TARGET_CELL_SIZE + TARGET_PADDING["bottom"]
    return CanvasSpec(
        width=width,
        height=height,
        origin_x=TARGET_PADDING["left"],
        origin_y=TARGET_PADDING["top"],
        cell_size=TARGET_CELL_SIZE,
        grid_extent=grid_size,
    )


def build_shape_spec(shape_vertices: dict[str, list[int]]) -> CanvasSpec:
    max_coordinate = max(max(point) for point in shape_vertices.values())
    grid_extent = max(MIN_SHAPE_GRID_EXTENT, max_coordinate + 1)
    available_size = SHAPE_MAX_CANVAS_SIZE - SHAPE_PADDING["left"] - SHAPE_PADDING["right"]
    cell_size = max(24, available_size // grid_extent)
    width = SHAPE_PADDING["left"] + grid_extent * cell_size + SHAPE_PADDING["right"]
    height = SHAPE_PADDING["top"] + grid_extent * cell_size + SHAPE_PADDING["bottom"]
    return CanvasSpec(
        width=width,
        height=height,
        origin_x=SHAPE_PADDING["left"],
        origin_y=SHAPE_PADDING["top"],
        cell_size=cell_size,
        grid_extent=grid_extent,
    )


def sort_vertex_items(shape_vertices: dict[str, list[int]]) -> list[tuple[str, list[int]]]:
    return sorted(shape_vertices.items(), key=lambda item: int(item[0][1:]))


def draw_text_centered(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((x - text_width / 2, y - text_height / 2), text, fill=AXIS_COLOR, font=font)


def draw_text_right(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((x - text_width, y - text_height / 2), text, fill=AXIS_COLOR, font=font)


def draw_grid_base(image: Image.Image, spec: CanvasSpec, title: str | None = None) -> None:
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, 0), (spec.width, spec.height)], fill=BACKGROUND_COLOR)

    grid_pixel_size = spec.grid_extent * spec.cell_size
    grid_left = spec.origin_x
    grid_top = spec.origin_y
    grid_right = grid_left + grid_pixel_size
    grid_bottom = grid_top + grid_pixel_size

    for index in range(spec.grid_extent + 1):
        offset = index * spec.cell_size
        x = grid_left + offset
        y = grid_top + offset
        draw.line([(x, grid_top), (x, grid_bottom)], fill=GRID_COLOR, width=1)
        draw.line([(grid_left, y), (grid_right, y)], fill=GRID_COLOR, width=1)

    draw.rectangle([(grid_left, grid_top), (grid_right, grid_bottom)], outline=AXIS_COLOR, width=2)

    for x in range(spec.grid_extent + 1):
        x_pos = grid_left + x * spec.cell_size
        draw.line([(x_pos, grid_bottom), (x_pos, grid_bottom + 6)], fill=TICK_COLOR, width=1)
        draw_text_centered(draw, x_pos, grid_bottom + 18, str(x), FONT_SMALL)

    for y in range(spec.grid_extent + 1):
        y_pos = grid_top + (spec.grid_extent - y) * spec.cell_size
        draw.line([(grid_left - 6, y_pos), (grid_left, y_pos)], fill=TICK_COLOR, width=1)
        draw_text_right(draw, grid_left - 10, y_pos, str(y), FONT_SMALL)

    draw_text_centered(draw, grid_left + grid_pixel_size / 2, grid_bottom + 36, "X", FONT_MEDIUM)
    draw_text_centered(draw, grid_left - 28, grid_top + grid_pixel_size / 2, "Y", FONT_MEDIUM)

    if title:
        draw.text((grid_left, 10), title, fill=AXIS_COLOR, font=FONT_LARGE)


def grid_points_to_pixels(points: list[list[int]] | list[tuple[int, int]], spec: CanvasSpec) -> list[tuple[int, int]]:
    return [
        (spec.origin_x + point[0] * spec.cell_size, spec.origin_y + (spec.grid_extent - point[1]) * spec.cell_size)
        for point in points
    ]


def rasterize_polygon_mask(
    polygons: list[list[list[int]]], spec: CanvasSpec, xor_mode: bool
) -> np.ndarray:
    width = spec.grid_extent * spec.cell_size
    height = spec.grid_extent * spec.cell_size
    composite = np.zeros((height, width), dtype=bool)

    for polygon in polygons:
        polygon_pixels = [
            (point[0] * spec.cell_size, (spec.grid_extent - point[1]) * spec.cell_size)
            for point in polygon
        ]
        temporary = Image.new("1", (width, height), 0)
        ImageDraw.Draw(temporary).polygon(polygon_pixels, fill=1, outline=1)
        polygon_mask = np.array(temporary, dtype=bool)
        if xor_mode:
            composite ^= polygon_mask
        else:
            composite |= polygon_mask

    return composite


def paste_mask_on_grid(base_image: Image.Image, mask: np.ndarray, spec: CanvasSpec) -> None:
    mask_image = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8), mode="L")
    fill_layer = Image.new("RGB", mask_image.size, FILL_COLOR)
    base_image.paste(fill_layer, (spec.origin_x, spec.origin_y), mask_image)


def draw_shape_vertex_labels(
    image: Image.Image, shape_vertices: dict[str, list[int]], spec: CanvasSpec
) -> None:
    draw = ImageDraw.Draw(image)
    for vertex_id, point in sort_vertex_items(shape_vertices):
        pixel_x = spec.origin_x + point[0] * spec.cell_size
        pixel_y = spec.origin_y + (spec.grid_extent - point[1]) * spec.cell_size
        radius = 4
        draw.ellipse(
            [(pixel_x - radius, pixel_y - radius), (pixel_x + radius, pixel_y + radius)],
            fill=BACKGROUND_COLOR,
            outline=AXIS_COLOR,
            width=1,
        )
        draw.text((pixel_x + 8, pixel_y - 16), vertex_id, fill=AXIS_COLOR, font=FONT_SMALL)


def render_target_image(level_data: dict, output_path: Path) -> None:
    spec = build_target_spec(level_data["gridSize"])
    image = Image.new("RGB", (spec.width, spec.height), BACKGROUND_COLOR)
    draw_grid_base(image, spec, title="Target")
    mask = rasterize_polygon_mask(
        [item["polygon"] for item in level_data["target"]],
        spec,
        xor_mode=True,
    )
    paste_mask_on_grid(image, mask, spec)
    image.save(output_path, format="PNG")


def render_shape_image(shape_id: str, shape_vertices: dict[str, list[int]], output_path: Path) -> None:
    spec = build_shape_spec(shape_vertices)
    image = Image.new("RGB", (spec.width, spec.height), BACKGROUND_COLOR)
    draw_grid_base(image, spec, title=shape_id)
    mask = rasterize_polygon_mask(
        [[point for _, point in sort_vertex_items(shape_vertices)]],
        spec,
        xor_mode=False,
    )
    paste_mask_on_grid(image, mask, spec)
    draw_shape_vertex_labels(image, shape_vertices, spec)
    image.save(output_path, format="PNG")


def relative_asset_path(level_json_path: Path, asset_path: Path) -> str:
    return Path("..").joinpath(asset_path.relative_to(asset_path.parents[1])).as_posix()


def build_image_asset_payload(level_dir_name: str, shape_ids: list[str]) -> dict:
    shape_paths = {
        shape_id: f"../images/{level_dir_name}/{SHAPE_IMAGE_PREFIX}{shape_id}.png"
        for shape_id in shape_ids
    }
    return {
        "target": f"../images/{level_dir_name}/{TARGET_IMAGE_NAME}",
        "shapes": shape_paths,
    }


def render_level_images(level_json_path: Path, images_root: Path) -> None:
    level_data = json.loads(level_json_path.read_text(encoding="utf-8"))
    level_id = level_json_path.stem
    level_image_dir = images_root / level_id
    level_image_dir.mkdir(parents=True, exist_ok=True)

    for stale_png in level_image_dir.glob("*.png"):
        stale_png.unlink()

    render_target_image(level_data, level_image_dir / TARGET_IMAGE_NAME)

    for shape_id, shape_vertices in level_data["inventory"].items():
        render_shape_image(
            shape_id,
            shape_vertices,
            level_image_dir / f"{SHAPE_IMAGE_PREFIX}{shape_id}.png",
        )

    level_data[IMAGE_ASSET_FIELD] = build_image_asset_payload(
        level_id,
        list(level_data["inventory"].keys()),
    )
    level_json_path.write_text(
        json.dumps(level_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    levels_dir = args.levels_dir
    images_dir = args.images_dir
    images_dir.mkdir(parents=True, exist_ok=True)

    level_paths = sorted(levels_dir.glob("level*.json"))
    if not level_paths:
        raise SystemExit(f"No level JSON files found in {levels_dir}")

    for level_json_path in level_paths:
        render_level_images(level_json_path, images_dir)
        print(f"Rendered images for {level_json_path.stem}")

    print(f"Generated image assets for {len(level_paths)} levels in {images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
