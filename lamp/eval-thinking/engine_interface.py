from __future__ import annotations

import math
from typing import Any


def _point_in_rect(point: dict[str, float], rect: dict[str, float]) -> bool:
    return (
        point["x"] >= rect["x"] and
        point["x"] <= rect["x"] + rect["width"] and
        point["y"] >= rect["y"] and
        point["y"] <= rect["y"] + rect["height"]
    )


def _orientation(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> int:
    value = ((b["y"] - a["y"]) * (c["x"] - b["x"])) - ((b["x"] - a["x"]) * (c["y"] - b["y"]))
    if abs(value) < 1e-9:
        return 0
    return 1 if value > 0 else 2


def _on_segment(a: dict[str, float], b: dict[str, float], c: dict[str, float]) -> bool:
    return (
        min(a["x"], c["x"]) - 1e-9 <= b["x"] <= max(a["x"], c["x"]) + 1e-9 and
        min(a["y"], c["y"]) - 1e-9 <= b["y"] <= max(a["y"], c["y"]) + 1e-9
    )


def _segments_intersect(a1: dict[str, float], a2: dict[str, float], b1: dict[str, float], b2: dict[str, float]) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _on_segment(a1, b1, a2):
        return True
    if o2 == 0 and _on_segment(a1, b2, a2):
        return True
    if o3 == 0 and _on_segment(b1, a1, b2):
        return True
    if o4 == 0 and _on_segment(b1, a2, b2):
        return True

    return False


def _segment_intersects_rect(start: dict[str, float], end: dict[str, float], rect: dict[str, float]) -> bool:
    if _point_in_rect(start, rect) or _point_in_rect(end, rect):
        return True

    top_left = {"x": rect["x"], "y": rect["y"] + rect["height"]}
    top_right = {"x": rect["x"] + rect["width"], "y": rect["y"] + rect["height"]}
    bottom_left = {"x": rect["x"], "y": rect["y"]}
    bottom_right = {"x": rect["x"] + rect["width"], "y": rect["y"]}

    return (
        _segments_intersect(start, end, top_left, top_right) or
        _segments_intersect(start, end, top_right, bottom_right) or
        _segments_intersect(start, end, bottom_right, bottom_left) or
        _segments_intersect(start, end, bottom_left, top_left)
    )


def _collect_obstacle_collisions(joints: list[dict[str, float]], obstacles: list[dict[str, Any]]) -> list[str]:
    collided_ids: list[str] = []

    for obstacle in obstacles:
      obstacle_id = str(obstacle.get("id", "wall"))
      parts = list(obstacle.get("parts", []))
      collision_found = False

      for start, end in zip(joints, joints[1:]):
          if any(_segment_intersects_rect(start, end, part) for part in parts):
              collision_found = True
              break

      if collision_found:
          collided_ids.append(obstacle_id)

    return collided_ids


def evaluate_solution(
    *,
    origin: dict[str, float],
    segments: list[int],
    angles: list[int],
    target: dict[str, float],
    light_radius: float,
    obstacles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_x = float(origin.get("x", 0))
    base_y = float(origin.get("y", 0))
    x = base_x
    y = base_y
    joints = [{"x": round(base_x, 2), "y": round(base_y, 2)}]

    for length, angle in zip(segments, angles):
        radians = math.radians(angle)
        x += length * math.cos(radians)
        y += length * math.sin(radians)
        joints.append({"x": round(x, 2), "y": round(y, 2)})

    predicted_bulb = {
        "x": round(x, 2),
        "y": round(y, 2),
    }
    distance = round(math.hypot(target["x"] - x, target["y"] - y), 4)
    blocking_obstacles = _collect_obstacle_collisions(joints, obstacles or [])
    collision_with_obstacle = len(blocking_obstacles) > 0
    solved = (distance <= light_radius) and not collision_with_obstacle

    return {
        "evaluation_status": "obstacle_collision" if collision_with_obstacle else "ok",
        "is_valid_solution": solved,
        "is_pattern_correct": solved,
        "is_pattern_and_rotation_correct": solved,
        "is_fully_correct": solved,
        "distance": distance,
        "origin": origin,
        "predicted_bulb": predicted_bulb,
        "target": target,
        "light_radius": light_radius,
        "normalized_angles": list(angles),
        "collision_with_obstacle": collision_with_obstacle,
        "blocking_obstacles": blocking_obstacles,
        "format_error": None,
        "solution_error": (
            "The mechanical arm intersects an obstacle wall."
            if collision_with_obstacle
            else (None if solved else "The lamp light radius does not cover the target point.")
        ),
    }

