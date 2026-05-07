"""Migrate lamp/data/levels/lamp-*.json to the SimVerse v1 answer schema.

Before:
    {
        ...
        "arm": {
            ...
            "answer": [-60, -135, 140, -15, 165]
        }
    }

After:
    {
        ...
        "arm": {
            ...                        # arm.answer removed
        },
        "answer": {
            "actions": [
                {"joint": 1, "angle": -60},
                {"joint": 2, "angle": -135},
                {"joint": 3, "angle":  140},
                {"joint": 4, "angle":  -15},
                {"joint": 5, "angle":  165}
            ]
        },
        "legacy_answer": [-60, -135, 140, -15, 165]
    }

Run from anywhere:
    python lamp/eval-thinking/migrate_dataset.py
    python lamp/eval-thinking/migrate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEVELS_DIR = PROJECT_ROOT / "data" / "levels"


def migrate_one(payload: dict) -> tuple[bool, dict]:
    arm = payload.get("arm")
    if not isinstance(arm, dict):
        return False, payload

    existing_answer = payload.get("answer")
    if isinstance(existing_answer, dict) and isinstance(existing_answer.get("actions"), list):
        return False, payload

    legacy_answer = arm.get("answer")
    if not isinstance(legacy_answer, list):
        return False, payload

    actions = [
        {"joint": index + 1, "angle": int(round(float(angle)))}
        for index, angle in enumerate(legacy_answer)
    ]
    new_payload = dict(payload)
    new_payload["answer"] = {"actions": actions}
    new_payload["legacy_answer"] = list(legacy_answer)
    new_arm = dict(arm)
    new_arm.pop("answer", None)
    new_payload["arm"] = new_arm
    return True, new_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate lamp dataset to v1 answer schema.")
    parser.add_argument("--levels-dir", type=Path, default=DEFAULT_LEVELS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(args.levels_dir.glob("lamp-*.json"))
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
