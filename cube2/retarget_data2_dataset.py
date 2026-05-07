from __future__ import annotations

import json
import random
import sys
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any


CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR / "data2"
TASK_DIR = DATA_DIR / "task_jsons"
MANIFEST_PATH = DATA_DIR / "manifests" / "goal_roll_tasks.jsonl"
SAMPLED_MANIFEST_PATH = DATA_DIR / "manifests" / "sampled_150_seed20260425.jsonl"
SEED = 20260426
VALID_DIRECTIONS = ("N", "S", "E", "W")
ROTATION_OFFSETS = (90, 180, 270)
MAX_SEARCH_DEPTH = 20
SAMPLED_COUNT = 150

sys.path.insert(0, str((CURRENT_DIR / "eval-thinking").resolve()))
from engine_interface import cube_from_solution_faces, observe_top_face  # noqa: E402
from generate_goal_roll_dataset import render_target_top_face_image  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_face(face: dict[str, Any]) -> dict[str, Any]:
    return {
        "patternId": str(face.get("patternId", "?")),
        "rotation": int(face.get("rotation", 0)) % 360,
    }


def face_matches(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        str(left.get("patternId", "?")) == str(right.get("patternId", "?"))
        and int(left.get("rotation", 0)) % 360 == int(right.get("rotation", 0)) % 360
    )


def cube_state_key(cube: Any) -> tuple[Any, ...]:
    return tuple(
        (
            str(face.get("patternId", "?")),
            int(face.get("rotation", 0)) % 360,
        )
        for face in cube.faces
    )


def find_reachable_sequence(solution_faces: dict[str, Any], target_face: dict[str, Any]) -> list[str] | None:
    initial_cube = cube_from_solution_faces(solution_faces)
    initial_observed = normalize_face(observe_top_face(initial_cube))
    if face_matches(initial_observed, target_face):
        return []

    queue: deque[tuple[Any, list[str]]] = deque([(initial_cube, [])])
    visited = {cube_state_key(initial_cube)}

    while queue:
        cube, path = queue.popleft()
        if len(path) >= MAX_SEARCH_DEPTH:
            continue

        for direction in VALID_DIRECTIONS:
            next_cube = cube.clone()
            next_cube.roll(direction)
            key = cube_state_key(next_cube)
            if key in visited:
                continue
            visited.add(key)

            next_path = path + [direction]
            observed_face = normalize_face(observe_top_face(next_cube))
            if face_matches(observed_face, target_face):
                return next_path

            queue.append((next_cube, next_path))

    return None


def build_invalidated_answers() -> dict[str, Any]:
    return {
        "directions": [],
        "moveCount": 0,
        "referenceValid": False,
    }


def choose_rotated_target(
    payload: dict[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], int, list[str]]:
    original_target = normalize_face(dict(payload.get("targetTopFace", {})))
    solution_faces = dict(payload.get("initialCube", {}).get("solutionFaces", {}))
    offsets = list(ROTATION_OFFSETS)
    rng.shuffle(offsets)

    for offset in offsets:
        candidate = deepcopy(original_target)
        candidate["rotation"] = (candidate["rotation"] + offset) % 360
        witness = find_reachable_sequence(solution_faces, candidate)
        if witness is not None:
            return candidate, offset, witness

    raise RuntimeError(
        f"Could not find a reachable rotated top-face target within {MAX_SEARCH_DEPTH} steps for {payload.get('code', 'unknown')}."
    )


def mutate_task_payload(payload: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    mutated = deepcopy(payload)
    new_target, offset, witness = choose_rotated_target(mutated, rng)
    target = dict(mutated.get("targetTopFace", {}))
    target.update(new_target)
    mutated["targetTopFace"] = target
    mutated["answers"] = build_invalidated_answers()

    metadata = dict(mutated.get("metadata", {}))
    metadata["targetRotationOffset"] = offset
    mutated["metadata"] = metadata
    return mutated


def rewrite_manifest(task_payloads: list[dict[str, Any]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        for payload in task_payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def rewrite_sampled_manifest(task_payloads: list[dict[str, Any]], sample_count: int, seed: int) -> None:
    rng = random.Random(seed)
    sample_size = min(sample_count, len(task_payloads))
    sampled = rng.sample(task_payloads, sample_size)
    sampled.sort(key=lambda payload: str(payload.get("code", "")))

    with SAMPLED_MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        for payload in sampled:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    rng = random.Random(SEED)
    task_paths = sorted(TASK_DIR.glob("C*.json"))
    if not task_paths:
        raise FileNotFoundError(f"No task JSON files found under {TASK_DIR}")

    updated_payloads: list[dict[str, Any]] = []

    for task_path in task_paths:
        payload = load_json(task_path)
        mutated = mutate_task_payload(payload, rng)
        save_json(task_path, mutated)
        target_image_path = DATA_DIR / mutated["imagePaths"]["targetTopFaceImage"]
        render_target_top_face_image(mutated, target_image_path)
        updated_payloads.append(mutated)

    rewrite_manifest(updated_payloads)
    rewrite_sampled_manifest(updated_payloads, SAMPLED_COUNT, 20260425)
    print(f"Retargeted {len(updated_payloads)} top-face tasks under: {TASK_DIR}")


if __name__ == "__main__":
    main()
