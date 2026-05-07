"""Regenerate cube1/levels/index.json (the frontend's fat catalog) from
cube1/data/task_jsons/*.json (the canonical per-level files used by the eval
pipeline). Run this whenever the per-level files are edited so the frontend
stays in sync.

The catalog is a single JSON file with all 502 levels embedded; the frontend
fetches it once at startup and renders the level-select grid from its contents.
The per-level files are the source-of-truth schema (SimVerse v1, with
`answer.faces`); this script translates the snake_case per-level fields into
the camelCase catalog schema the frontend expects.

Run:
    python cube1/regenerate_catalog.py
    python cube1/regenerate_catalog.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS_DIR = PROJECT_ROOT / "data" / "task_jsons"
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "levels" / "index.json"

CATALOG_VERSION = 3

GROUPS_DEFINITION = [
    {"key": "tier-1", "label": "Difficulty 1", "description": "2-3 moves",  "minMoves": 2,  "maxMoves": 3},
    {"key": "tier-2", "label": "Difficulty 2", "description": "4-5 moves",  "minMoves": 4,  "maxMoves": 5},
    {"key": "tier-3", "label": "Difficulty 3", "description": "6-7 moves",  "minMoves": 6,  "maxMoves": 7},
    {"key": "tier-4", "label": "Difficulty 4", "description": "8-9 moves",  "minMoves": 8,  "maxMoves": 9},
    {"key": "tier-5", "label": "Difficulty 5", "description": "10-10 moves", "minMoves": 10, "maxMoves": 10},
]

REQUIRED_FACE_KEYS = ("TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT")


def _ensure_face_payload(face: dict[str, Any]) -> dict[str, Any]:
    return {
        "patternId": str(face.get("patternId", "?")),
        "rotation": int(face.get("rotation", 0)),
        "flipHorizontal": bool(face.get("flipHorizontal", False)),
        "flipVertical": bool(face.get("flipVertical", False)),
    }


def _ensure_face_map(face_map: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    face_map = face_map or {}
    return {
        key: _ensure_face_payload(face_map.get(key, {"patternId": "?", "rotation": 0}))
        for key in REQUIRED_FACE_KEYS
    }


def task_json_to_catalog_entry(task: dict[str, Any]) -> dict[str, Any]:
    metadata = task.get("metadata", {}) or {}
    sample_id = str(task.get("sample_id"))
    answer = task.get("answer", {}) if isinstance(task.get("answer"), dict) else {}
    solution_face_map = answer.get("faces") or task.get("legacy_answer") or {}

    bottom_faces = [
        {
            "patternId": str(face.get("patternId", "?")),
            "rotation": int(face.get("rotation", 0)),
            "flipHorizontal": bool(face.get("flipHorizontal", False)),
            "flipVertical": bool(face.get("flipVertical", False)),
            "x": int(face.get("x", 0)),
            "y": int(face.get("y", 0)),
        }
        for face in task.get("bottom_faces", [])
    ]

    net_faces = [_ensure_face_payload(face) for face in task.get("net_faces", [])]

    observed_path_faces = [
        _ensure_face_payload(face) for face in task.get("observed_path_faces", [])
    ]

    return {
        "id": int(metadata.get("level_id", 0)),
        "code": sample_id,
        "name": str(metadata.get("name", sample_id)),
        "mode": "reconstruct",
        "description": str(task.get("description", "")),
        "difficulty": int(metadata.get("difficulty", 0)),
        "moveCount": int(metadata.get("move_count", len(task.get("roll_sequence", [])))),
        "tier": int(metadata.get("tier", 0)),
        "tierLabel": str(metadata.get("tier_label", f"Difficulty {metadata.get('tier', '?')}")),
        "sourceFile": str(metadata.get("source_level_path", "")),
        "netLayout": str(task.get("net_layout", "standard_cross")),
        "netPatterns": list(task.get("net_patterns", [])),
        "path": list(task.get("roll_sequence", [])),
        "startX": int(task.get("start_x", 0)),
        "startY": int(task.get("start_y", 0)),
        "gridWidth": int(task.get("grid_width", 0)),
        "gridHeight": int(task.get("grid_height", 0)),
        "netFaces": net_faces,
        "gtBottomFaces": bottom_faces,
        "solutionFaces": _ensure_face_map(solution_face_map),
        "trueSolutionFaces": _ensure_face_map(task.get("true_solution_faces")),
        "prompt": {
            "directions": list(task.get("roll_sequence", [])),
            "observedPathFaces": observed_path_faces,
            "slotSequence": list(task.get("slot_sequence", [])),
            "requiredSlots": list(task.get("required_slots", [])),
            "requiredCount": int(task.get("required_count", 0)),
        },
        "answers": {
            "solutionFaces": _ensure_face_map(solution_face_map),
            "trueSolutionFaces": _ensure_face_map(task.get("true_solution_faces")),
            "bottomFaces": bottom_faces,
        },
    }


def build_catalog(tasks_dir: Path) -> dict[str, Any]:
    paths = sorted(tasks_dir.glob("*.json"))
    levels: list[dict[str, Any]] = []
    for path in paths:
        if path.name in {"model_summary.json", "sample_manifest.json", "manifest.json", "index.json"}:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        levels.append(task_json_to_catalog_entry(payload))

    levels.sort(key=lambda level: (level.get("id", 0), level.get("code", "")))

    groups: list[dict[str, Any]] = []
    for group_def in GROUPS_DEFINITION:
        count = sum(
            1
            for level in levels
            if group_def["minMoves"] <= int(level.get("moveCount", 0)) <= group_def["maxMoves"]
        )
        groups.append({**group_def, "count": count})

    return {
        "version": CATALOG_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "modes": {
            "reconstruct": {
                "groups": groups,
                "levels": levels,
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate cube1 frontend catalog from per-level task JSONs.")
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Build the catalog in memory but do not write it.")
    args = parser.parse_args()

    catalog = build_catalog(args.tasks_dir)
    levels = catalog["modes"]["reconstruct"]["levels"]
    suffix = " (dry run)" if args.dry_run else ""
    print(f"Built catalog with {len(levels)} levels{suffix}")
    for group in catalog["modes"]["reconstruct"]["groups"]:
        print(f"  {group['key']}: count={group['count']} (moves {group['minMoves']}..{group['maxMoves']})")

    if args.dry_run:
        return

    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    args.catalog.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.catalog}")


if __name__ == "__main__":
    main()
