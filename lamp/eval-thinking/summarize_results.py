from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import statistics
from typing import Any


CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_ROOT = CURRENT_DIR / "results"
SUMMARY_FILENAME = "model_summary.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    valid_format = sum(1 for record in records if bool(record.get("is_valid_format", False)))
    solved = sum(1 for record in records if bool(record.get("is_valid_solution", False)))
    status_counts = Counter(str(record.get("evaluation_status", "unknown")) for record in records)

    distances = [
        float(record.get("distance", 0))
        for record in records
        if record.get("distance") is not None
    ]

    return {
        "total_tasks": total,
        "valid_format_count": valid_format,
        "valid_format_rate": round(valid_format / total, 6) if total else 0.0,
        "solved_tasks": solved,
        "solution_rate": round(solved / total, 6) if total else 0.0,
        "average_distance": round(statistics.mean(distances), 6) if distances else 0.0,
        "median_distance": round(statistics.median(distances), 6) if distances else 0.0,
        "evaluation_status_counts": dict(sorted(status_counts.items())),
    }


def summarize_model_directory(model_dir: Path) -> dict[str, Any]:
    result_files = sorted(path for path in model_dir.rglob("*.json") if path.name != SUMMARY_FILENAME)
    records = [load_json(path) for path in result_files]
    return {
        "model_name": model_dir.name,
        "model_result_dir": str(model_dir.resolve()),
        "overall": summarize_records(records),
    }


def save_summary(model_dir: Path, summary: dict[str, Any]) -> Path:
    output_path = model_dir / SUMMARY_FILENAME
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def iter_model_directories(target_path: Path) -> list[Path]:
    if target_path.name.startswith("results"):
        return sorted(path for path in target_path.iterdir() if path.is_dir())
    return [target_path]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize mechanical lamp evaluation results.")
    parser.add_argument("target_path", nargs="?", type=Path, default=DEFAULT_RESULTS_ROOT)
    args = parser.parse_args()

    target_path = args.target_path.resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    for model_dir in iter_model_directories(target_path):
        summary = summarize_model_directory(model_dir)
        output_path = save_summary(model_dir, summary)
        overall = summary["overall"]
        print(f"Model: {model_dir.name}")
        print(f"Summary saved to: {output_path}")
        print(f"Valid format rate: {overall['valid_format_rate']:.6f}")
        print(f"Solution rate: {overall['solution_rate']:.6f}")
        print(f"Average distance: {overall['average_distance']:.2f}")
        print(f"Median distance: {overall['median_distance']:.2f}")


if __name__ == "__main__":
    main()
