"""Migrate VOI/data/levels/voi-*.json to the SimVerse v1 answer schema.

Before:
    {
        ...
        "answer": "S1 180 V2 [4,2]\\nS2 90 V3 [5,2]"
    }

After:
    {
        ...
        "answer": {
            "placements": [
                {"shape": "S1", "angle": 180, "vertex": "V2", "grid": [4, 2]},
                {"shape": "S2", "angle":  90, "vertex": "V3", "grid": [5, 2]}
            ]
        },
        "legacy_answer": "S1 180 V2 [4,2]\\nS2 90 V3 [5,2]",
        "solutionText": "S1 180 V2 [4,2]\\nS2 90 V3 [5,2]"
    }

`solutionText` is recreated from placements so the existing pixel engine (which
internally reads `level_data["solutionText"]` for the reference mask) keeps
working without modification.

Run:
    python VOI/eval/migrate_dataset.py
    python VOI/eval/migrate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEVELS_DIR = PROJECT_ROOT / "data" / "levels"

DSL_LINE_PATTERN = re.compile(
    r"^\s*([A-Za-z][\w-]*)\s+(0|90|180|270)\s+(V\d+)\s+\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]\s*$"
)


def parse_dsl_lines(text: str) -> list[dict[str, Any]]:
    placements: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = DSL_LINE_PATTERN.match(line)
        if not match:
            raise ValueError(f"Cannot parse DSL line: {raw_line!r}")
        shape_id, angle_text, vertex_id, grid_x_text, grid_y_text = match.groups()
        placements.append({
            "shape": shape_id,
            "angle": int(angle_text),
            "vertex": vertex_id,
            "grid": [int(grid_x_text), int(grid_y_text)],
        })
    if not placements:
        raise ValueError("No valid DSL lines found.")
    return placements


def placements_to_dsl(placements: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{p['shape']} {p['angle']} {p['vertex']} [{p['grid'][0]},{p['grid'][1]}]"
        for p in placements
    )


def migrate_one(payload: dict) -> tuple[bool, dict]:
    answer = payload.get("answer")

    # Already migrated?
    if isinstance(answer, dict) and isinstance(answer.get("placements"), list):
        return False, payload

    if not isinstance(answer, str) or not answer.strip():
        return False, payload

    placements = parse_dsl_lines(answer)
    new_payload = dict(payload)
    new_payload["answer"] = {"placements": placements}
    new_payload["legacy_answer"] = answer
    new_payload["solutionText"] = placements_to_dsl(placements)
    return True, new_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate VOI dataset to v1 answer schema.")
    parser.add_argument("--levels-dir", type=Path, default=DEFAULT_LEVELS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(args.levels_dir.glob("voi-*.json"))
    if not paths:
        # Older naming used level001.json — handle both.
        paths = sorted(args.levels_dir.glob("level*.json"))
    changed = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            modified, new_payload = migrate_one(payload)
        except ValueError as exc:
            print(f"  ! {path.name}: {exc}")
            continue
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
