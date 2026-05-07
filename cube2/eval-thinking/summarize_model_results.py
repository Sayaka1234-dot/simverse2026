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


def round_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def normalize_rotation(value: Any) -> int:
    try:
        return int(value) % 360
    except (TypeError, ValueError):
        return 0


def is_pattern_correct(record: dict[str, Any]) -> bool:
    if "is_pattern_correct" in record:
        return bool(record.get("is_pattern_correct"))

    engine_result = record.get("engine_result") or {}
    if "is_pattern_correct" in engine_result:
        return bool(engine_result.get("is_pattern_correct"))

    target_face = engine_result.get("target_face") or {}
    final_face = engine_result.get("final_observed_face") or {}
    return str(target_face.get("patternId", "?")) == str(final_face.get("patternId", "?"))


def is_pattern_and_rotation_correct(record: dict[str, Any]) -> bool:
    if "is_pattern_and_rotation_correct" in record:
        return bool(record.get("is_pattern_and_rotation_correct"))

    engine_result = record.get("engine_result") or {}
    if "is_pattern_and_rotation_correct" in engine_result:
        return bool(engine_result.get("is_pattern_and_rotation_correct"))

    target_face = engine_result.get("target_face") or {}
    final_face = engine_result.get("final_observed_face") or {}
    return (
        str(target_face.get("patternId", "?")) == str(final_face.get("patternId", "?"))
        and normalize_rotation(target_face.get("rotation", 0)) == normalize_rotation(final_face.get("rotation", 0))
    )


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    raw_total_tasks = len(records)
    valid_records = [record for record in records if record.get("evaluation_status") == "ok"]
    total_tasks = len(valid_records)
    solved_tasks = sum(1 for record in valid_records if bool(record.get("is_valid_solution", False)))
    pattern_correct_count = sum(1 for record in valid_records if is_pattern_correct(record))
    pattern_and_rotation_correct_count = sum(
        1 for record in valid_records if is_pattern_and_rotation_correct(record)
    )
    exact_reference_match_count = sum(
        1 for record in valid_records if bool(record.get("exact_reference_match", False))
    )
    total_predicted_move_count = sum(safe_int(record.get("predicted_move_count")) for record in valid_records)
    total_reference_move_count = sum(safe_int(record.get("reference_move_count")) for record in valid_records)
    evaluation_status_counts = Counter(str(record.get("evaluation_status", "unknown")) for record in records)

    average_predicted_move_count = round(total_predicted_move_count / total_tasks, 6) if total_tasks else 0.0
    average_reference_move_count = round(total_reference_move_count / total_tasks, 6) if total_tasks else 0.0

    return {
        "raw_total_tasks": raw_total_tasks,
        "total_tasks": total_tasks,
        "valid_evaluation_count": total_tasks,
        "valid_evaluation_rate": round_ratio(total_tasks, raw_total_tasks),
        "solved_tasks": solved_tasks,
        "solution_rate": round_ratio(solved_tasks, total_tasks),
        "pattern_correct_count": pattern_correct_count,
        "pattern_accuracy": round_ratio(pattern_correct_count, total_tasks),
        "pattern_and_rotation_correct_count": pattern_and_rotation_correct_count,
        "pattern_and_rotation_accuracy": round_ratio(pattern_and_rotation_correct_count, total_tasks),
        "exact_reference_match_count": exact_reference_match_count,
        "exact_reference_match_rate": round_ratio(exact_reference_match_count, total_tasks),
        "total_predicted_move_count": total_predicted_move_count,
        "total_reference_move_count": total_reference_move_count,
        "average_predicted_move_count": average_predicted_move_count,
        "average_reference_move_count": average_reference_move_count,
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
        raise ValueError("Please pass a model result directory or the cube2/eval-thinking/results root.")
    if target_path.name == "results":
        return sorted(path for path in target_path.iterdir() if path.is_dir())
    return [target_path]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize cube2 eval-thinking results.")
    parser.add_argument(
        "target_path",
        type=Path,
        nargs="?",
        default=DEFAULT_RESULTS_ROOT,
        help="A model result directory or the cube2/eval-thinking/results root.",
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
        print(f"Solution rate: {overall['solution_rate']:.6f} ({overall['solved_tasks']} / {overall['total_tasks']})")
        print(
            f"Pattern accuracy: {overall['pattern_accuracy']:.6f} "
            f"({overall['pattern_correct_count']} / {overall['total_tasks']})"
        )
        print(
            f"Pattern+rotation accuracy: {overall['pattern_and_rotation_accuracy']:.6f} "
            f"({overall['pattern_and_rotation_correct_count']} / {overall['total_tasks']})"
        )
        print(
            f"Exact reference match rate: {overall['exact_reference_match_rate']:.6f} "
            f"({overall['exact_reference_match_count']} / {overall['total_tasks']})"
        )
        print(f"Average predicted move count: {overall['average_predicted_move_count']:.6f}")
        print(f"Average reference move count: {overall['average_reference_move_count']:.6f}")


if __name__ == "__main__":
    main()
