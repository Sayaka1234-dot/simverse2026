"""Embed the per-level system + user prompt text into each cutRope eval JSON.

Adds a top-level field:
    "prompt": {"system": "...", "user": "..."}

Run:
    python cutRope/eval/populate_prompts.py
    python cutRope/eval/populate_prompts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from prompts import _construct_system_prompt, _construct_user_prompt  # noqa: E402

DEFAULT_DATA_DIR = CURRENT_DIR / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed prompt text into cutRope eval JSONs.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = sorted(p for p in args.data_dir.glob("rope-*.json") if p.name != "manifest.json")
    system_text = _construct_system_prompt()
    updated = 0
    unchanged = 0

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        user_text = _construct_user_prompt(payload)
        new_prompt = {"system": system_text, "user": user_text}
        existing = payload.get("prompt")
        if isinstance(existing, dict) and existing.get("system") == system_text and existing.get("user") == user_text:
            unchanged += 1
            continue
        payload["prompt"] = new_prompt
        updated += 1
        if args.dry_run:
            continue
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    suffix = " (dry run)" if args.dry_run else ""
    print(f"Embedded prompt: {updated} updated, {unchanged} unchanged of {len(paths)} files{suffix}")


if __name__ == "__main__":
    main()
