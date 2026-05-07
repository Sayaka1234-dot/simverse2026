"""Migrate cutRope/eval/data/rope-*.json to the SimVerse v1 answer schema.

Before:
    {
        ...
        "reference_solution": "cut_rope 2\\npop_bubble 3\\n...",
        "reference": {"won": true, "stars": 3, "updated_at": "..."}
    }

After:
    {
        ...
        "reference_solution": "...",     # kept for build pipeline back-compat
        "reference": {...},              # kept
        "answer": {
            "commands": "cut_rope 2\\npop_bubble 3\\n...",
            "reason": "reference solution",
            "confidence": 1.0
        },
        "legacy_answer": "..."           # snapshot of reference_solution at migration time
    }

Run:
    python cutRope/eval/migrate_dataset.py
    python cutRope/eval/migrate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = EVAL_ROOT / "data"


def migrate_one(payload: dict) -> tuple[bool, dict]:
    answer = payload.get("answer")
    if isinstance(answer, dict) and isinstance(answer.get("commands"), str):
        return False, payload

    reference_solution = payload.get("reference_solution")
    if not isinstance(reference_solution, str) or not reference_solution.strip():
        return False, payload

    new_payload = dict(payload)
    new_payload["answer"] = {
        "commands": reference_solution,
        "reason": "reference solution",
        "confidence": 1.0,
    }
    new_payload["legacy_answer"] = reference_solution
    return True, new_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate cutRope eval dataset to v1 answer schema.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(p for p in args.data_dir.glob("*.json") if p.name != "manifest.json")
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
