from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_RASTER_SCALE = 16
SUPPORTED_ANGLES = (0, 90, 180, 270)
EPSILON = 1e-9
COMMAND_SEARCH_PATTERN = re.compile(
    r"([A-Za-z][\w-]*)\s+(0|90|180|270)\s+(V\d+)\s+\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]"
)

PixelSet = set[tuple[int, int]]
Point = tuple[int, int]


@dataclass(frozen=True)
class ParsedCommand:
    shape_id: str
    angle: int
    vertex_id: str
    target_grid_x: int
    target_grid_y: int
    source_line_number: int
    source_line_text: str

    @property
    def target_grid(self) -> Point:
        return (self.target_grid_x, self.target_grid_y)

    def as_dict(self) -> dict[str, Any]:
        return {
            "shapeId": self.shape_id,
            "angle": self.angle,
            "vertexId": self.vertex_id,
            "targetGrid": [self.target_grid_x, self.target_grid_y],
            "sourceLineNumber": self.source_line_number,
            "sourceLineText": self.source_line_text,
        }


def rotate_point(point: Point, angle: int) -> Point:
    x, y = point
    if angle == 0:
        return (x, y)
    if angle == 90:
        return (y, -x)
    if angle == 180:
        return (-x, -y)
    if angle == 270:
        return (-y, x)
    raise ValueError(f"Unsupported angle: {angle}")


def calculate_transformed_vertices(
    shape_data: dict[str, list[int]],
    angle: int,
    vertex_id: str,
    target_grid: Point,
) -> list[tuple[str, Point]]:
    rotated_vertices = [
        (vertex_name, rotate_point((point[0], point[1]), angle))
        for vertex_name, point in sorted(shape_data.items(), key=lambda item: int(item[0][1:]))
    ]

    anchor = next((name, point) for name, point in rotated_vertices if name == vertex_id)
    translate_x = target_grid[0] - anchor[1][0]
    translate_y = target_grid[1] - anchor[1][1]

    return [
        (name, (point[0] + translate_x, point[1] + translate_y))
        for name, point in rotated_vertices
    ]


def rasterize_polygon(
    polygon: list[Point],
    grid_size: int,
    raster_scale: int,
) -> PixelSet:
    canvas_size = grid_size * raster_scale
    filled_pixels: PixelSet = set()

    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    min_x = max(0, int(math.floor(min(xs) * raster_scale)))
    max_x = min(canvas_size, int(math.ceil(max(xs) * raster_scale)))
    min_y = max(0, int(math.floor(min(ys) * raster_scale)))
    max_y = min(canvas_size, int(math.ceil(max(ys) * raster_scale)))

    if min_x >= max_x or min_y >= max_y:
        return filled_pixels

    edges = list(zip(polygon, polygon[1:] + polygon[:1]))

    for pixel_y in range(min_y, max_y):
        sample_y = (pixel_y + 0.5) / raster_scale
        for pixel_x in range(min_x, max_x):
            sample_x = (pixel_x + 0.5) / raster_scale
            inside = False
            on_boundary = False

            for start, end in edges:
                x1, y1 = start
                x2, y2 = end

                if y1 != y2:
                    intersects = ((y1 > sample_y) != (y2 > sample_y)) and (
                        sample_x < ((x2 - x1) * (sample_y - y1) / (y2 - y1)) + x1
                    )
                    if intersects:
                        inside = not inside

                cross = (sample_x - x1) * (y2 - y1) - (sample_y - y1) * (x2 - x1)
                within_x = min(x1, x2) - EPSILON <= sample_x <= max(x1, x2) + EPSILON
                within_y = min(y1, y2) - EPSILON <= sample_y <= max(y1, y2) + EPSILON
                if abs(cross) <= EPSILON and within_x and within_y:
                    on_boundary = True

            if inside or on_boundary:
                filled_pixels.add((pixel_x, pixel_y))

    return filled_pixels


def xor_pixel_sets(pixel_sets: list[PixelSet]) -> PixelSet:
    result: PixelSet = set()
    for pixel_set in pixel_sets:
        result.symmetric_difference_update(pixel_set)
    return result


def build_mask_from_target_polygons(
    target_polygons: list[dict[str, Any]],
    grid_size: int,
    raster_scale: int,
) -> PixelSet:
    masks = [
        rasterize_polygon(
            [(point[0], point[1]) for point in polygon_item["polygon"]],
            grid_size,
            raster_scale,
        )
        for polygon_item in target_polygons
    ]
    return xor_pixel_sets(masks)


def parse_solution_text(solution_text: str) -> list[tuple[str, int, str, Point]]:
    steps = []
    for raw_line in solution_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        shape_id, angle_text, vertex_id, grid_text = line.split()
        grid_x_text, grid_y_text = grid_text.strip("[]").split(",")
        steps.append(
            (shape_id, int(angle_text), vertex_id, (int(grid_x_text), int(grid_y_text)))
        )
    return steps


def replay_solution_mask(level_data: dict[str, Any], raster_scale: int) -> PixelSet:
    masks: list[PixelSet] = []
    for shape_id, angle, vertex_id, target_grid in parse_solution_text(level_data["solutionText"]):
        transformed_vertices = calculate_transformed_vertices(
            level_data["inventory"][shape_id],
            angle,
            vertex_id,
            target_grid,
        )
        masks.append(
            rasterize_polygon(
                [point for _, point in transformed_vertices],
                level_data["gridSize"],
                raster_scale,
            )
        )
    return xor_pixel_sets(masks)


def _normalize_line_for_search(raw_line: str) -> str:
    candidate = raw_line.strip().strip("`")
    candidate = re.sub(r"^\s*(?:[-*]\s+|\d+[.)]\s+)", "", candidate)
    return candidate


def parse_model_output(
    level_data: dict[str, Any],
    model_output: str,
) -> tuple[list[ParsedCommand], list[str], list[str], int]:
    parsed_commands: list[ParsedCommand] = []
    ignored_lines: list[str] = []
    errors: list[str] = []
    used_shapes: set[str] = set()
    structured_operation_count = 0

    for line_number, raw_line in enumerate(model_output.splitlines(), start=1):
        if not raw_line.strip():
            continue
        if raw_line.strip().startswith("```"):
            continue

        candidate = _normalize_line_for_search(raw_line)
        if not candidate:
            continue

        match = COMMAND_SEARCH_PATTERN.search(candidate)
        if not match:
            ignored_lines.append(raw_line.rstrip())
            continue

        structured_operation_count += 1
        shape_id, angle_text, vertex_id, grid_x_text, grid_y_text = match.groups()
        if shape_id not in level_data["inventory"]:
            errors.append(f"Line {line_number} references unknown shape: {shape_id}")
            continue
        if vertex_id not in level_data["inventory"][shape_id]:
            errors.append(
                f"Line {line_number} references unknown vertex {vertex_id} in {shape_id}"
            )
            continue
        if shape_id in used_shapes:
            errors.append(f"Shape {shape_id} is reused and can only be used once")
            continue

        used_shapes.add(shape_id)
        parsed_commands.append(
            ParsedCommand(
                shape_id=shape_id,
                angle=int(angle_text),
                vertex_id=vertex_id,
                target_grid_x=int(grid_x_text),
                target_grid_y=int(grid_y_text),
                source_line_number=line_number,
                source_line_text=raw_line.rstrip(),
            )
        )

    if structured_operation_count == 0:
        errors.append("No valid operation-code lines were found in the model output")

    return parsed_commands, ignored_lines, errors, structured_operation_count


def build_prediction_mask(
    level_data: dict[str, Any],
    parsed_commands: list[ParsedCommand],
    raster_scale: int,
) -> PixelSet:
    masks: list[PixelSet] = []
    for command in parsed_commands:
        transformed_vertices = calculate_transformed_vertices(
            level_data["inventory"][command.shape_id],
            command.angle,
            command.vertex_id,
            command.target_grid,
        )
        masks.append(
            rasterize_polygon(
                [point for _, point in transformed_vertices],
                level_data["gridSize"],
                raster_scale,
            )
        )
    return xor_pixel_sets(masks)


def _compute_overlap_metrics(
    predicted_mask: PixelSet,
    target_mask: PixelSet,
    total_pixels: int,
) -> dict[str, Any]:
    intersection = len(predicted_mask & target_mask)
    union = len(predicted_mask | target_mask)
    predicted_pixels = len(predicted_mask)
    target_pixels = len(target_mask)
    exact_match = predicted_mask == target_mask

    iou = 1.0 if union == 0 else intersection / union
    denominator = predicted_pixels + target_pixels
    dice = 1.0 if denominator == 0 else (2 * intersection) / denominator
    precision = intersection / predicted_pixels if predicted_pixels > 0 else 0.0
    recall = intersection / target_pixels if target_pixels > 0 else 0.0
    pixel_accuracy = (
        (total_pixels - len(predicted_mask ^ target_mask)) / total_pixels if total_pixels else 1.0
    )

    return {
        "is_pattern_matched": exact_match,
        "pattern_iou": round(iou, 6),
        "overlap_ratio": round(iou, 6),
        "dice_score": round(dice, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "pixel_accuracy": round(pixel_accuracy, 6),
        "intersection_pixels": intersection,
        "union_pixels": union,
        "predicted_pixels": predicted_pixels,
        "target_pixels": target_pixels,
    }


def _maybe_finaljson_to_dsl(model_output: str) -> str:
    """If `model_output` ends with a `FINAL_JSON: {"placements": [...]}` line,
    convert that JSON's placements list to the legacy text DSL the regex parser
    expects, and append it to the original output. Returns the original text on
    any failure so non-JSON outputs flow through unchanged."""
    if "FINAL_JSON:" not in model_output:
        return model_output

    marker_index = model_output.rfind("FINAL_JSON:")
    after_marker = model_output[marker_index + len("FINAL_JSON:"):]
    object_start = after_marker.find("{")
    if object_start == -1:
        return model_output

    depth = 0
    in_string = False
    is_escaped = False
    json_end = -1
    for index in range(object_start, len(after_marker)):
        char = after_marker[index]
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
                json_end = index + 1
                break
    if json_end == -1:
        return model_output

    candidate = after_marker[object_start:json_end]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return model_output

    placements = payload.get("placements") if isinstance(payload, dict) else None
    if not isinstance(placements, list) or not placements:
        return model_output

    dsl_lines: list[str] = []
    for item in placements:
        if not isinstance(item, dict):
            continue
        try:
            shape = str(item["shape"])
            angle = int(item["angle"])
            vertex = str(item["vertex"])
            grid = item["grid"]
            grid_x, grid_y = int(grid[0]), int(grid[1])
        except (KeyError, ValueError, TypeError):
            continue
        dsl_lines.append(f"{shape} {angle} {vertex} [{grid_x},{grid_y}]")
    if not dsl_lines:
        return model_output

    return model_output + "\n" + "\n".join(dsl_lines)


def evaluate_with_project_engine(
    level_json_path: str | Path,
    model_output: str,
) -> dict[str, Any]:
    level_path = Path(level_json_path)
    level_data = json.loads(level_path.read_text(encoding="utf-8"))
    raster_scale = int(level_data.get("meta", {}).get("rasterScale", DEFAULT_RASTER_SCALE))
    total_pixels = (level_data["gridSize"] * raster_scale) ** 2

    target_mask = build_mask_from_target_polygons(
        level_data["target"],
        level_data["gridSize"],
        raster_scale,
    )
    reference_mask = replay_solution_mask(level_data, raster_scale)
    # SimVerse v1: if the model emits FINAL_JSON, splice an equivalent DSL block
    # onto the output so the regex parser still finds placements.
    augmented_output = _maybe_finaljson_to_dsl(model_output)
    parsed_commands, ignored_lines, errors, structured_operation_count = parse_model_output(
        level_data, augmented_output
    )

    if parsed_commands:
        predicted_mask = build_prediction_mask(level_data, parsed_commands, raster_scale)
    else:
        predicted_mask = set()
    overlap_metrics = _compute_overlap_metrics(predicted_mask, target_mask, total_pixels)

    if structured_operation_count == 0:
        evaluation_status = "invalid_output"
    elif errors:
        evaluation_status = "mismatched"
    else:
        evaluation_status = "matched" if overlap_metrics["is_pattern_matched"] else "mismatched"

    reference_metrics = _compute_overlap_metrics(predicted_mask, reference_mask, total_pixels)
    reference_steps = parse_solution_text(level_data["solutionText"])
    normalized_instruction_text = "\n".join(
        f"{command.shape_id} {command.angle} {command.vertex_id} "
        f"[{command.target_grid_x},{command.target_grid_y}]"
        for command in parsed_commands
    ).strip()

    return {
        "evaluation_status": evaluation_status,
        "is_fully_cleared": overlap_metrics["is_pattern_matched"],
        "is_pattern_matched": overlap_metrics["is_pattern_matched"],
        "pattern_iou": overlap_metrics["pattern_iou"],
        "overlap_ratio": overlap_metrics["overlap_ratio"],
        "dice_score": overlap_metrics["dice_score"],
        "precision": overlap_metrics["precision"],
        "recall": overlap_metrics["recall"],
        "pixel_accuracy": overlap_metrics["pixel_accuracy"],
        "intersection_pixels": overlap_metrics["intersection_pixels"],
        "union_pixels": overlap_metrics["union_pixels"],
        "predicted_pixels": overlap_metrics["predicted_pixels"],
        "target_pixels": overlap_metrics["target_pixels"],
        "reference_iou": reference_metrics["pattern_iou"],
        "reference_dice_score": reference_metrics["dice_score"],
        "raster_scale": raster_scale,
        "parsed_operation_count": len(parsed_commands),
        "structured_operation_count": structured_operation_count,
        "required_operation_count": int(level_data.get("meta", {}).get("requiredShapeCount", 0)),
        "ignored_text_lines": ignored_lines,
        "ignored_text_line_count": len(ignored_lines),
        "validation_errors": errors,
        "parsed_operations": [command.as_dict() for command in parsed_commands],
        "reference_solution_text": level_data["solutionText"],
        "reference_solution_operation_count": len(reference_steps),
        "exact_instruction_match": normalized_instruction_text == level_data["solutionText"].strip(),
    }
