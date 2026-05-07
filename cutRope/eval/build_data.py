from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from eval_common import DEFAULT_DATA_DIR, PROJECT_ROOT


LEVELS_DIR = PROJECT_ROOT / "data" / "task"
VIDEOS_DIR = PROJECT_ROOT / "data" / "video"

OBJECT_NAMES = {
    2: "target",
    3: "star",
    50: "left_candy",
    51: "right_candy",
    52: "candy",
    53: "gravity_button",
    54: "bubble",
    55: "pump",
    56: "sock",
    57: "spike",
    58: "spike",
    59: "spike",
    60: "spike",
    81: "bouncer",
    82: "bouncer",
    100: "grab_or_rope_anchor",
    120: "turntable",
    121: "target",
    122: "candy",
    130: "ghost",
    131: "steam_tube",
    132: "lantern",
    133: "mouse",
    134: "light_bulb",
    135: "conveyor_belt",
}

SOLUTION_FIELDS = {
    "textCommandSolution",
    "textCommandSolutionUpdatedAt",
    "textCommandSolutionStars",
    "textCommandSolutionWon",
}


def relative_to_project(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def summarize_level(level: dict[str, Any]) -> dict[str, Any]:
    objects = level.get("objects", [])
    settings = level.get("settings", [])
    map_settings = next((item for item in settings if item.get("name") == 0), {})
    game_design = next((item for item in settings if item.get("name") == 1), {})

    counter: Counter[str] = Counter()
    for item in objects:
        raw_name = item.get("name")
        object_name = OBJECT_NAMES.get(raw_name, f"object_{raw_name}")
        counter[object_name] += 1

    return {
        "canvas_width": 1920,
        "canvas_height": 1080,
        "map_width": map_settings.get("width"),
        "map_height": map_settings.get("height"),
        "two_parts": bool(game_design.get("twoParts")),
        "special": game_design.get("special"),
        "object_counts": dict(sorted(counter.items())),
    }


def sanitize_level(level: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in level.items() if key not in SOLUTION_FIELDS}


def build_eval_item(level_path: Path, video_path: Path) -> dict[str, Any]:
    level = json.loads(level_path.read_text(encoding="utf-8"))
    reference_solution = level.get("textCommandSolution", "")
    video = {
        "path": relative_to_project(video_path),
        "mime_type": "video/mp4",
        "duration_seconds": 3,
        "fps": 30,
    }

    return {
        "schema_version": 1,
        "level_id": level_path.stem,
        "level_file": relative_to_project(level_path),
        "video": video,
        "prompt_level": summarize_level(level),
        "level_json_without_solution": sanitize_level(level),
        "reference_solution": reference_solution,
        "reference": {
            "won": level.get("textCommandSolutionWon"),
            "stars": level.get("textCommandSolutionStars"),
            "updated_at": level.get("textCommandSolutionUpdatedAt"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build eval/data items from level JSON and recorded MP4 videos.")
    parser.add_argument("--levels-dir", type=Path, default=LEVELS_DIR)
    parser.add_argument("--videos-dir", type=Path, default=VIDEOS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing eval data JSON files.")
    args = parser.parse_args()

    level_paths = sorted(p for p in args.levels_dir.glob("*.json") if p.name != "manifest.json")
    if args.limit is not None:
        level_paths = level_paths[: args.limit]
    if not level_paths:
        raise SystemExit(f"No level JSON files found in {args.levels_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_levels: list[dict[str, Any]] = []
    missing_videos: list[str] = []
    written = 0

    for level_path in level_paths:
        video_path = args.videos_dir / f"{level_path.stem}.mp4"
        if not video_path.exists():
            missing_videos.append(str(video_path))
            continue

        out_path = args.out_dir / f"{level_path.stem}.json"
        if out_path.exists() and not args.force:
            raise SystemExit(f"{out_path} already exists. Pass --force to overwrite.")

        item = build_eval_item(level_path, video_path)
        out_path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_levels.append(
            {
                "level_id": item["level_id"],
                "data_file": relative_to_project(out_path),
                "level_file": item["level_file"],
                "video_file": item["video"]["path"],
            }
        )
        written += 1

    if missing_videos:
        raise SystemExit("Missing video files:\n" + "\n".join(missing_videos[:20]))

    manifest = {
        "schema_version": 1,
        "data_dir": relative_to_project(args.out_dir),
        "levels": manifest_levels,
    }
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {written} eval data files to {args.out_dir}")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
