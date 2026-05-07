"""Migrate cube1/data/task_jsons/*.json to the SimVerse v1 answer schema.

Before:
    {
        ...
        "answer": {
            "TOP":    {"patternId": "...", "rotation": ...},
            "BOTTOM": {"patternId": "...", "rotation": ...},
            ...
        }
    }

After:
    {
        ...
        "answer": {
            "faces": {
                "TOP":    {"patternId": "...", "rotation": ...},
                ...
            }
        },
        "legacy_answer": { /* the original face map */ }
    }

Run:
    python cube1/eval-thinking/migrate_dataset.py
    python cube1/eval-thinking/migrate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_DIR = PROJECT_ROOT / "data" / "task_jsons"

REQUIRED_FACE_KEYS = ("TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT")


def migrate_one(payload: dict) -> tuple[bool, dict]:
    answer = payload.get("answer")
    if not isinstance(answer, dict):
        return False, payload

    # Already migrated?
    if "faces" in answer and set(answer.keys()) == {"faces"}:
        return False, payload

    # Detect a flat face map: keys equal the canonical face names.
    if all(face_key in answer for face_key in REQUIRED_FACE_KEYS):
        legacy = {face_key: dict(answer[face_key]) for face_key in REQUIRED_FACE_KEYS}
        new_payload = dict(payload)
        new_payload["answer"] = {"faces": legacy}
        new_payload["legacy_answer"] = legacy
        return True, new_payload

    return False, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate cube1 dataset to v1 answer schema.")
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(args.tasks_dir.glob("*.json"))
    changed = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        modified, new_payload = migrate_one(payload)
        if not modified:
            continue
        changed += 1
        if args.dry_run:
            continue
        path.write_text(
            json.dumps(new_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    suffix = " (dry run)" if args.dry_run else ""
    print(f"Migrated {changed}/{len(paths)} files{suffix}")


if __name__ == "__main__":
    main()
