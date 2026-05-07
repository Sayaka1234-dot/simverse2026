"""Download SimVerse data from HuggingFace into the local task directories
where the eval pipeline and frontend demos expect them.

The repo's code is on GitHub; the bulky data + media live on HuggingFace
(see https://huggingface.co/datasets/SimVer-ano/simverse2026, anonymized for
double-blind review). After `git clone`, run this script once to populate
each task's `data/` directory.

Usage:
    pip install -U huggingface_hub
    python scripts/download_dataset.py                  # all 5 tasks
    python scripts/download_dataset.py --tasks lamp voi # subset
    python scripts/download_dataset.py --revision main  # pin a specific HF revision
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_REPO_ID = "SimVer-ano/simverse2026"

# Per-task mapping from HF download paths -> local destination paths.
#
# These mappings are the inverse of the upload layout produced by
# scripts/package_for_hf.py. The HF repo restructures the local source tree
# into a per-config layout (HF wants `<config>/data/`, `<config>/images/`, etc.);
# this script puts everything back where the eval pipelines and frontend demos
# expect it locally.
TASK_LAYOUTS = {
    "voi": [
        ("voi/data", PROJECT_ROOT / "VOI" / "data" / "levels"),
        ("voi/images", PROJECT_ROOT / "VOI" / "data" / "images"),
    ],
    "cube1": [
        ("cube1/data", PROJECT_ROOT / "cube1" / "data" / "task_jsons"),
        ("cube1/images", PROJECT_ROOT / "cube1" / "data" / "images"),
        ("cube1/catalog.json", PROJECT_ROOT / "cube1" / "levels" / "index.json"),
    ],
    "cube2": [
        ("cube2/data", PROJECT_ROOT / "cube2" / "data2" / "task_jsons"),
        ("cube2/images", PROJECT_ROOT / "cube2" / "images"),
        ("cube2/catalog.json", PROJECT_ROOT / "cube2" / "data2" / "index.json"),
    ],
    "lamp": [
        ("lamp/data", PROJECT_ROOT / "lamp" / "data" / "levels"),
        ("lamp/images", PROJECT_ROOT / "lamp" / "data" / "images"),
    ],
    "cutrope": [
        # `cutrope/data` on HF == eval format (carries `prompt_level` etc.) —
        # this is what the eval pipeline reads.
        ("cutrope/data", PROJECT_ROOT / "cutRope" / "eval" / "data"),
        # `cutrope/source` on HF == frontend-format level files — this is what
        # the vite middleware bridges to `/data/boxes/levels/` for the demo.
        ("cutrope/source", PROJECT_ROOT / "cutRope" / "data" / "task"),
        # MP4 videos for both eval and frontend.
        ("cutrope/videos", PROJECT_ROOT / "cutRope" / "data" / "video"),
    ],
}


def _import_hf_hub():
    try:
        from huggingface_hub import snapshot_download  # noqa: WPS433
        return snapshot_download
    except ImportError as exc:  # pragma: no cover
        sys.stderr.write(
            "huggingface_hub is required. Install with:\n"
            "    pip install -U huggingface_hub\n"
        )
        raise SystemExit(1) from exc


def _mirror_directory(src: Path, dest: Path) -> int:
    """Copy every file from `src` (recursively) into `dest`. Returns count."""
    if not src.exists():
        sys.stderr.write(f"  WARN: HF source missing: {src}\n")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    if src.is_file():
        shutil.copy2(src, dest)
        return 1
    for item in src.rglob("*"):
        if item.is_dir():
            (dest / item.relative_to(src)).mkdir(parents=True, exist_ok=True)
            continue
        target = dest / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Download SimVerse data from HuggingFace.")
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help=f"HF dataset repo id. Default: {DEFAULT_REPO_ID}",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="HF revision (branch / tag / commit). Default: main",
    )
    parser.add_argument(
        "--tasks",
        nargs="*",
        default=list(TASK_LAYOUTS.keys()),
        choices=list(TASK_LAYOUTS.keys()),
        help="Which tasks to download. Default: all.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="HF cache dir override; defaults to ~/.cache/huggingface/hub.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without copying.",
    )
    args = parser.parse_args()

    # Dry-run is fully offline: we only print the planned mappings, never
    # touch the network or filesystem.
    if args.dry_run:
        print(
            f"[dry run] Would download {args.repo_id}@{args.revision} "
            f"for tasks: {', '.join(args.tasks)}"
        )
        for task in args.tasks:
            print(f"\n--- {task} ---")
            for hf_subpath, local_dest in TASK_LAYOUTS[task]:
                rel_dest = local_dest.relative_to(PROJECT_ROOT)
                print(f"  {hf_subpath:<24} ->  {rel_dest}")
        print(
            "\n[dry run] no network access performed; no files copied. "
            "Re-run without --dry-run to actually download."
        )
        return

    snapshot_download = _import_hf_hub()

    # Build allow-patterns to skip media we won't use (savings on download).
    allow = []
    for task in args.tasks:
        allow.append(f"{task}/**")

    print(f"Downloading {args.repo_id}@{args.revision} for tasks: {', '.join(args.tasks)}")
    snapshot = snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
        cache_dir=str(args.cache_dir) if args.cache_dir else None,
        allow_patterns=allow + [
            "README.md",
            "LICENSE",
            "croissant.json",
            "datasheet.md",
            "*/README.md",
        ],
    )
    snapshot_root = Path(snapshot)
    print(f"HF snapshot: {snapshot_root}")

    total = 0
    for task in args.tasks:
        print(f"\n--- {task} ---")
        for hf_subpath, local_dest in TASK_LAYOUTS[task]:
            src = snapshot_root / hf_subpath
            print(f"  {hf_subpath:<30} -> {local_dest.relative_to(PROJECT_ROOT)}")
            count = _mirror_directory(src, local_dest)
            total += count
            print(f"     copied {count} files")

    suffix = " (dry run)" if args.dry_run else ""
    print(f"\nDone. Total files written: {total}{suffix}")
    print(
        "\nNext steps:\n"
        "  1. Verify each task's data: ls VOI/data/levels | head\n"
        "  2. Re-run prompts (idempotent, in case templates changed):\n"
        "       python lamp/eval-thinking/populate_prompts.py\n"
        "       python cube1/eval-thinking/populate_prompts.py\n"
        "       python cube2/eval-thinking/populate_prompts.py\n"
        "       python VOI/eval/populate_prompts.py\n"
        "       python cutRope/eval/populate_prompts.py\n"
        "  3. Run an eval: python lamp/eval-thinking/eval_local.py ../data/levels/lamp-000.json\n"
    )


if __name__ == "__main__":
    main()
