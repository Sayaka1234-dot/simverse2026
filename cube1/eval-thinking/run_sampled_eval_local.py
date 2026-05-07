from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import eval_local
from eval_common import (
    DEFAULT_MODEL_NAME,
    TASK_JSON_ROOT,
    build_result_namespace,
    get_results_dir,
    load_task_json,
)


DEFAULT_TOTAL = 100
DEFAULT_SEED = 20260412
IGNORED_JSON_FILENAMES = {"model_summary.json", "sample_manifest.json"}


def list_task_files_by_tier(dataset_root: Path) -> dict[int, list[Path]]:
    grouped: dict[int, list[Path]] = {}
    for task_path in sorted(dataset_root.rglob("*.json")):
        if task_path.name in IGNORED_JSON_FILENAMES:
            continue
        _, task = load_task_json(task_path)
        tier = int(task.metadata.get("tier", task.metadata.get("difficulty", 0)) or 0)
        grouped.setdefault(tier, []).append(task_path)
    return dict(sorted(grouped.items()))


def allocate_counts(tiers: list[int], total: int) -> dict[int, int]:
    if total <= 0:
        raise ValueError("total must be greater than 0")
    if not tiers:
        raise ValueError("No task tiers were found.")

    base = total // len(tiers)
    remainder = total % len(tiers)
    allocation: dict[int, int] = {}

    for index, tier in enumerate(tiers):
        allocation[tier] = base + (1 if index < remainder else 0)

    return allocation


def sample_task_files(dataset_root: Path, total: int, seed: int) -> list[Path]:
    grouped = list_task_files_by_tier(dataset_root)
    tiers = sorted(grouped.keys())
    allocation = allocate_counts(tiers, total)

    rng = random.Random(seed)
    sampled: list[Path] = []

    for tier in tiers:
        candidates = list(grouped[tier])
        take_count = allocation[tier]
        if take_count > len(candidates):
            raise ValueError(f"Tier {tier} only has {len(candidates)} tasks, cannot sample {take_count}.")
        rng.shuffle(candidates)
        sampled.extend(sorted(candidates[:take_count]))

    return sorted(sampled)


def save_sampling_manifest(
    sampled_files: list[Path],
    result_namespace: str,
    seed: int,
    dataset_root: Path,
) -> Path:
    result_root = get_results_dir(result_namespace)
    result_root.mkdir(parents=True, exist_ok=True)

    tier_counter = Counter()
    for task_path in sampled_files:
        _, task = load_task_json(task_path)
        tier_counter[int(task.metadata.get("tier", task.metadata.get("difficulty", 0)) or 0)] += 1

    payload = {
        "result_namespace": result_namespace,
        "dataset_root": str(dataset_root.resolve()),
        "seed": seed,
        "total_sampled_tasks": len(sampled_files),
        "sample_counts_by_tier": {str(key): value for key, value in sorted(tier_counter.items())},
        "sampled_task_paths": [str(path.resolve()) for path in sampled_files],
    }

    manifest_path = result_root / "sample_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def run_sampled_eval(
    *,
    dataset_root: Path,
    total: int,
    seed: int,
    model_name: str,
    result_namespace: str,
    skip_existing: bool,
) -> None:
    sampled_files = sample_task_files(dataset_root, total=total, seed=seed)
    manifest_path = save_sampling_manifest(sampled_files, result_namespace, seed, dataset_root)

    success = 0
    completed = 0

    print(f"Sampling manifest saved to: {manifest_path}")
    print(f"Result namespace: {result_namespace}")
    print(f"Total sampled tasks: {len(sampled_files)}")

    for index, task_path in enumerate(sampled_files, 1):
        result_path = eval_local.build_result_path(task_path, result_namespace=result_namespace)
        if skip_existing and result_path.exists():
            print(f"\n[{index}/{len(sampled_files)}] [跳过] {task_path.name}")
            try:
                cached = json.loads(result_path.read_text(encoding="utf-8"))
                completed += 1
                if cached.get("is_fully_correct"):
                    success += 1
            except Exception:
                pass
            continue

        print(f"\n[{index}/{len(sampled_files)}] 正在测评 {task_path.name}")
        result = eval_local.evaluate_single_task_json(
            task_path,
            model_name=model_name,
            result_namespace=result_namespace,
        )
        if result is None:
            continue
        completed += 1
        if result.get("is_fully_correct"):
            success += 1

    print("\n========== [抽样测评总结] ==========")
    print(f"完成数: {completed}")
    print(f"完全正确数: {success}")
    if completed > 0:
        print(f"完全正确率: {success / completed * 100:.2f}%")
    print("===================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按难度层均匀抽样运行立方体还原任务测评。")
    parser.add_argument("--dataset-root", type=Path, default=TASK_JSON_ROOT, help="任务 JSON 根目录。")
    parser.add_argument("--total", type=int, default=DEFAULT_TOTAL, help="总抽样任务数。")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子。")
    parser.add_argument(
        "--result-namespace",
        default=None,
        help="结果目录名，默认自动按 eval_common.py 里的模型名生成。",
    )
    parser.add_argument("--skip-existing", action="store_true", help="跳过已有结果。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_namespace = build_result_namespace(DEFAULT_MODEL_NAME, args.result_namespace)
    run_sampled_eval(
        dataset_root=args.dataset_root.resolve(),
        total=args.total,
        seed=args.seed,
        model_name=DEFAULT_MODEL_NAME,
        result_namespace=result_namespace,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
