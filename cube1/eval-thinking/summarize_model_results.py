from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results"
SUMMARY_FILENAME = "model_summary.json"
IGNORED_FILENAMES = {SUMMARY_FILENAME, "sample_manifest.json"}


def is_result_json(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".json" and path.name not in IGNORED_FILENAMES


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def round_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    raw_total_tasks = len(records)
    valid_records = [record for record in records if record.get("evaluation_status") == "ok"]
    total_tasks = len(valid_records)
    fully_correct_tasks = sum(1 for record in valid_records if bool(record.get("is_fully_correct", False)))

    total_face_count = sum(safe_int(record.get("total_face_count")) for record in valid_records)
    correct_face_count = sum(safe_int(record.get("correct_face_count")) for record in valid_records)
    determined_face_count = sum(safe_int(record.get("determined_face_count")) for record in valid_records)
    correct_determined_face_count = sum(safe_int(record.get("correct_determined_face_count")) for record in valid_records)
    unknown_face_count = sum(safe_int(record.get("unknown_face_count")) for record in valid_records)
    correct_unknown_face_count = sum(safe_int(record.get("correct_unknown_face_count")) for record in valid_records)
    correct_pattern_count = sum(safe_int(record.get("correct_pattern_count")) for record in valid_records)
    correct_pattern_and_rotation_count = sum(
        safe_int(record.get("correct_pattern_and_rotation_count", record.get("correct_rotation_count")))
        for record in valid_records
    )
    correct_rotation_count = sum(safe_int(record.get("correct_rotation_count")) for record in valid_records)

    evaluation_status_counts = Counter(str(record.get("evaluation_status", "unknown")) for record in records)

    average_overall_face_accuracy = round(
        sum(safe_float(record.get("overall_face_accuracy")) for record in valid_records) / total_tasks,
        6,
    ) if total_tasks else 0.0
    average_determined_face_accuracy = round(
        sum(safe_float(record.get("determined_face_accuracy")) for record in valid_records) / total_tasks,
        6,
    ) if total_tasks else 0.0
    average_pattern_accuracy = round(
        sum(safe_float(record.get("pattern_accuracy")) for record in valid_records) / total_tasks,
        6,
    ) if total_tasks else 0.0
    average_pattern_and_rotation_accuracy = round(
        sum(safe_float(record.get("pattern_and_rotation_accuracy", record.get("rotation_accuracy"))) for record in valid_records)
        / total_tasks,
        6,
    ) if total_tasks else 0.0

    return {
        "raw_total_tasks": raw_total_tasks,
        "total_tasks": total_tasks,
        "fully_correct_tasks": fully_correct_tasks,
        "pass_rate": round_ratio(fully_correct_tasks, total_tasks),
        "valid_evaluation_count": total_tasks,
        "valid_evaluation_rate": round_ratio(total_tasks, raw_total_tasks),
        "total_face_count": total_face_count,
        "correct_face_count": correct_face_count,
        "face_accuracy": round_ratio(correct_face_count, total_face_count),
        "determined_face_count": determined_face_count,
        "correct_determined_face_count": correct_determined_face_count,
        "determined_face_accuracy": round_ratio(correct_determined_face_count, determined_face_count),
        "unknown_face_count": unknown_face_count,
        "correct_unknown_face_count": correct_unknown_face_count,
        "unknown_face_accuracy": round_ratio(correct_unknown_face_count, unknown_face_count),
        "correct_pattern_count": correct_pattern_count,
        "pattern_accuracy": average_pattern_accuracy,
        "correct_pattern_and_rotation_count": correct_pattern_and_rotation_count,
        "pattern_and_rotation_accuracy": average_pattern_and_rotation_accuracy,
        "correct_rotation_count": correct_rotation_count,
        "rotation_accuracy": round_ratio(correct_rotation_count, determined_face_count),
        "average_overall_face_accuracy": average_overall_face_accuracy,
        "average_determined_face_accuracy": average_determined_face_accuracy,
        "evaluation_status_counts": dict(sorted(evaluation_status_counts.items())),
    }


def summarize_model_directory(model_dir: Path) -> dict[str, Any]:
    result_files = sorted(path for path in model_dir.rglob("*.json") if is_result_json(path))
    records = [load_json(path) for path in result_files]

    by_tier: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        metadata = record.get("task_metadata") or {}
        tier = str(metadata.get("tier", metadata.get("difficulty", "unknown")))
        by_tier.setdefault(tier, []).append(record)

    summary = {
        "model_name": model_dir.name,
        "model_result_dir": str(model_dir.resolve()),
        "summary_file": str((model_dir / SUMMARY_FILENAME).resolve()),
        "overall": summarize_records(records),
        "by_tier": {
            tier: summarize_records(tier_records)
            for tier, tier_records in sorted(by_tier.items(), key=lambda item: item[0])
        },
    }

    if records:
        first_model_info = records[0].get("model")
        if isinstance(first_model_info, dict):
            summary["model_info"] = first_model_info

    return summary


def save_summary(model_dir: Path, summary: dict[str, Any]) -> Path:
    output_path = model_dir / SUMMARY_FILENAME
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def iter_model_directories(target_path: Path) -> list[Path]:
    if target_path.is_file():
        raise ValueError("Please pass a model result directory or the eval-thinking/results root, not a single result file.")

    if target_path.name == "results":
        return sorted(path for path in target_path.iterdir() if path.is_dir())

    return [target_path]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize cube eval-thinking model results.")
    parser.add_argument(
        "target_path",
        type=Path,
        nargs="?",
        default=DEFAULT_RESULTS_ROOT,
        help="A model result directory, such as eval-thinking/results/gpt-4.1, or the eval-thinking/results root.",
    )
    args = parser.parse_args()

    target_path = args.target_path.resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"The target path does not exist: {target_path}")

    model_dirs = iter_model_directories(target_path)
    if not model_dirs:
        print(f"No model result directories found under: {target_path}")
        return

    for model_dir in model_dirs:
        summary = summarize_model_directory(model_dir)
        output_path = save_summary(model_dir, summary)
        overall = summary["overall"]

        print(f"\nModel: {model_dir.name}")
        print(f"Summary saved to: {output_path}")
        print(f"Pass rate: {overall['pass_rate']:.6f} ({overall['fully_correct_tasks']} / {overall['total_tasks']})")
        print(f"Face accuracy: {overall['face_accuracy']:.6f}")
        print(f"Determined face accuracy: {overall['determined_face_accuracy']:.6f}")
        print(f"Pattern accuracy: {overall['pattern_accuracy']:.6f}")
        print(f"Pattern+rotation accuracy: {overall['pattern_and_rotation_accuracy']:.6f}")
        print(f"Rotation accuracy: {overall['rotation_accuracy']:.6f}")


if __name__ == "__main__":
    main()
