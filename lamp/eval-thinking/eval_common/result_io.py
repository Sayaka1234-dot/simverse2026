from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CURRENT_DIR = Path(__file__).resolve().parent
EVAL_THINKING_ROOT = CURRENT_DIR.parent
DEFAULT_RESULTS_DIR_NAME = "results"


def sanitize_namespace(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._-")
    return normalized or "default"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_results_dir_name(task_source: str | Path | None) -> str:
    if task_source is None:
        return DEFAULT_RESULTS_DIR_NAME

    raw_value = str(task_source).replace("\\", "/").lower()
    path_parts = [part.lower() for part in Path(raw_value).parts]
    if (
        "task2" in path_parts
        or raw_value.startswith("task2/")
        or "/task2/" in raw_value
        or raw_value.endswith("/task2")
        or "random_50_tasks2" in raw_value
    ):
        return "results_task2"

    return DEFAULT_RESULTS_DIR_NAME


def build_result_path(
    sample_id: str,
    *,
    model_name: str,
    namespace: str | None = None,
    results_dir_name: str = DEFAULT_RESULTS_DIR_NAME,
) -> Path:
    safe_model = sanitize_namespace(model_name)
    safe_namespace = sanitize_namespace(namespace or model_name)
    results_root = EVAL_THINKING_ROOT / results_dir_name
    return (results_root / safe_model / safe_namespace / f"{sample_id}.json").resolve()


def save_result_json(
    sample_id: str,
    payload: dict[str, Any],
    *,
    model_name: str,
    namespace: str | None = None,
    results_dir_name: str = DEFAULT_RESULTS_DIR_NAME,
) -> Path:
    result_path = build_result_path(
        sample_id,
        model_name=model_name,
        namespace=namespace,
        results_dir_name=results_dir_name,
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


def format_task_progress(task_path: str | Path, *, index: int, total: int) -> str:
    return f"[{index}/{total}] Evaluating task file: {Path(task_path).resolve()}"


def format_skip_existing(task_path: str | Path, result_path: str | Path, *, index: int, total: int) -> str:
    return (
        f"[{index}/{total}] Skip existing result for task file: {Path(task_path).resolve()}\n"
        f"[{index}/{total}] Existing result path: {Path(result_path).resolve()}"
    )


def format_result_saved(sample_id: str, result_path: str | Path) -> str:
    return f"[{sample_id}] Result saved to: {Path(result_path).resolve()}"
