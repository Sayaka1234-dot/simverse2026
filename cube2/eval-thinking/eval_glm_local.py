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
    GoalRollTask,
    ModelAnswer,
    ModelOutputParseError,
    build_multimodal_messages_for_eval,
    build_result_namespace,
    build_result_path,
    build_result_path_for_sample,
    extract_message_output_parts,
    extract_text_content,
    should_skip_result_write,
    iter_manifest_tasks,
    iter_task_json_files,
    load_task_from_manifest_by_id,
    load_task_json,
    parse_model_answer_or_raise,
    save_result_json,
    save_result_json_for_sample,
    split_reasoning_from_raw_output,
    utc_timestamp,
)


# GLM_MODEL_NAME:
# Default GLM model name used by this goal-roll evaluation entry.
GLM_MODEL_NAME = "glm-5v-turbo"

# GLM_API_KEY:
# Zhipu API key.
# By default this reads the GLM_API_KEY environment variable.
GLM_API_KEY = os.getenv("GLM_API_KEY", "1042338736b9443d980979cdfe935688.Zi0RmJGJCvkKP9ZW")

# GLM_BASE_URL:
# Recorded for result metadata only.
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# GLM_MAX_TOKENS:
# Maximum number of output tokens requested from the GLM model.
GLM_MAX_TOKENS = 10000


def build_glm_client() -> Any:
    try:
        from zai import ZhipuAiClient
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The official ZAI SDK is not installed. Please install the package that provides 'from zai import ZhipuAiClient'."
        ) from exc

    return ZhipuAiClient(api_key=GLM_API_KEY)


def extract_glm_message_text(message: Any) -> str:
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")

    return extract_text_content(content)


def request_glm_answer(task: GoalRollTask, model_name: str) -> tuple[str, ModelAnswer, str]:
    if not GLM_API_KEY or GLM_API_KEY == "YOUR_GLM_API_KEY":
        raise RuntimeError("GLM_API_KEY is empty. Please set GLM_API_KEY or edit cube2/eval-thinking/eval_glm_local.py.")

    messages = build_multimodal_messages_for_eval(task)

    client = build_glm_client()
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "max_tokens": GLM_MAX_TOKENS,
    }

    response = client.chat.completions.create(**request_kwargs)
    raw_text, reasoning_output = extract_message_output_parts(response.choices[0].message)
    raw_text = raw_text.strip()

    print(f"\n[Model Raw Output] {task.sample_id} | {model_name}")
    print(raw_text)
    print("[End Model Raw Output]\n")

    answer = parse_model_answer_or_raise(raw_text, task.sample_id)
    return raw_text, answer, reasoning_output


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
            "base_url": GLM_BASE_URL,
            "provider": "zhipu-zai",
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
            "base_url": GLM_BASE_URL,
            "provider": "zhipu-zai",
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
    raw_model_output, answer, model_reasoning_output = request_glm_answer(task, model_name)
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
        payload = evaluate_task(task, task_source=str(task_path), model_name=model_name)
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
        payload = evaluate_task(task, task_source=source, model_name=model_name)
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

    print("\n========== [GLM Batch Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Valid solutions: {solved}")
    if completed > 0:
        print(f"Solution rate: {solved / completed * 100:.2f}%")
    print("========================================")


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

    print("\n========== [GLM Manifest Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Valid solutions: {solved}")
    if completed > 0:
        print(f"Solution rate: {solved / completed * 100:.2f}%")
    print("===========================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cube2 goal-roll tasks with GLM.")
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
    model_name = GLM_MODEL_NAME
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
