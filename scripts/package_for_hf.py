"""Assemble the SimVerse HuggingFace upload bundle in `hf_dataset/`.

Layout produced (per task config):
    hf_dataset/
    ├── README.md                   <-- written manually; this script never overwrites it
    ├── LICENSE                     <-- written manually
    ├── voi/
    │   ├── test.jsonl             <-- one record per level, image paths normalized
    │   ├── data/                   <-- per-level JSONs + per-level image dirs (mirror)
    │   └── README.md               <-- written manually
    ├── cube1/  (same shape, plus catalog.json + flat images/ tree)
    ├── cube2/  (same shape, plus catalog.json)
    ├── lamp/   (same shape, flat data/ + flat images/)
    └── cutrope/(same shape, plus source/ for frontend levels and videos/)

Hardlinks are used by default to avoid duplicating ~350MB of media; falls back
to copy when hardlink fails (e.g. cross-volume or read-only target).

Re-running is destructive *only* for the per-task `data/`, `images/`, `videos/`,
`source/`, `catalog.json`, and `test.jsonl` files. The repo-root `README.md`,
`LICENSE`, and per-task `README.md` are NEVER touched by this script — those
stay editable.

Run:
    python scripts/package_for_hf.py
    python scripts/package_for_hf.py --tasks lamp cube1
    python scripts/package_for_hf.py --copy           # force real file copies
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "hf_dataset"


def _link_or_copy(src: Path, dst: Path, *, copy_only: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    if copy_only:
        shutil.copy2(src, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def mirror_tree(src_root: Path, dst_root: Path, *, copy_only: bool) -> int:
    """Hardlink (or copy) every regular file under src_root into dst_root, preserving
    the relative path. Returns the number of files placed."""
    if not src_root.exists():
        raise FileNotFoundError(f"Source missing: {src_root}")
    placed = 0
    for src in src_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        _link_or_copy(src, dst, copy_only=copy_only)
        placed += 1
    return placed


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


# ---------- per-task packagers ----------

@dataclass
class TaskBundle:
    name: str
    description: str
    pack: Callable[..., dict[str, int]]


def _load_level_files(directory: Path, glob: str = "*.json", *, exclude_names: set[str] = frozenset()) -> list[Path]:
    return sorted(
        p for p in directory.glob(glob)
        if p.is_file() and p.name not in exclude_names
    )


# --- voi -------------------------------------------------------------------

def pack_voi(out_root: Path, *, copy_only: bool) -> dict[str, int]:
    """VOI: data/levels/voi-*.json + data/images/voi-XXX/{target.png,shape_*.png}.
    HF layout: hf_dataset/voi/data/ mirrors data/levels/ AND
    hf_dataset/voi/images/ mirrors data/images/. Image paths inside the level
    JSONs (e.g. "../images/voi-000/target.png") still resolve correctly because
    the relative ../images/ traversal lands inside hf_dataset/voi/images/."""
    src_levels = PROJECT_ROOT / "VOI" / "data" / "levels"
    src_images = PROJECT_ROOT / "VOI" / "data" / "images"
    dst_dir = out_root / "voi"
    dst_data = dst_dir / "data"
    dst_images = dst_dir / "images"

    clean_dir(dst_data)
    clean_dir(dst_images)
    placed_data = mirror_tree(src_levels, dst_data, copy_only=copy_only)
    placed_images = mirror_tree(src_images, dst_images, copy_only=copy_only) if src_images.exists() else 0

    # Build test.jsonl from the per-level JSONs we just placed.
    level_paths = _load_level_files(dst_data, "voi-*.json", exclude_names={"manifest.json"})
    records: list[dict[str, Any]] = []

    def _normalize_voi_image_path(rel: str | None) -> str | None:
        # Convert "../images/voi-000/target.png" (relative to data/levels/<file>)
        # to "images/voi-000/target.png" (relative to the config root voi/).
        if not rel:
            return rel
        return _normalize_dotdot(rel)

    for path in level_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        image_assets = payload.get("imageAssets", {}) or {}
        normalized_images = {
            "target": _normalize_voi_image_path(image_assets.get("target")),
            "shapes": {
                shape_id: _normalize_voi_image_path(relative)
                for shape_id, relative in (image_assets.get("shapes") or {}).items()
            },
        }
        record = dict(payload)
        record["images_relative_to_config"] = normalized_images
        record["__sample_id__"] = payload.get("ID") or path.stem
        records.append(record)
    written = write_jsonl(records, dst_dir / "test.jsonl")
    return {"files_mirrored": placed_data + placed_images, "test.jsonl": written}


# --- cube1 -----------------------------------------------------------------

def pack_cube1(out_root: Path, *, copy_only: bool) -> dict[str, int]:
    """cube1: data/task_jsons/ -> data/, data/images/ -> images/,
    levels/index.json -> catalog.json. Image paths in test.jsonl are unchanged
    (they already start with `images/` which matches the HF layout)."""
    src_tasks = PROJECT_ROOT / "cube1" / "data" / "task_jsons"
    src_images = PROJECT_ROOT / "cube1" / "data" / "images"
    src_catalog = PROJECT_ROOT / "cube1" / "levels" / "index.json"
    dst_dir = out_root / "cube1"
    dst_data = dst_dir / "data"
    dst_images = dst_dir / "images"
    dst_catalog = dst_dir / "catalog.json"

    clean_dir(dst_data)
    clean_dir(dst_images)
    if dst_catalog.exists():
        dst_catalog.unlink()

    placed_data = mirror_tree(src_tasks, dst_data, copy_only=copy_only)
    placed_images = mirror_tree(src_images, dst_images, copy_only=copy_only)
    _link_or_copy(src_catalog, dst_catalog, copy_only=copy_only)

    level_paths = _load_level_files(
        dst_data, "*.json",
        exclude_names={"manifest.json", "index.json", "model_summary.json", "sample_manifest.json"}
    )
    records: list[dict[str, Any]] = []
    for path in level_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Existing image_paths fields like "images/blank_nets/open.png" are
        # already relative to cube1/data/, which is now hf_dataset/cube1/.
        # No rewrite needed — they resolve from the config dir.
        record = dict(payload)
        record["__sample_id__"] = payload.get("sample_id") or path.stem
        records.append(record)
    written = write_jsonl(records, dst_dir / "test.jsonl")
    return {"files_mirrored": placed_data + placed_images + 1, "test.jsonl": written}


# --- cube2 -----------------------------------------------------------------

def pack_cube2(out_root: Path, *, copy_only: bool) -> dict[str, int]:
    """cube2: data2/task_jsons/ -> data/, images/ -> images/,
    data2/index.json -> catalog.json. Image paths in JSON like
    "../images/C001/initial_net.png" are rewritten to "images/C001/initial_net.png"."""
    src_tasks = PROJECT_ROOT / "cube2" / "data2" / "task_jsons"
    src_images = PROJECT_ROOT / "cube2" / "images"
    src_catalog = PROJECT_ROOT / "cube2" / "data2" / "index.json"
    dst_dir = out_root / "cube2"
    dst_data = dst_dir / "data"
    dst_images = dst_dir / "images"
    dst_catalog = dst_dir / "catalog.json"

    clean_dir(dst_data)
    clean_dir(dst_images)
    if dst_catalog.exists():
        dst_catalog.unlink()

    placed_data = mirror_tree(src_tasks, dst_data, copy_only=copy_only)
    placed_images = mirror_tree(src_images, dst_images, copy_only=copy_only)
    placed_catalog = 0
    if src_catalog.exists():
        _link_or_copy(src_catalog, dst_catalog, copy_only=copy_only)
        placed_catalog = 1

    level_paths = _load_level_files(
        dst_data, "*.json",
        exclude_names={"manifest.json", "index.json", "model_summary.json", "sample_manifest.json"}
    )
    records: list[dict[str, Any]] = []
    for path in level_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Rewrite imagePaths from "../images/..." to "images/..."
        image_paths = payload.get("imagePaths", {}) or {}
        normalized = {
            "initialNetImage": _normalize_dotdot(image_paths.get("initialNetImage")),
            "targetTopFaceImage": _normalize_dotdot(image_paths.get("targetTopFaceImage")),
        }
        record = dict(payload)
        record["images_relative_to_config"] = normalized
        record["__sample_id__"] = payload.get("code") or payload.get("sample_id") or path.stem
        records.append(record)
    written = write_jsonl(records, dst_dir / "test.jsonl")
    return {"files_mirrored": placed_data + placed_images + placed_catalog, "test.jsonl": written}


def _normalize_dotdot(rel: str | None) -> str | None:
    if not rel:
        return rel
    # "../images/X" -> "images/X"
    parts = rel.replace("\\", "/").split("/")
    parts = [p for p in parts if p and p != ".."]
    return "/".join(parts)


# --- lamp ------------------------------------------------------------------

def pack_lamp(out_root: Path, *, copy_only: bool) -> dict[str, int]:
    """lamp: data/levels/ -> data/, data/images/ -> images/. Image paths in
    test.jsonl are derived from the level id."""
    src_levels = PROJECT_ROOT / "lamp" / "data" / "levels"
    src_images = PROJECT_ROOT / "lamp" / "data" / "images"
    dst_dir = out_root / "lamp"
    dst_data = dst_dir / "data"
    dst_images = dst_dir / "images"

    clean_dir(dst_data)
    clean_dir(dst_images)

    placed_data = mirror_tree(src_levels, dst_data, copy_only=copy_only)
    placed_images = mirror_tree(src_images, dst_images, copy_only=copy_only) if src_images.exists() else 0

    level_paths = _load_level_files(dst_data, "lamp-*.json", exclude_names={"manifest.json"})
    records: list[dict[str, Any]] = []
    for path in level_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        sample_id = payload.get("id") or path.stem
        record = dict(payload)
        record["images_relative_to_config"] = {"image": f"images/{sample_id}.png"}
        record["__sample_id__"] = sample_id
        records.append(record)
    written = write_jsonl(records, dst_dir / "test.jsonl")
    return {"files_mirrored": placed_data + placed_images, "test.jsonl": written}


# --- cutrope ---------------------------------------------------------------

def pack_cutrope(out_root: Path, *, copy_only: bool) -> dict[str, int]:
    """cutRope: eval/data/ -> data/, data/task/ -> source/, data/video/ -> videos/.
    Video paths in JSON like 'data/video/rope-000.mp4' are rewritten to
    'videos/rope-000.mp4'. The frontend-friendly 'source/' tree is also shipped."""
    src_eval = PROJECT_ROOT / "cutRope" / "eval" / "data"
    src_source = PROJECT_ROOT / "cutRope" / "data" / "task"
    src_videos = PROJECT_ROOT / "cutRope" / "data" / "video"
    dst_dir = out_root / "cutrope"
    dst_data = dst_dir / "data"
    dst_source = dst_dir / "source"
    dst_videos = dst_dir / "videos"

    clean_dir(dst_data)
    clean_dir(dst_source)
    clean_dir(dst_videos)

    placed_data = mirror_tree(src_eval, dst_data, copy_only=copy_only)
    placed_source = mirror_tree(src_source, dst_source, copy_only=copy_only)
    placed_videos = mirror_tree(src_videos, dst_videos, copy_only=copy_only)

    level_paths = _load_level_files(dst_data, "rope-*.json", exclude_names={"manifest.json"})
    records: list[dict[str, Any]] = []
    for path in level_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Rewrite video paths from "data/video/<file>" to "videos/<file>"
        video_info = payload.get("video", {}) or {}
        original_video_path = video_info.get("path", "")
        normalized_path = (
            "videos/" + Path(original_video_path).name
            if original_video_path else original_video_path
        )
        record = dict(payload)
        record["video_relative_to_config"] = {
            "path": normalized_path,
            "mime_type": video_info.get("mime_type", "video/mp4"),
        }
        record["__sample_id__"] = payload.get("level_id") or path.stem
        records.append(record)
    written = write_jsonl(records, dst_dir / "test.jsonl")
    return {
        "files_mirrored": placed_data + placed_source + placed_videos,
        "test.jsonl": written,
    }


TASKS: dict[str, TaskBundle] = {
    "voi":     TaskBundle("voi",     "Text-VOI spatial logic puzzle (placements)",     pack_voi),
    "cube1":   TaskBundle("cube1",   "Cube reconstruction (six-face map)",             pack_cube1),
    "cube2":   TaskBundle("cube2",   "Cube goal-roll (top-face directions)",           pack_cube2),
    "lamp":    TaskBundle("lamp",    "Mechanical-arm lamp targeting (joint angles)",   pack_lamp),
    "cutrope": TaskBundle("cutrope", "Cut the Rope video-to-command",                  pack_cutrope),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble SimVerse HF upload bundle.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tasks", nargs="*", choices=sorted(TASKS.keys()), default=None,
                        help="Subset of tasks to repack. Default: all.")
    parser.add_argument("--copy", action="store_true",
                        help="Force real file copies instead of hardlinks.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    selected = args.tasks or sorted(TASKS.keys())
    print(f"Packaging {len(selected)} task(s) into {args.out}")
    if args.copy:
        print("Mode: full copy")
    else:
        print("Mode: hardlinks (auto-fallback to copy)")
    print()

    for name in selected:
        bundle = TASKS[name]
        print(f"--- {bundle.name}: {bundle.description}")
        result = bundle.pack(args.out, copy_only=args.copy)
        for key, value in result.items():
            print(f"  {key}: {value}")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
