from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from eval_common import FaceObservation, GoalRollTask, ModelAnswer


VALID_ROTATIONS = {0, 90, 180, 270}
FACE_ORDER = ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"]


def normalize_rotation(rotation: int) -> int:
    normalized = int(rotation) % 360
    if normalized not in VALID_ROTATIONS:
        raise ValueError(f"Rotation must be one of 0, 90, 180, 270, got {rotation}")
    return normalized


def normalize_face_payload(face: Any) -> dict[str, Any]:
    if isinstance(face, FaceObservation):
        return {
            "patternId": str(face.patternId),
            "rotation": normalize_rotation(face.rotation),
        }

    payload = dict(face or {})
    return {
        "patternId": str(payload.get("patternId", "?")),
        "rotation": normalize_rotation(payload.get("rotation", 0)),
    }


@dataclass
class CubeState:
    faces: List[dict[str, Any]]
    x: int = 0
    y: int = 0

    def clone(self) -> "CubeState":
        return CubeState([dict(face) for face in self.faces], self.x, self.y)

    @property
    def top(self) -> dict[str, Any]:
        return self.faces[0]

    @property
    def bottom(self) -> dict[str, Any]:
        return self.faces[1]

    @property
    def front(self) -> dict[str, Any]:
        return self.faces[2]

    @property
    def back(self) -> dict[str, Any]:
        return self.faces[3]

    @property
    def left(self) -> dict[str, Any]:
        return self.faces[4]

    @property
    def right(self) -> dict[str, Any]:
        return self.faces[5]

    def _remap(self, mapping: List[int], rotation_adjustments: List[int]) -> None:
        old = [dict(face) for face in self.faces]
        for index in range(6):
            previous = old[mapping[index]]
            self.faces[index] = {
                "patternId": previous["patternId"],
                "rotation": normalize_rotation(previous["rotation"] + rotation_adjustments[index]),
            }

    def roll_north(self) -> "CubeState":
        self._remap([2, 3, 1, 0, 4, 5], [0, 180, 0, 180, -90, 90])
        self.y -= 1
        return self

    def roll_south(self) -> "CubeState":
        self._remap([3, 2, 0, 1, 4, 5], [180, 0, 0, 180, 90, -90])
        self.y += 1
        return self

    def roll_east(self) -> "CubeState":
        self._remap([4, 5, 2, 3, 1, 0], [90, 90, 90, -90, 90, 90])
        self.x += 1
        return self

    def roll_west(self) -> "CubeState":
        self._remap([5, 4, 2, 3, 0, 1], [-90, -90, -90, 90, -90, -90])
        self.x -= 1
        return self

    def roll(self, direction: str) -> "CubeState":
        if direction == "N":
            return self.roll_north()
        if direction == "S":
            return self.roll_south()
        if direction == "E":
            return self.roll_east()
        if direction == "W":
            return self.roll_west()
        raise ValueError(f"Unknown direction: {direction}")


def cube_from_solution_faces(solution_faces: Dict[str, Any]) -> CubeState:
    normalized = {key: normalize_face_payload(solution_faces[key]) for key in FACE_ORDER}
    return CubeState(
        [
            normalized["TOP"],
            normalized["BOTTOM"],
            normalized["FRONT"],
            normalized["BACK"],
            normalized["LEFT"],
            normalized["RIGHT"],
        ]
    )


def build_visible_initial_faces(visible_solution_faces: Dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    visible_solution_faces = visible_solution_faces or {}
    return {
        key: normalize_face_payload(visible_solution_faces.get(key, {"patternId": "?", "rotation": 0}))
        for key in FACE_ORDER
    }


def bottom_face_to_path_view_face(face: dict[str, Any], *, x: int | None = None, y: int | None = None) -> dict[str, Any]:
    payload = normalize_face_payload(face)
    payload["x"] = 0 if x is None else int(x)
    payload["y"] = 0 if y is None else int(y)
    return payload


def observe_bottom_face(cube: CubeState) -> dict[str, Any]:
    return bottom_face_to_path_view_face(cube.bottom, x=cube.x, y=cube.y)


def observe_top_face(cube: CubeState) -> dict[str, Any]:
    payload = normalize_face_payload(cube.top)
    payload["x"] = int(cube.x)
    payload["y"] = int(cube.y)
    return payload


def compare_faces(left: dict[str, Any], right: FaceObservation) -> bool:
    right_payload = normalize_face_payload(right)
    return (
        str(left.get("patternId", "?")) == right_payload["patternId"]
        and normalize_rotation(left.get("rotation", 0)) == right_payload["rotation"]
    )


def compare_face_patterns(left: dict[str, Any], right: FaceObservation) -> bool:
    right_payload = normalize_face_payload(right)
    return str(left.get("patternId", "?")) == right_payload["patternId"]


def build_trace(initial_state: CubeState, directions: List[str]) -> tuple[List[dict[str, Any]], CubeState]:
    cube = initial_state.clone()
    observed_faces: List[dict[str, Any]] = []
    for direction in directions:
        cube.roll(direction)
        observed_faces.append(observe_top_face(cube))
    return observed_faces, cube


def evaluate_with_project_engine(task: GoalRollTask, answer: ModelAnswer) -> dict[str, Any]:
    initial_faces = build_visible_initial_faces(task.visible_solution_faces)
    initial_state = cube_from_solution_faces(initial_faces)
    normalized_directions = list(answer.directions)
    observed_trace, final_cube = build_trace(initial_state, normalized_directions)
    final_face = observed_trace[-1] if observed_trace else observe_top_face(initial_state)
    target_face = normalize_face_payload(task.target_top_face)
    pattern_correct = compare_face_patterns(final_face, task.target_top_face)
    matched = compare_faces(final_face, task.target_top_face)
    exact_reference_match = normalized_directions == list(task.reference_directions)

    return {
        "evaluation_status": "ok",
        "is_pattern_correct": pattern_correct,
        "is_pattern_and_rotation_correct": matched,
        "is_valid_solution": matched,
        "is_fully_correct": matched,
        "exact_reference_match": exact_reference_match,
        "predicted_move_count": len(normalized_directions),
        "reference_move_count": len(task.reference_directions),
        "normalized_directions": normalized_directions,
        "reference_directions": list(task.reference_directions),
        "target_face": target_face,
        "final_observed_face": final_face,
        "final_cube_position": {"x": final_cube.x, "y": final_cube.y},
        "trace_observed_faces": observed_trace,
        "mismatch_reason": None if matched else "The final top face does not match the target face exactly.",
    }
