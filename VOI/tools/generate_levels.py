#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


GENERATOR_VERSION = "1.0.0"
DEFAULT_RASTER_SCALE = 16
SUPPORTED_ANGLES = (0, 90, 180, 270)

Point = tuple[int, int]


@dataclass(frozen=True)
class ShapeTemplate:
    template_id: str
    complexity: str
    vertices: tuple[Point, ...]

    def inventory_shape(self) -> dict[str, list[int]]:
        return {
            f"V{index + 1}": [point[0], point[1]]
            for index, point in enumerate(self.vertices)
        }


@dataclass(frozen=True)
class LevelConfig:
    level_index: int
    name: str
    grid_size: int
    required_shape_count: int
    shape_pool_complexity: str
    overlap_allowed: bool
    distractor_shape_count: int
    max_components: int
    overlap_ratio_range: tuple[float, float] | None = None
    fill_ratio_range: tuple[float, float] = (0.10, 0.60)
    max_attempts: int = 2000
    accepted_candidates_goal: int = 10


@dataclass(frozen=True)
class DifficultyTier:
    tier_id: int
    label: str
    count: int
    config: LevelConfig


@dataclass
class Placement:
    template: ShapeTemplate
    angle: int
    anchor_vertex_id: str
    target_grid: Point
    vertices: tuple[tuple[str, Point], ...]
    mask: np.ndarray

    @property
    def polygon(self) -> list[list[int]]:
        return [[point[0], point[1]] for _, point in self.vertices]

    @property
    def area(self) -> int:
        return int(np.count_nonzero(self.mask))


@dataclass
class InventoryEntry:
    template: ShapeTemplate
    shape_id: str = ""
    placement: Placement | None = None

    @property
    def is_required(self) -> bool:
        return self.placement is not None


@dataclass
class Candidate:
    config: LevelConfig
    seed: int
    inventory_entries: list[InventoryEntry]
    target_mask: np.ndarray
    overlap_ratio: float
    contour_complexity: int
    connected_components: int
    fill_ratio: float
    quality_score: float

    @property
    def required_entries(self) -> list[InventoryEntry]:
        return [entry for entry in self.inventory_entries if entry.is_required]


SHAPE_LIBRARY: tuple[ShapeTemplate, ...] = (
    ShapeTemplate("sq1", "low", ((0, 0), (1, 0), (1, 1), (0, 1))),
    ShapeTemplate("rect2", "low", ((0, 0), (2, 0), (2, 1), (0, 1))),
    ShapeTemplate("rect1x2", "low", ((0, 0), (1, 0), (1, 2), (0, 2))),
    ShapeTemplate("sq2", "low", ((0, 0), (2, 0), (2, 2), (0, 2))),
    ShapeTemplate("tri1", "low", ((0, 0), (1, 0), (0, 1))),
    ShapeTemplate("tri2", "low", ((0, 0), (2, 0), (0, 2))),
    ShapeTemplate("rect3", "medium", ((0, 0), (3, 0), (3, 1), (0, 1))),
    ShapeTemplate("rect1x3", "medium", ((0, 0), (1, 0), (1, 3), (0, 3))),
    ShapeTemplate("rect2x3", "medium", ((0, 0), (3, 0), (3, 2), (0, 2))),
    ShapeTemplate("l3", "medium", ((0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3))),
    ShapeTemplate("trap1", "medium", ((0, 0), (3, 0), (2, 1), (0, 1))),
)


COMPLEXITY_ORDER = {"low": 0, "medium": 1, "high": 1}


CAMPAIGN_CONFIGS: tuple[LevelConfig, ...] = (
    LevelConfig(1, "Level 1", 6, 2, "low", False, 0, 1),
    LevelConfig(2, "Level 2", 6, 3, "low", False, 1, 1),
    LevelConfig(3, "Level 3", 8, 3, "medium", True, 1, 1, (0.08, 0.18)),
    LevelConfig(4, "Level 4", 8, 4, "medium", True, 2, 2, (0.15, 0.28)),
    LevelConfig(5, "Level 5", 10, 4, "medium", True, 2, 2, (0.22, 0.35)),
)


CATALOG_500_TIERS: tuple[DifficultyTier, ...] = (
    DifficultyTier(1, "基础 1", 50, LevelConfig(1, "Tier 1", 6, 2, "low", True, 0, 1, (0.05, 0.25), (0.09, 0.42), 800, 3)),
    DifficultyTier(2, "基础 2", 50, LevelConfig(2, "Tier 2", 6, 3, "low", True, 1, 1, (0.08, 0.30), (0.10, 0.45), 900, 3)),
    DifficultyTier(3, "进阶 1", 100, LevelConfig(3, "Tier 3", 8, 3, "medium", True, 1, 1, (0.10, 0.35), (0.10, 0.45), 1200, 2)),
    DifficultyTier(4, "进阶 2", 100, LevelConfig(4, "Tier 4", 8, 3, "medium", True, 2, 1, (0.12, 0.38), (0.10, 0.45), 1200, 2)),
    DifficultyTier(5, "挑战 1", 75, LevelConfig(5, "Tier 5", 8, 4, "medium", True, 2, 1, (0.15, 0.40), (0.10, 0.45), 1500, 2)),
    DifficultyTier(6, "挑战 2", 75, LevelConfig(6, "Tier 6", 10, 4, "medium", True, 2, 2, (0.18, 0.42), (0.10, 0.42), 1800, 2)),
    DifficultyTier(7, "专家 1", 50, LevelConfig(7, "Tier 7", 10, 4, "medium", True, 3, 2, (0.22, 0.45), (0.10, 0.40), 2200, 2)),
)

CATALOG_724_EXTENSION_COUNTS: tuple[int, ...] = (22, 22, 45, 45, 34, 34, 22)
CATALOG_724_EXTENSION_TIERS: tuple[DifficultyTier, ...] = tuple(
    DifficultyTier(base_tier.tier_id, base_tier.label, extension_count, base_tier.config)
    for base_tier, extension_count in zip(
        CATALOG_500_TIERS,
        CATALOG_724_EXTENSION_COUNTS,
        strict=True,
    )
)
CATALOG_724_TOTAL_TIERS: tuple[DifficultyTier, ...] = tuple(
    DifficultyTier(base_tier.tier_id, base_tier.label, base_tier.count + extension_count, base_tier.config)
    for base_tier, extension_count in zip(
        CATALOG_500_TIERS,
        CATALOG_724_EXTENSION_COUNTS,
        strict=True,
    )
)


PLACEMENT_SIGNATURE_CACHE: dict[tuple[tuple[Point, ...], int, int], tuple[int, ...]] = {}


def get_shape_pool(complexity: str) -> list[ShapeTemplate]:
    limit = COMPLEXITY_ORDER[complexity]
    return [
        shape
        for shape in SHAPE_LIBRARY
        if COMPLEXITY_ORDER[shape.complexity] <= limit
    ]


def rotate_point(point: Point, angle: int) -> Point:
    x, y = point
    if angle == 0:
        return x, y
    if angle == 90:
        return y, -x
    if angle == 180:
        return -x, -y
    if angle == 270:
        return -y, x
    raise ValueError(f"Unsupported angle: {angle}")


def rotate_labeled_vertices(
    template: ShapeTemplate,
    angle: int,
) -> tuple[tuple[str, Point], ...]:
    return tuple(
        (f"V{index + 1}", rotate_point(point, angle))
        for index, point in enumerate(template.vertices)
    )


def translation_bounds(points: Iterable[Point], grid_size: int) -> tuple[range, range]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_range = range(-min_x, grid_size - max_x + 1)
    y_range = range(-min_y, grid_size - max_y + 1)
    return x_range, y_range


def translate_labeled_vertices(
    labeled_vertices: tuple[tuple[str, Point], ...],
    translate_x: int,
    translate_y: int,
) -> tuple[tuple[str, Point], ...]:
    return tuple(
        (vertex_id, (point[0] + translate_x, point[1] + translate_y))
        for vertex_id, point in labeled_vertices
    )


def rasterize_polygon(
    polygon: Iterable[Point],
    grid_size: int,
    raster_scale: int,
) -> np.ndarray:
    polygon_points = list(polygon)
    canvas_size = grid_size * raster_scale
    mask = np.zeros((canvas_size, canvas_size), dtype=bool)

    xs = [point[0] for point in polygon_points]
    ys = [point[1] for point in polygon_points]
    min_x = max(0, int(math.floor(min(xs) * raster_scale)))
    max_x = min(canvas_size, int(math.ceil(max(xs) * raster_scale)))
    min_y = max(0, int(math.floor(min(ys) * raster_scale)))
    max_y = min(canvas_size, int(math.ceil(max(ys) * raster_scale)))

    if min_x >= max_x or min_y >= max_y:
        return mask

    sample_x = (np.arange(min_x, max_x, dtype=np.float64) + 0.5) / raster_scale
    sample_y = (np.arange(min_y, max_y, dtype=np.float64) + 0.5) / raster_scale
    grid_x, grid_y = np.meshgrid(sample_x, sample_y)
    inside = np.zeros(grid_x.shape, dtype=bool)
    on_boundary = np.zeros(grid_x.shape, dtype=bool)
    epsilon = 1e-9

    loop_points = polygon_points[1:] + polygon_points[:1]
    for start, end in zip(polygon_points, loop_points):
        x1, y1 = start
        x2, y2 = end
        if y1 != y2:
            intersects = ((y1 > grid_y) != (y2 > grid_y)) & (
                grid_x < ((x2 - x1) * (grid_y - y1) / (y2 - y1)) + x1
            )
            inside ^= intersects

        cross = (grid_x - x1) * (y2 - y1) - (grid_y - y1) * (x2 - x1)
        within_x = (np.minimum(x1, x2) - epsilon <= grid_x) & (
            grid_x <= np.maximum(x1, x2) + epsilon
        )
        within_y = (np.minimum(y1, y2) - epsilon <= grid_y) & (
            grid_y <= np.maximum(y1, y2) + epsilon
        )
        on_boundary |= (np.abs(cross) <= epsilon) & within_x & within_y

    mask[min_y:max_y, min_x:max_x] = inside | on_boundary
    return mask


def xor_masks(masks: Iterable[np.ndarray]) -> np.ndarray:
    iterator = iter(masks)
    try:
        result = next(iterator).copy()
    except StopIteration as exc:
        raise ValueError("At least one mask is required for XOR.") from exc

    for mask in iterator:
        np.logical_xor(result, mask, out=result)
    return result


def mask_signature(mask: np.ndarray) -> int:
    packed = np.packbits(mask.reshape(-1), bitorder="big")
    return int.from_bytes(packed.tobytes(), "big")


def count_connected_components(mask: np.ndarray) -> int:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    component_count = 0

    for start_y, start_x in np.argwhere(mask):
        if visited[start_y, start_x]:
            continue

        component_count += 1
        queue = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True

        while queue:
            y, x = queue.popleft()
            for delta_y, delta_x in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                next_y = y + delta_y
                next_x = x + delta_x
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and mask[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))

    return component_count


def choose_continuation(
    current_point: tuple[int, int],
    candidates: list[tuple[int, int]],
    previous_direction: tuple[int, int],
) -> tuple[int, int]:
    priorities = []
    for candidate in candidates:
        direction = (candidate[0] - current_point[0], candidate[1] - current_point[1])
        turn_score = 0 if direction == previous_direction else 1
        priorities.append((turn_score, direction[1], direction[0], candidate))
    priorities.sort()
    return priorities[0][3]


def extract_boundary_loops(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    height, width = mask.shape
    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

    for y in range(height):
        for x in range(width):
            if not mask[y, x]:
                continue
            if y == 0 or not mask[y - 1, x]:
                adjacency[(x, y)].append((x + 1, y))
            if x == width - 1 or not mask[y, x + 1]:
                adjacency[(x + 1, y)].append((x + 1, y + 1))
            if y == height - 1 or not mask[y + 1, x]:
                adjacency[(x + 1, y + 1)].append((x, y + 1))
            if x == 0 or not mask[y, x - 1]:
                adjacency[(x, y + 1)].append((x, y))

    edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = defaultdict(int)
    for start, next_points in adjacency.items():
        for end in next_points:
            edge_counts[(start, end)] += 1

    loops: list[list[tuple[int, int]]] = []
    for start, end in list(edge_counts):
        if edge_counts[(start, end)] == 0:
            continue

        loop = [start]
        current_start = start
        current_end = end

        while True:
            edge_counts[(current_start, current_end)] -= 1
            loop.append(current_end)
            if current_end == start:
                break

            next_candidates = [
                candidate
                for candidate in adjacency[current_end]
                if edge_counts[(current_end, candidate)] > 0
            ]
            if not next_candidates:
                break

            if len(next_candidates) == 1:
                next_point = next_candidates[0]
            else:
                previous_direction = (
                    current_end[0] - current_start[0],
                    current_end[1] - current_start[1],
                )
                next_point = choose_continuation(
                    current_end,
                    next_candidates,
                    previous_direction,
                )
            current_start, current_end = current_end, next_point

        if len(loop) > 2 and loop[0] == loop[-1]:
            loops.append(loop)

    return loops


def simplify_loop(loop: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(loop) <= 3:
        return loop

    simplified = [loop[0]]
    for index in range(1, len(loop) - 1):
        previous_point = simplified[-1]
        current_point = loop[index]
        next_point = loop[index + 1]
        vector_a = (
            current_point[0] - previous_point[0],
            current_point[1] - previous_point[1],
        )
        vector_b = (
            next_point[0] - current_point[0],
            next_point[1] - current_point[1],
        )
        if vector_a[0] * vector_b[1] == vector_a[1] * vector_b[0]:
            continue
        simplified.append(current_point)

    simplified.append(loop[-1])
    return simplified


def contour_complexity(mask: np.ndarray) -> int:
    return sum(max(0, len(simplify_loop(loop)) - 1) for loop in extract_boundary_loops(mask))


def compute_overlap_ratio(individual_area_sum: int, final_area: int) -> float:
    if individual_area_sum == 0:
        return 0.0
    return (individual_area_sum - final_area) / individual_area_sum


def candidate_score(
    config: LevelConfig,
    overlap_ratio: float,
    fill_ratio: float,
    components: int,
) -> float:
    score = abs(fill_ratio - 0.30) * 2.0 + max(0, components - 1) * 0.25
    if config.overlap_ratio_range is None:
        score += overlap_ratio
    else:
        lower, upper = config.overlap_ratio_range
        midpoint = (lower + upper) / 2
        score += abs(overlap_ratio - midpoint) * 4.0
    return score


def sample_placement(
    template: ShapeTemplate,
    grid_size: int,
    raster_scale: int,
    rng: random.Random,
) -> Placement | None:
    angle = rng.choice(SUPPORTED_ANGLES)
    rotated = rotate_labeled_vertices(template, angle)
    translated_range_x, translated_range_y = translation_bounds(
        [point for _, point in rotated],
        grid_size,
    )
    range_x = list(translated_range_x)
    range_y = list(translated_range_y)
    if not range_x or not range_y:
        return None

    translate_x = rng.choice(range_x)
    translate_y = rng.choice(range_y)
    translated = translate_labeled_vertices(rotated, translate_x, translate_y)
    anchor_vertex_id, anchor_position = rng.choice(list(translated))
    mask = rasterize_polygon(
        [point for _, point in translated],
        grid_size,
        raster_scale,
    )
    return Placement(
        template=template,
        angle=angle,
        anchor_vertex_id=anchor_vertex_id,
        target_grid=anchor_position,
        vertices=translated,
        mask=mask,
    )


def enumerate_shape_placement_signatures(
    template: ShapeTemplate,
    grid_size: int,
    raster_scale: int,
) -> tuple[int, ...]:
    cache_key = (template.vertices, grid_size, raster_scale)
    if cache_key in PLACEMENT_SIGNATURE_CACHE:
        return PLACEMENT_SIGNATURE_CACHE[cache_key]

    signatures: set[int] = set()
    for angle in SUPPORTED_ANGLES:
        rotated = rotate_labeled_vertices(template, angle)
        translated_range_x, translated_range_y = translation_bounds(
            [point for _, point in rotated],
            grid_size,
        )
        for translate_x in translated_range_x:
            for translate_y in translated_range_y:
                translated = translate_labeled_vertices(rotated, translate_x, translate_y)
                mask = rasterize_polygon(
                    [point for _, point in translated],
                    grid_size,
                    raster_scale,
                )
                signatures.add(mask_signature(mask))

    cached = tuple(sorted(signatures))
    PLACEMENT_SIGNATURE_CACHE[cache_key] = cached
    return cached


def has_solution_with_fewer_shapes(
    target_signature: int,
    placement_signatures: list[tuple[int, ...]],
    required_shape_count: int,
) -> bool:
    if required_shape_count <= 1:
        return False

    if any(target_signature in signatures for signatures in placement_signatures):
        return True

    if required_shape_count <= 2:
        return False

    per_shape_sets = [set(signatures) for signatures in placement_signatures]
    inventory_indices = range(len(placement_signatures))

    for left_index in inventory_indices:
        for right_index in range(left_index + 1, len(placement_signatures)):
            right_set = per_shape_sets[right_index]
            for left_signature in placement_signatures[left_index]:
                if (target_signature ^ left_signature) in right_set:
                    return True

    if required_shape_count <= 3:
        return False

    pair_signature_map: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for left_index in inventory_indices:
        for right_index in range(left_index + 1, len(placement_signatures)):
            for left_signature in placement_signatures[left_index]:
                for right_signature in placement_signatures[right_index]:
                    pair_signature_map[left_signature ^ right_signature].append(
                        (left_index, right_index)
                    )

    for third_index in inventory_indices:
        for third_signature in placement_signatures[third_index]:
            needed_signature = target_signature ^ third_signature
            for left_index, right_index in pair_signature_map.get(needed_signature, []):
                if third_index not in (left_index, right_index):
                    return True

    return False


def build_candidate(
    config: LevelConfig,
    level_seed: int,
    raster_scale: int,
    rng: random.Random,
) -> Candidate | None:
    shape_pool = get_shape_pool(config.shape_pool_complexity)
    canvas_size = config.grid_size * raster_scale
    target_mask = np.zeros((canvas_size, canvas_size), dtype=bool)
    required_entries: list[InventoryEntry] = []
    individual_area_sum = 0

    for _ in range(config.required_shape_count):
        accepted_placement: Placement | None = None
        for _ in range(180):
            template = rng.choice(shape_pool)
            placement = sample_placement(template, config.grid_size, raster_scale, rng)
            if placement is None:
                continue
            if not config.overlap_allowed and np.any(target_mask & placement.mask):
                continue
            accepted_placement = placement
            break

        if accepted_placement is None:
            return None

        required_entries.append(
            InventoryEntry(template=accepted_placement.template, placement=accepted_placement)
        )
        np.logical_xor(target_mask, accepted_placement.mask, out=target_mask)
        individual_area_sum += accepted_placement.area

    final_area = int(np.count_nonzero(target_mask))
    if final_area == 0:
        return None

    lower_fill, upper_fill = config.fill_ratio_range
    fill_ratio = final_area / target_mask.size
    if not (lower_fill <= fill_ratio <= upper_fill):
        return None

    connected_components = count_connected_components(target_mask)
    if connected_components > config.max_components:
        return None

    shape_complexity = contour_complexity(target_mask)
    if shape_complexity < 4:
        return None

    overlap_ratio = compute_overlap_ratio(individual_area_sum, final_area)
    if config.overlap_ratio_range is not None:
        lower_overlap, upper_overlap = config.overlap_ratio_range
        if not (lower_overlap <= overlap_ratio <= upper_overlap):
            return None

    distractor_entries = [
        InventoryEntry(template=rng.choice(shape_pool))
        for _ in range(config.distractor_shape_count)
    ]
    inventory_entries = required_entries + distractor_entries
    rng.shuffle(inventory_entries)

    for index, entry in enumerate(inventory_entries, start=1):
        entry.shape_id = f"S{index}"

    placement_signatures = [
        enumerate_shape_placement_signatures(entry.template, config.grid_size, raster_scale)
        for entry in inventory_entries
    ]
    if has_solution_with_fewer_shapes(
        mask_signature(target_mask),
        placement_signatures,
        config.required_shape_count,
    ):
        return None

    return Candidate(
        config=config,
        seed=level_seed,
        inventory_entries=inventory_entries,
        target_mask=target_mask,
        overlap_ratio=overlap_ratio,
        contour_complexity=shape_complexity,
        connected_components=connected_components,
        fill_ratio=fill_ratio,
        quality_score=candidate_score(
            config,
            overlap_ratio,
            fill_ratio,
            connected_components,
        ),
    )


def candidate_to_level_payload(
    candidate: Candidate,
    raster_scale: int,
    level_name: str | None = None,
    extra_meta: dict | None = None,
) -> dict:
    inventory = {
        entry.shape_id: entry.template.inventory_shape()
        for entry in candidate.inventory_entries
    }

    solution_lines = []
    target_polygons = []
    for entry in candidate.required_entries:
        assert entry.placement is not None
        solution_lines.append(
            f"{entry.shape_id} {entry.placement.angle} {entry.placement.anchor_vertex_id} "
            f"[{entry.placement.target_grid[0]},{entry.placement.target_grid[1]}]"
        )
        target_polygons.append({"polygon": entry.placement.polygon})

    payload = {
        "name": level_name or candidate.config.name,
        "gridSize": candidate.config.grid_size,
        "inventory": inventory,
        "target": target_polygons,
        "solutionText": "\n".join(solution_lines),
        "meta": {
            "generatorVersion": GENERATOR_VERSION,
            "seed": candidate.seed,
            "requiredShapeCount": candidate.config.required_shape_count,
            "distractorShapeCount": candidate.config.distractor_shape_count,
            "shapePoolComplexity": candidate.config.shape_pool_complexity,
            "overlapAllowed": candidate.config.overlap_allowed,
            "overlapRatio": round(candidate.overlap_ratio, 6),
            "contourComplexity": candidate.contour_complexity,
            "connectedComponents": candidate.connected_components,
            "fillRatio": round(candidate.fill_ratio, 6),
            "difficultyScore": round(candidate.quality_score, 6),
            "rasterScale": raster_scale,
            "targetPackaging": "solution_xor_components",
        },
    }
    if extra_meta:
        payload["meta"].update(extra_meta)
    return payload


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


def calculate_transformed_vertices(
    shape_data: dict[str, list[int]],
    angle: int,
    vertex_id: str,
    target_grid: Point,
) -> list[tuple[str, Point]]:
    rotated_vertices = []
    for vertex_name, point in sorted(shape_data.items(), key=lambda item: int(item[0][1:])):
        rotated_vertices.append((vertex_name, rotate_point((point[0], point[1]), angle)))

    anchor = next(vertex for vertex in rotated_vertices if vertex[0] == vertex_id)
    translate_x = target_grid[0] - anchor[1][0]
    translate_y = target_grid[1] - anchor[1][1]
    return [
        (name, (point[0] + translate_x, point[1] + translate_y))
        for name, point in rotated_vertices
    ]


def build_mask_from_target_polygons(
    target_polygons: list[dict],
    grid_size: int,
    raster_scale: int,
) -> np.ndarray:
    masks = [
        rasterize_polygon(
            [(point[0], point[1]) for point in polygon_item["polygon"]],
            grid_size,
            raster_scale,
        )
        for polygon_item in target_polygons
    ]
    return xor_masks(masks)


def validate_level_payload(payload: dict) -> None:
    required_top_level = {"name", "gridSize", "inventory", "target", "solutionText", "meta"}
    missing_keys = required_top_level - set(payload)
    if missing_keys:
        raise ValueError(f"Missing top-level keys: {sorted(missing_keys)}")

    if not isinstance(payload["gridSize"], int) or payload["gridSize"] <= 0:
        raise ValueError("gridSize must be a positive integer.")

    if not payload["inventory"]:
        raise ValueError("inventory must not be empty.")

    for shape_id, shape_data in payload["inventory"].items():
        if len(shape_data) < 3:
            raise ValueError(f"{shape_id} must contain at least three vertices.")
        for vertex_id, point in shape_data.items():
            if not vertex_id.startswith("V"):
                raise ValueError(f"Unexpected vertex id: {vertex_id}")
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(isinstance(value, int) for value in point)
            ):
                raise ValueError(f"{shape_id}.{vertex_id} must be an integer [x, y] pair.")

    if not payload["target"]:
        raise ValueError("target must not be empty.")

    for polygon_item in payload["target"]:
        polygon = polygon_item.get("polygon")
        if not polygon or len(polygon) < 3:
            raise ValueError("Each target polygon must contain at least three points.")

    solution_steps = parse_solution_text(payload["solutionText"])
    if len(solution_steps) != payload["meta"]["requiredShapeCount"]:
        raise ValueError("solutionText line count must equal meta.requiredShapeCount.")


def replay_solution_mask(payload: dict, raster_scale: int) -> np.ndarray:
    solution_masks = []
    for shape_id, angle, vertex_id, target_grid in parse_solution_text(payload["solutionText"]):
        transformed = calculate_transformed_vertices(
            payload["inventory"][shape_id],
            angle,
            vertex_id,
            target_grid,
        )
        solution_masks.append(
            rasterize_polygon(
                [point for _, point in transformed],
                payload["gridSize"],
                raster_scale,
            )
        )
    return xor_masks(solution_masks)


def verify_level_payload(payload: dict, raster_scale: int) -> None:
    validate_level_payload(payload)

    target_mask = build_mask_from_target_polygons(
        payload["target"],
        payload["gridSize"],
        raster_scale,
    )
    replay_mask = replay_solution_mask(payload, raster_scale)
    if not np.array_equal(target_mask, replay_mask):
        raise ValueError(f"{payload['name']} failed replay validation.")

    placement_signatures = []
    for shape_id, shape_data in payload["inventory"].items():
        template = ShapeTemplate(
            template_id=shape_id,
            complexity=payload["meta"]["shapePoolComplexity"],
            vertices=tuple(
                (point[0], point[1])
                for _, point in sorted(shape_data.items(), key=lambda item: int(item[0][1:]))
            ),
        )
        placement_signatures.append(
            enumerate_shape_placement_signatures(template, payload["gridSize"], raster_scale)
        )

    if has_solution_with_fewer_shapes(
        mask_signature(target_mask),
        placement_signatures,
        payload["meta"]["requiredShapeCount"],
    ):
        raise ValueError(
            f"{payload['name']} can be solved with fewer than the required number of shapes."
        )


def generate_level(config: LevelConfig, seed: int, raster_scale: int) -> dict:
    rng = random.Random(seed)
    accepted_candidates: list[Candidate] = []
    best_candidate: Candidate | None = None

    for _ in range(config.max_attempts):
        candidate = build_candidate(config, seed, raster_scale, rng)
        if candidate is None:
            continue
        accepted_candidates.append(candidate)
        if best_candidate is None or candidate.quality_score < best_candidate.quality_score:
            best_candidate = candidate
        if len(accepted_candidates) >= config.accepted_candidates_goal and best_candidate is not None:
            break

    if best_candidate is None:
        raise RuntimeError(
            f"Unable to generate a valid {config.name} within {config.max_attempts} attempts."
        )

    payload = candidate_to_level_payload(best_candidate, raster_scale)
    verify_level_payload(payload, raster_scale)
    return payload


def generate_campaign(seed: int, raster_scale: int) -> list[dict]:
    payloads = []
    for config in CAMPAIGN_CONFIGS:
        level_seed = seed * 100 + config.level_index
        payloads.append(generate_level(config, level_seed, raster_scale))
    validate_campaign_progression(payloads)
    return payloads


def generate_catalog500(seed: int, raster_scale: int) -> list[dict]:
    payloads: list[dict] = []
    seen_target_signatures: set[int] = set()
    catalog_index = 1

    for tier in CATALOG_500_TIERS:
        created_for_tier = 0
        tier_attempt = 0
        max_seed_attempts = max(tier.count * 80, 400)
        while created_for_tier < tier.count:
            if tier_attempt >= max_seed_attempts:
                raise RuntimeError(
                    f"Unable to fill difficulty tier {tier.tier_id} "
                    f"after {max_seed_attempts} seed attempts."
                )
            tier_attempt += 1
            level_seed = seed * 100000 + tier.tier_id * 1000 + tier_attempt
            try:
                payload = generate_level(tier.config, level_seed, raster_scale)
            except RuntimeError:
                continue
            level_name = f"Level {catalog_index:03d}"
            payload["name"] = level_name
            payload["meta"].update(
                {
                    "catalogIndex": catalog_index,
                    "difficultyTier": tier.tier_id,
                    "difficultyLabel": tier.label,
                    "strictValidation": True,
                }
            )

            target_mask = build_mask_from_target_polygons(
                payload["target"],
                payload["gridSize"],
                payload["meta"]["rasterScale"],
            )
            signature = mask_signature(target_mask)
            if signature in seen_target_signatures:
                continue

            seen_target_signatures.add(signature)
            payloads.append(payload)
            created_for_tier += 1
            catalog_index += 1
            print(f"Generated {catalog_index - 1}/500: {payload['name']}", flush=True)

    validate_catalog500(payloads)
    return payloads


def load_existing_catalog_payloads(output_dir: Path) -> list[dict]:
    level_paths = sorted(output_dir.glob("level*.json"))
    payloads = [
        json.loads(level_path.read_text(encoding="utf-8"))
        for level_path in level_paths
    ]
    payloads.sort(key=lambda payload: payload["meta"]["catalogIndex"])
    return payloads


def build_target_signature_set(payloads: list[dict]) -> set[int]:
    signatures: set[int] = set()
    for payload in payloads:
        target_mask = build_mask_from_target_polygons(
            payload["target"],
            payload["gridSize"],
            payload["meta"]["rasterScale"],
        )
        signatures.add(mask_signature(target_mask))
    return signatures


def generate_catalog724(seed: int, raster_scale: int, output_dir: Path) -> list[dict]:
    existing_payloads = load_existing_catalog_payloads(output_dir)
    if len(existing_payloads) != 500:
        raise RuntimeError(
            "catalog724 incremental generation expects exactly 500 existing levels in the output directory."
        )

    validate_catalog500(existing_payloads)

    payloads = list(existing_payloads)
    seen_target_signatures = build_target_signature_set(existing_payloads)
    catalog_index = len(existing_payloads) + 1

    for tier in CATALOG_724_EXTENSION_TIERS:
        created_for_tier = 0
        tier_attempt = 0
        max_seed_attempts = max(tier.count * 120, 400)
        while created_for_tier < tier.count:
            if tier_attempt >= max_seed_attempts:
                raise RuntimeError(
                    f"Unable to extend difficulty tier {tier.tier_id} "
                    f"after {max_seed_attempts} seed attempts."
                )
            tier_attempt += 1
            level_seed = seed * 100000 + 500000 + tier.tier_id * 1000 + tier_attempt
            try:
                payload = generate_level(tier.config, level_seed, raster_scale)
            except RuntimeError:
                continue

            payload["name"] = f"Level {catalog_index:03d}"
            payload["meta"].update(
                {
                    "catalogIndex": catalog_index,
                    "difficultyTier": tier.tier_id,
                    "difficultyLabel": tier.label,
                    "strictValidation": True,
                }
            )

            target_mask = build_mask_from_target_polygons(
                payload["target"],
                payload["gridSize"],
                payload["meta"]["rasterScale"],
            )
            signature = mask_signature(target_mask)
            if signature in seen_target_signatures:
                continue

            seen_target_signatures.add(signature)
            payloads.append(payload)
            created_for_tier += 1
            catalog_index += 1
            print(f"Generated {catalog_index - 1}/724: {payload['name']}", flush=True)

    validate_catalog724(payloads)
    return payloads


def validate_campaign_progression(payloads: list[dict]) -> None:
    required_counts = [payload["meta"]["requiredShapeCount"] for payload in payloads]
    distractor_counts = [payload["meta"]["distractorShapeCount"] for payload in payloads]
    overlap_flags = [payload["meta"]["overlapAllowed"] for payload in payloads]

    if required_counts != sorted(required_counts):
        raise ValueError("requiredShapeCount must be non-decreasing across the campaign.")
    if distractor_counts != sorted(distractor_counts):
        raise ValueError("distractorShapeCount must be non-decreasing across the campaign.")
    if overlap_flags[:2] != [False, False] or overlap_flags[2:] != [True, True, True]:
        raise ValueError("overlapAllowed must only enable from level3 onward.")

    overlap_ranges = {
        "Level 3": (0.08, 0.18),
        "Level 4": (0.15, 0.28),
        "Level 5": (0.22, 0.35),
    }
    for payload in payloads:
        level_name = payload["name"]
        if level_name in overlap_ranges:
            lower, upper = overlap_ranges[level_name]
            overlap_ratio = payload["meta"]["overlapRatio"]
            if not (lower <= overlap_ratio <= upper):
                raise ValueError(f"{level_name} overlapRatio is out of range.")


def validate_catalog_payloads(
    payloads: list[dict],
    expected_count: int,
    expected_tiers: tuple[DifficultyTier, ...],
    preset_name: str,
) -> None:
    if len(payloads) != expected_count:
        raise ValueError(f"{preset_name} must contain exactly {expected_count} levels.")

    target_signatures: set[int] = set()
    expected_index = 1
    tier_counts = defaultdict(int)

    for payload in payloads:
        meta = payload["meta"]
        if meta["catalogIndex"] != expected_index:
            raise ValueError("catalogIndex sequence is broken.")
        expected_index += 1

        tier_counts[meta["difficultyTier"]] += 1
        verify_level_payload(payload, meta["rasterScale"])

        target_mask = build_mask_from_target_polygons(
            payload["target"],
            payload["gridSize"],
            meta["rasterScale"],
        )
        signature = mask_signature(target_mask)
        if signature in target_signatures:
            raise ValueError(f"Duplicate target detected in {payload['name']}.")
        target_signatures.add(signature)

    for tier in expected_tiers:
        if tier_counts[tier.tier_id] != tier.count:
            raise ValueError(
                f"Difficulty tier {tier.tier_id} expected {tier.count} levels, "
                f"got {tier_counts[tier.tier_id]}."
            )


def validate_catalog500(payloads: list[dict]) -> None:
    validate_catalog_payloads(payloads, 500, CATALOG_500_TIERS, "catalog500")


def validate_catalog724(payloads: list[dict]) -> None:
    validate_catalog_payloads(payloads, 724, CATALOG_724_TOTAL_TIERS, "catalog724")


def deterministic_smoke_test(seed: int, raster_scale: int) -> None:
    first_pass = generate_campaign(seed, raster_scale)
    second_pass = generate_campaign(seed, raster_scale)
    first_json = json.dumps(first_pass, ensure_ascii=False, sort_keys=True)
    second_json = json.dumps(second_pass, ensure_ascii=False, sort_keys=True)
    if first_json != second_json:
        raise AssertionError(
            "Deterministic smoke test failed: repeated generation with the same seed differed."
        )


def deterministic_catalog_sample_test(seed: int, raster_scale: int) -> None:
    first_sample = generate_catalog500_sample(seed, raster_scale, sample_count=12)
    second_sample = generate_catalog500_sample(seed, raster_scale, sample_count=12)
    first_json = json.dumps(first_sample, ensure_ascii=False, sort_keys=True)
    second_json = json.dumps(second_sample, ensure_ascii=False, sort_keys=True)
    if first_json != second_json:
        raise AssertionError(
            "Catalog deterministic sample test failed: repeated generation with the same seed differed."
        )


def generate_catalog500_sample(seed: int, raster_scale: int, sample_count: int = 12) -> list[dict]:
    payloads: list[dict] = []
    seen_target_signatures: set[int] = set()
    catalog_index = 1

    for tier in CATALOG_500_TIERS:
        if len(payloads) >= sample_count:
            break
        created_for_tier = 0
        tier_attempt = 0
        tier_target = max(1, min(tier.count, sample_count - len(payloads)))
        max_seed_attempts = max(tier_target * 80, 200)

        while created_for_tier < tier_target:
            if tier_attempt >= max_seed_attempts:
                raise RuntimeError(
                    f"Unable to sample difficulty tier {tier.tier_id} "
                    f"after {max_seed_attempts} seed attempts."
                )
            tier_attempt += 1
            level_seed = seed * 100000 + tier.tier_id * 1000 + tier_attempt
            try:
                payload = generate_level(tier.config, level_seed, raster_scale)
            except RuntimeError:
                continue
            payload["name"] = f"Level {catalog_index:03d}"
            payload["meta"].update(
                {
                    "catalogIndex": catalog_index,
                    "difficultyTier": tier.tier_id,
                    "difficultyLabel": tier.label,
                    "strictValidation": True,
                }
            )
            target_mask = build_mask_from_target_polygons(
                payload["target"],
                payload["gridSize"],
                payload["meta"]["rasterScale"],
            )
            signature = mask_signature(target_mask)
            if signature in seen_target_signatures:
                continue
            seen_target_signatures.add(signature)
            payloads.append(payload)
            created_for_tier += 1
            catalog_index += 1

    return payloads


def build_level_manifest(payloads: list[dict]) -> dict:
    levels: list[dict] = []
    has_catalog_metadata = any("catalogIndex" in payload.get("meta", {}) for payload in payloads)
    source = f"catalog{len(payloads)}" if has_catalog_metadata else "campaign"

    for payload in payloads:
        meta = payload["meta"]
        level_number = payload["name"].split()[-1]
        level_entry = {
            "id": f"level{level_number}",
            "name": payload["name"],
            "gridSize": payload["gridSize"],
            "requiredShapeCount": meta["requiredShapeCount"],
            "distractorShapeCount": meta["distractorShapeCount"],
            "shapePoolComplexity": meta["shapePoolComplexity"],
            "overlapAllowed": meta["overlapAllowed"],
            "overlapRatio": meta["overlapRatio"],
            "connectedComponents": meta["connectedComponents"],
        }
        if "catalogIndex" in meta:
            level_entry["catalogIndex"] = meta["catalogIndex"]
        if "difficultyTier" in meta:
            level_entry["difficultyTier"] = meta["difficultyTier"]
        if "difficultyLabel" in meta:
            level_entry["difficultyLabel"] = meta["difficultyLabel"]
        levels.append(level_entry)

    return {
        "version": 1,
        "source": source,
        "count": len(levels),
        "levels": levels,
    }


def write_levels(payloads: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for existing_path in output_dir.glob("level*.json"):
        existing_path.unlink()
    for payload in payloads:
        level_number = payload["name"].split()[-1]
        output_path = output_dir / f"level{level_number}.json"
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(build_level_manifest(payloads), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def generate_sequential_level_id(index: int) -> str:
    return f"voi-{index:03d}"


def transform_payload_for_data_export(source_payload: dict, level_id: str) -> dict:
    payload = json.loads(json.dumps(source_payload, ensure_ascii=False))
    payload["ID"] = level_id
    if "solutionText" in payload:
        payload["answer"] = payload.pop("solutionText")
    elif "answer" in payload:
        payload["answer"] = payload["answer"]
    else:
        raise KeyError("Neither 'solutionText' nor 'answer' exists in the source payload.")
    payload.pop("name", None)

    meta = payload.get("meta", {})
    for redundant_key in ("generatorVersion", "difficultyTier", "difficultyLabel"):
        meta.pop(redundant_key, None)

    image_assets = payload.get("imageAssets")
    if isinstance(image_assets, dict):
        image_assets["target"] = f"../images/{level_id}/target.png"
        shape_assets = image_assets.get("shapes", {})
        if isinstance(shape_assets, dict):
            for shape_id in list(shape_assets.keys()):
                shape_assets[shape_id] = f"../images/{level_id}/shape_{shape_id}.png"

    return payload


def resolve_source_image_dir(
    source_payload: dict,
    level_path: Path,
    source_images_dir: Path,
) -> Path:
    image_assets = source_payload.get("imageAssets", {})
    target_asset = image_assets.get("target") if isinstance(image_assets, dict) else None
    if isinstance(target_asset, str):
        image_dir_name = Path(target_asset).parent.name
        return source_images_dir / image_dir_name
    return source_images_dir / level_path.stem


def export_data_subset(
    source_levels_dir: Path,
    source_images_dir: Path,
    data_dir: Path,
    limit: int,
) -> None:
    source_level_paths = [
        level_path
        for level_path in source_levels_dir.glob("*.json")
        if level_path.name != "manifest.json"
    ]
    source_payload_entries = [
        (
            level_path,
            json.loads(level_path.read_text(encoding="utf-8")),
        )
        for level_path in source_level_paths
    ]
    source_payload_entries.sort(
        key=lambda entry: (
            entry[1].get("meta", {}).get("catalogIndex", 10**9),
            entry[0].name,
        )
    )
    source_payload_entries = source_payload_entries[:limit]
    if len(source_payload_entries) < limit:
        raise RuntimeError(
            f"Requested {limit} levels for data export, but only found {len(source_level_paths)} in {source_levels_dir}."
        )

    data_levels_dir = data_dir / "levels"
    data_images_dir = data_dir / "images"
    data_levels_dir.mkdir(parents=True, exist_ok=True)
    data_images_dir.mkdir(parents=True, exist_ok=True)

    same_levels_dir = source_levels_dir.resolve() == data_levels_dir.resolve()
    same_images_dir = source_images_dir.resolve() == data_images_dir.resolve()
    staging_root = data_dir / ".tmp_export_staging"
    staging_levels_dir = staging_root / "levels"
    staging_images_dir = staging_root / "images"
    target_levels_dir = staging_levels_dir if same_levels_dir else data_levels_dir
    target_images_dir = staging_images_dir if same_images_dir else data_images_dir

    if staging_root.exists():
        shutil.rmtree(staging_root)
    if same_levels_dir or same_images_dir:
        staging_levels_dir.mkdir(parents=True, exist_ok=True)
        staging_images_dir.mkdir(parents=True, exist_ok=True)

    if not same_levels_dir:
        for stale_level_path in data_levels_dir.glob("*.json"):
            stale_level_path.unlink()
    if not same_images_dir:
        for stale_image_dir in data_images_dir.iterdir():
            if stale_image_dir.is_dir():
                shutil.rmtree(stale_image_dir)

    manifest_levels: list[dict] = []

    for index, (level_path, source_payload) in enumerate(source_payload_entries):
        sequential_level_id = generate_sequential_level_id(index)
        transformed_payload = transform_payload_for_data_export(source_payload, sequential_level_id)
        meta = transformed_payload.get("meta", {})

        target_level_path = target_levels_dir / f"{sequential_level_id}.json"
        target_level_path.write_text(
            json.dumps(transformed_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        manifest_level_entry = {
            "id": sequential_level_id,
            "gridSize": transformed_payload.get("gridSize"),
            "requiredShapeCount": meta.get("requiredShapeCount"),
            "distractorShapeCount": meta.get("distractorShapeCount"),
            "shapePoolComplexity": meta.get("shapePoolComplexity"),
            "overlapAllowed": meta.get("overlapAllowed"),
            "overlapRatio": meta.get("overlapRatio"),
            "connectedComponents": meta.get("connectedComponents"),
            "catalogIndex": meta.get("catalogIndex"),
        }
        manifest_levels.append(manifest_level_entry)

        source_image_dir = resolve_source_image_dir(source_payload, level_path, source_images_dir)
        if not source_image_dir.exists():
            raise FileNotFoundError(f"Missing source image directory: {source_image_dir}")
        shutil.copytree(source_image_dir, target_images_dir / random_level_id)

    manifest_payload = {
        "version": 1,
        "source": f"data_export_{limit}",
        "count": len(manifest_levels),
        "levels": manifest_levels,
    }
    manifest_output_path = target_levels_dir / "manifest.json"
    manifest_output_path.write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if same_levels_dir:
        for stale_level_path in data_levels_dir.glob("*.json"):
            stale_level_path.unlink()
        for staged_level_path in staging_levels_dir.glob("*.json"):
            shutil.move(str(staged_level_path), data_levels_dir / staged_level_path.name)

    if same_images_dir:
        for stale_image_dir in data_images_dir.iterdir():
            if stale_image_dir.is_dir():
                shutil.rmtree(stale_image_dir)
        for staged_image_dir in staging_images_dir.iterdir():
            shutil.move(str(staged_image_dir), data_images_dir / staged_image_dir.name)

    if staging_root.exists():
        shutil.rmtree(staging_root)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate validated Text-VOI campaign levels.")
    parser.add_argument("--preset", default="campaign", choices=["campaign", "catalog500", "catalog724"])
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--output-dir", default="levels", type=Path)
    parser.add_argument("--source-images-dir", default="images", type=Path)
    parser.add_argument("--export-data-dir", default=None, type=Path)
    parser.add_argument("--export-data-limit", default=600, type=int)
    parser.add_argument("--export-data-only", action="store_true")
    parser.add_argument("--raster-scale", default=DEFAULT_RASTER_SCALE, type=int)
    parser.add_argument("--self-check", action="store_true")
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.export_data_only:
        export_target_dir = args.export_data_dir or Path("data")
        export_data_subset(
            args.output_dir,
            args.source_images_dir,
            export_target_dir,
            args.export_data_limit,
        )
        print(
            f"Exported {args.export_data_limit} levels into "
            f"{export_target_dir / 'levels'} and {export_target_dir / 'images'}."
        )
        return 0

    if args.self_check:
        if args.preset == "campaign":
            deterministic_smoke_test(args.seed, args.raster_scale)
            print("Deterministic smoke test passed.")
        else:
            deterministic_catalog_sample_test(args.seed, args.raster_scale)
            print("Catalog deterministic sample test passed.")

    if args.preset == "campaign":
        payloads = generate_campaign(args.seed, args.raster_scale)
    elif args.preset == "catalog500":
        payloads = generate_catalog500(args.seed, args.raster_scale)
    else:
        payloads = generate_catalog724(args.seed, args.raster_scale, args.output_dir)

    write_levels(payloads, args.output_dir)

    if args.export_data_dir is not None:
        export_data_subset(
            args.output_dir,
            args.source_images_dir,
            args.export_data_dir,
            args.export_data_limit,
        )

    for payload in payloads:
        meta = payload["meta"]
        summary = (
            f"{payload['name']}: "
            f"required={meta['requiredShapeCount']}, "
            f"distractors={meta['distractorShapeCount']}, "
            f"overlap={meta['overlapRatio']}, "
            f"components={meta['connectedComponents']}, "
            f"score={meta['difficultyScore']}"
        )
        if args.preset.startswith("catalog"):
            summary += f", tier={meta['difficultyTier']}"
        print(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
