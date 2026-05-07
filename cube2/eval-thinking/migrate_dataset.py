"""Migrate cube2/data2/task_jsons/*.json to the SimVerse v1 answer schema.

Before:
    {
        ...
        "rollSequence": ["N", "E", "S"],
        "answer": {                       # legacy face-map; irrelevant to goal-roll task
            "TOP": {...}, "BOTTOM": {...}, ...
        },
        "answers": {"directions": [], "moveCount": 0, "referenceValid": false}
    }

After:
    {
        ...
        "rollSequence": ["N", "E", "S"],
        "answer": {"directions": ["N", "E", "S"]},
        "legacy_answer": {                # old face-map preserved for one cycle
            "TOP": {...}, ...
        }
    }

Cube2 is open-ended: any direction sequence that produces the target top face is
valid. `answer.directions` carries one known-valid reference sequence drawn from
`rollSequence`; the validator confirms a model answer by simulating the engine,
not by string equality.

Run:
    python cube2/eval-thinking/migrate_dataset.py
    python cube2/eval-thinking/migrate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_DIR = PROJECT_ROOT / "data2" / "task_jsons"
VALID_DIRECTIONS = {"N", "S", "E", "W"}


def migrate_one(payload: dict) -> tuple[bool, dict]:
    answer = payload.get("answer")

    # Already migrated?
    if isinstance(answer, dict) and isinstance(answer.get("directions"), list) and len(answer) == 1:
        return False, payload

    # Pull a reference sequence from the existing data.
    candidates: list[Any] = [
        payload.get("rollSequence"),
        payload.get("answers", {}).get("directions") if isinstance(payload.get("answers"), dict) else None,
    ]
    directions: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, list):
            normalized = [str(item).strip().upper() for item in candidate if str(item).strip()]
            if all(d in VALID_DIRECTIONS for d in normalized) and normalized:
                directions = normalized
                break

    if not directions:
        # Cube2 has no usable reference — store an empty list to keep schema shape.
        directions = []

    new_payload = dict(payload)
    if isinstance(answer, dict) and "directions" not in answer:
        new_payload["legacy_answer"] = answer
    new_payload["answer"] = {"directions": directions}
    return True, new_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate cube2 dataset to v1 answer schema.")
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
