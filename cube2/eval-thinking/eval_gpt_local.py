from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from engine_interface import evaluate_with_project_engine
from eval_common import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_SAMPLE,
    ModelAnswer,
    ModelOutputParseError,
    GoalRollTask,
    build_result_namespace,
    build_result_path,
    build_result_path_for_sample,
    should_skip_result_write,
    iter_manifest_tasks,
    iter_task_json_files,
    load_task_from_manifest_by_id,
    load_task_json,
    request_model_answer,
    save_result_json,
    save_result_json_for_sample,
    split_reasoning_from_raw_output,
    utc_timestamp,
)


# DEFAULT_MODEL_NAME:
# Default model name used by this goal-roll evaluation entry.
DEFAULT_MODEL_NAME = "gpt-5.4"

# DEFAULT_BASE_URL:
# Base URL for the OpenAI-compatible endpoint.
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://xiaoai.plus/v1")

# DEFAULT_API_KEY:
# API key used for model calls.
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")

# DEFAULT_TIMEOUT_SECONDS:
# Request timeout in seconds.
DEFAULT_TIMEOUT_SECONDS = 600.0

# DEFAULT_MAX_TOKENS:
# Maximum number of output tokens requested from the model.
DEFAULT_MAX_TOKENS = 10000

# DEFAULT_TRUST_ENV:
# Whether httpx should trust system proxy environment variables.
DEFAULT_TRUST_ENV = False


def build_success_payload(
    *,
    task: GoalRollTask,
    task_source: str,
    model_name: str,
    raw_model_output: str,
    model_reasoning_output: str,
    answer: ModelAnswer,
    engine_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sample_id": task.sample_id,
        "sample_id": task.sample_id,
        "task_source": task_source,
        "source_task_json_path": task.metadata.get("sourceTaskJsonPath"),
        "source_level_path": task.metadata.get("sourceLevelPath"),
        "model": {
            "model_name": model_name,
            "base_url": DEFAULT_BASE_URL or None,
        },
        "raw_model_output": raw_model_output,
        "model_reasoning_output": model_reasoning_output,
        "normalized_answer": {
            "directions": list(answer.directions),
        },
        "engine_result": engine_result,
        "evaluation_status": engine_result.get("evaluation_status"),
        "is_pattern_correct": bool(engine_result.get("is_pattern_correct", False)),
        "is_pattern_and_rotation_correct": bool(engine_result.get("is_pattern_and_rotation_correct", False)),
        "is_fully_correct": bool(engine_result.get("is_fully_correct", False)),
        "is_valid_solution": bool(engine_result.get("is_valid_solution", False)),
        "exact_reference_match": bool(engine_result.get("exact_reference_match", False)),
        "predicted_move_count": int(engine_result.get("predicted_move_count", 0) or 0),
        "reference_move_count": int(engine_result.get("reference_move_count", 0) or 0),
        "task_metadata": task.metadata,
        "saved_at_utc": utc_timestamp(),
    }


def build_error_payload(
    *,
    task: GoalRollTask | None,
    task_source: str,
    model_name: str,
    error_message: str,
    raw_model_output: str = "",
    model_reasoning_output: str = "",
) -> dict[str, Any]:
    return {
        "sample_id": task.sample_id if task else None,
        "sample_id": task.sample_id if task else None,
        "task_source": task_source,
        "source_task_json_path": task.metadata.get("sourceTaskJsonPath") if task else None,
        "source_level_path": task.metadata.get("sourceLevelPath") if task else None,
        "model": {
            "model_name": model_name,
            "base_url": DEFAULT_BASE_URL or None,
        },
        "raw_model_output": raw_model_output,
        "model_reasoning_output": model_reasoning_output,
        "normalized_answer": None,
        "engine_result": None,
        "evaluation_status": "error",
        "is_pattern_correct": False,
        "is_pattern_and_rotation_correct": False,
        "is_fully_correct": False,
        "is_valid_solution": False,
        "exact_reference_match": False,
        "predicted_move_count": 0,
        "reference_move_count": 0,
        "task_metadata": task.metadata if task else {},
        "error_message": error_message,
        "saved_at_utc": utc_timestamp(),
    }


def evaluate_task(
    task: GoalRollTask,
    *,
    task_source: str,
    model_name: str,
) -> dict[str, Any]:
    raw_model_output, answer, model_reasoning_output = request_model_answer(
        task,
        model_name,
        api_key=DEFAULT_API_KEY,
        base_url=DEFAULT_BASE_URL,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        trust_env=DEFAULT_TRUST_ENV,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    engine_result = evaluate_with_project_engine(task, answer)
    return build_success_payload(
        task=task,
        task_source=task_source,
        model_name=model_name,
        raw_model_output=raw_model_output,
        model_reasoning_output=model_reasoning_output,
        answer=answer,
        engine_result=engine_result,
    )


def evaluate_single_task_json(
    task_json_path: Path,
    *,
    model_name: str,
    result_namespace: str,
) -> dict[str, Any] | None:
    task_path, task = load_task_json(task_json_path)
    print(f"Evaluating task: {task.sample_id} ({task_path.name})")
    print(f"model: {model_name}")

    try:
        payload = evaluate_task(
            task,
            task_source=str(task_path),
            model_name=model_name,
        )
    except Exception as exc:
        if should_skip_result_write(exc):
            print(f"Skip {task.sample_id}: transient API failure or incomplete model output, no result file will be written.")
            return None
        payload = build_error_payload(
            task=task,
            task_source=str(task_path),
            model_name=model_name,
            error_message=str(exc),
            raw_model_output=exc.raw_text if isinstance(exc, ModelOutputParseError) else "",
            model_reasoning_output=split_reasoning_from_raw_output(exc.raw_text)[0]
            if isinstance(exc, ModelOutputParseError)
            else "",
        )

    result_path = save_result_json(
        task_path,
        payload,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    payload["result_json_path"] = str(result_path)
    save_result_json(
        task_path,
        payload,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    print(f"Saved result to: {result_path}")
    return payload


def evaluate_single_manifest_task(
    manifest_path: Path,
    sample_id: str,
    *,
    model_name: str,
    result_namespace: str,
) -> dict[str, Any] | None:
    task = load_task_from_manifest_by_id(manifest_path, sample_id)
    source = str(manifest_path.resolve())
    print(f"Evaluating task: {task.sample_id} (from manifest)")
    print(f"model: {model_name}")

    try:
        payload = evaluate_task(
            task,
            task_source=source,
            model_name=model_name,
        )
    except Exception as exc:
        if should_skip_result_write(exc):
            print(f"Skip {task.sample_id}: transient API failure or incomplete model output, no result file will be written.")
            return None
        payload = build_error_payload(
            task=task,
            task_source=source,
            model_name=model_name,
            error_message=str(exc),
            raw_model_output=exc.raw_text if isinstance(exc, ModelOutputParseError) else "",
            model_reasoning_output=split_reasoning_from_raw_output(exc.raw_text)[0]
            if isinstance(exc, ModelOutputParseError)
            else "",
        )

    result_path = save_result_json_for_sample(
        task.sample_id,
        payload,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    payload["result_json_path"] = str(result_path)
    save_result_json_for_sample(
        task.sample_id,
        payload,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    print(f"Saved result to: {result_path}")
    return payload


def evaluate_batch_task_jsons(
    task_dir: Path,
    *,
    model_name: str,
    result_namespace: str,
    skip_existing: bool,
    limit: int | None,
) -> None:
    task_files = iter_task_json_files(task_dir)
    if limit is not None and limit > 0:
        task_files = task_files[:limit]

    total = len(task_files)
    if total == 0:
        print(f"No task JSON files found under: {task_dir}")
        return

    solved = 0
    completed = 0

    for index, task_path in enumerate(task_files, 1):
        result_path = build_result_path(
            task_path,
            model_name=model_name,
            result_namespace=result_namespace,
        )
        if skip_existing and result_path.exists():
            print(f"\n[{index}/{total}] [skip] {task_path.name}")
            try:
                cached = json.loads(result_path.read_text(encoding="utf-8"))
                completed += 1
                if cached.get("is_valid_solution"):
                    solved += 1
            except Exception:
                pass
            continue

        print(f"\n[{index}/{total}] ==============================================")
        result = evaluate_single_task_json(
            task_path,
            model_name=model_name,
            result_namespace=result_namespace,
        )
        if result is None:
            continue
        completed += 1
        if result.get("is_valid_solution"):
            solved += 1

    print("\n========== [Batch Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Valid solutions: {solved}")
    if completed > 0:
        print(f"Solution rate: {solved / completed * 100:.2f}%")
    print("=====================================")


def evaluate_batch_manifest(
    manifest_path: Path,
    *,
    model_name: str,
    result_namespace: str,
    skip_existing: bool,
    limit: int | None,
) -> None:
    tasks = list(iter_manifest_tasks(manifest_path))
    if limit is not None and limit > 0:
        tasks = tasks[:limit]

    total = len(tasks)
    if total == 0:
        print(f"No tasks found in manifest: {manifest_path}")
        return

    solved = 0
    completed = 0

    for index, task in enumerate(tasks, 1):
        result_path = build_result_path_for_sample(
            task.sample_id,
            model_name=model_name,
            result_namespace=result_namespace,
        )
        if skip_existing and result_path.exists():
            print(f"\n[{index}/{total}] [skip] {task.sample_id}")
            try:
                cached = json.loads(result_path.read_text(encoding="utf-8"))
                completed += 1
                if cached.get("is_valid_solution"):
                    solved += 1
            except Exception:
                pass
            continue

        print(f"\n[{index}/{total}] ==============================================")
        result = evaluate_single_manifest_task(
            manifest_path,
            task.sample_id,
            model_name=model_name,
            result_namespace=result_namespace,
        )
        if result is None:
            continue
        completed += 1
        if result.get("is_valid_solution"):
            solved += 1

    print("\n========== [Manifest Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Valid solutions: {solved}")
    if completed > 0:
        print(f"Solution rate: {solved / completed * 100:.2f}%")
    print("=======================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cube2 goal-roll tasks with the default model.")
    parser.add_argument(
        "task_target",
        nargs="?",
        default=str(DEFAULT_OUTPUT_SAMPLE),
        help="A task JSON path, a task JSON directory, or a task manifest JSONL path.",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSONL path.")
    parser.add_argument("--sample-id", default=None, help="Evaluate one sample from the manifest.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip existing result files.")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N tasks.")
    parser.add_argument("--result-namespace", default=None, help="Optional result namespace override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = DEFAULT_MODEL_NAME
    result_namespace = build_result_namespace(model_name, args.result_namespace)

    if args.manifest:
        manifest_path = args.manifest.resolve()
        if args.sample_id:
            evaluate_single_manifest_task(
                manifest_path,
                args.sample_id,
                model_name=model_name,
                result_namespace=result_namespace,
            )
            return
        evaluate_batch_manifest(
            manifest_path,
            model_name=model_name,
            result_namespace=result_namespace,
            skip_existing=args.skip_existing,
            limit=args.limit,
        )
        return

    target = Path(args.task_target).resolve()
    if target.suffix.lower() == ".jsonl":
        evaluate_batch_manifest(
            target,
            model_name=model_name,
            result_namespace=result_namespace,
            skip_existing=args.skip_existing,
            limit=args.limit,
        )
        return

    if target.is_dir():
        evaluate_batch_task_jsons(
            target,
            model_name=model_name,
            result_namespace=result_namespace,
            skip_existing=args.skip_existing,
            limit=args.limit,
        )
        return

    evaluate_single_task_json(
        target,
        model_name=model_name,
        result_namespace=result_namespace,
    )


if __name__ == "__main__":
    main()
