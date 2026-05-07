from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from engine_interface import evaluate_with_project_engine
from eval_common import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_SAMPLE,
    ModelAnswer,
    ModelOutputParseError,
    PuzzleTask,
    build_multimodal_messages_for_eval,
    build_result_namespace,
    build_result_path,
    build_result_path_for_sample,
    describe_skip_reason,
    extract_text_content,
    extract_message_output_parts,
    iter_manifest_tasks,
    iter_task_json_files,
    load_task_from_manifest_by_id,
    load_task_json,
    parse_model_answer_or_raise,
    save_result_json,
    save_result_json_for_sample,
    should_skip_result_write,
    split_reasoning_from_raw_output,
    utc_timestamp,
)


QWEN_OPEN_MODEL_NAME = os.getenv("QWEN_OPEN_MODEL_NAME", "Qwen/Qwen3.5-397B-A17B")
QWEN_OPEN_BASE_URL = os.getenv("QWEN_OPEN_BASE_URL", os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"))
QWEN_OPEN_API_KEY = os.getenv("QWEN_OPEN_API_KEY", os.getenv("SILICONFLOW_API_KEY", ""))
QWEN_OPEN_TIMEOUT_SECONDS = 600.0
QWEN_OPEN_MAX_TOKENS = 10000
QWEN_OPEN_TRUST_ENV = False


def _get_field(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def build_qwen_open_client() -> tuple[Any, httpx.Client]:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'openai' package is not installed. Run: pip install -r eval-thinking/requirements.txt"
        ) from exc

    timeout = httpx.Timeout(
        timeout=QWEN_OPEN_TIMEOUT_SECONDS,
        connect=min(QWEN_OPEN_TIMEOUT_SECONDS, 30.0),
    )
    http_client = httpx.Client(timeout=timeout, trust_env=QWEN_OPEN_TRUST_ENV)
    client = OpenAI(
        api_key=QWEN_OPEN_API_KEY or None,
        base_url=QWEN_OPEN_BASE_URL or None,
        timeout=timeout,
        http_client=http_client,
    )
    return client, http_client


def extract_qwen_open_stream_parts(chunk: Any) -> tuple[str, str]:
    choices = _get_field(chunk, "choices")
    if not choices:
        return "", ""

    first_choice = choices[0]
    delta = _get_field(first_choice, "delta")
    if delta is None:
        delta = _get_field(first_choice, "message")
    if delta is None:
        return "", ""

    reasoning_parts: list[str] = []
    for key in ("reasoning_content", "reasoning", "thinking", "analysis"):
        value = _get_field(delta, key)
        extracted = extract_text_content(value)
        if extracted:
            reasoning_parts.append(extracted)

    content = _get_field(delta, "content")
    if isinstance(content, str):
        return content, "\n".join(reasoning_parts).strip()
    if isinstance(content, dict):
        extracted_content = extract_text_content(content)
        return extracted_content, "\n".join(reasoning_parts).strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            text = _get_field(item, "text")
            if isinstance(text, str):
                parts.append(text)
                continue
            if isinstance(item, dict):
                dict_text = item.get("text")
                if isinstance(dict_text, str):
                    parts.append(dict_text)
                    continue
                nested = item.get("content")
                if isinstance(nested, str):
                    parts.append(nested)
        return "".join(parts), "\n".join(reasoning_parts).strip()

    return "", "\n".join(reasoning_parts).strip()


def request_qwen_open_answer(task: PuzzleTask, model_name: str) -> tuple[str, ModelAnswer, str]:
    if not QWEN_OPEN_API_KEY or QWEN_OPEN_API_KEY == "YOUR_QWEN_OPEN_API_KEY":
        raise RuntimeError(
            "QWEN_OPEN_API_KEY is empty. Please set QWEN_OPEN_API_KEY or edit eval-thinking/eval_qwen_open_local.py."
        )

    messages = build_multimodal_messages_for_eval(task)

    client, http_client = build_qwen_open_client()
    try:
        request_kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": QWEN_OPEN_MAX_TOKENS,
        }
        response = client.chat.completions.create(**request_kwargs)

        raw_text, reasoning_output = extract_message_output_parts(response.choices[0].message)
        if not reasoning_output and raw_text:
            reasoning_output, _ = split_reasoning_from_raw_output(raw_text)
        if not raw_text and reasoning_output:
            raw_text = reasoning_output
        print(f"\n[Model Raw Output] {task.sample_id} | {model_name}")
        print(raw_text)
        print("[End Model Raw Output]\n")
    finally:
        http_client.close()

    if not raw_text.strip():
        raise ModelOutputParseError(
            "Model stream returned no extractable text content.",
            raw_text=reasoning_output,
        )

    answer = parse_model_answer_or_raise(raw_text, task.sample_id)
    return raw_text, answer, reasoning_output


def build_success_payload(
    *,
    task: PuzzleTask,
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
        "source_level_path": task.metadata.get("source_level_path"),
        "model": {
            "model_name": model_name,
            "base_url": QWEN_OPEN_BASE_URL or None,
            "provider": "siliconflow-openai-compatible",
        },
        "raw_model_output": raw_model_output,
        "model_reasoning_output": model_reasoning_output,
        "normalized_answer": {
            face_key: {
                "patternId": face.patternId,
                "rotation": face.rotation,
            }
            for face_key, face in answer.answer.items()
        },
        "engine_result": engine_result,
        "evaluation_status": engine_result.get("evaluation_status"),
        "is_fully_correct": bool(engine_result.get("is_fully_correct", False)),
        "correct_face_count": int(engine_result.get("correct_face_count", 0) or 0),
        "total_face_count": int(engine_result.get("total_face_count", 0) or 0),
        "determined_face_count": int(engine_result.get("determined_face_count", 0) or 0),
        "correct_determined_face_count": int(engine_result.get("correct_determined_face_count", 0) or 0),
        "unknown_face_count": int(engine_result.get("unknown_face_count", 0) or 0),
        "correct_unknown_face_count": int(engine_result.get("correct_unknown_face_count", 0) or 0),
        "correct_pattern_count": int(engine_result.get("correct_pattern_count", 0) or 0),
        "correct_pattern_and_rotation_count": int(
            engine_result.get("correct_pattern_and_rotation_count", engine_result.get("correct_rotation_count", 0)) or 0
        ),
        "correct_rotation_count": int(engine_result.get("correct_rotation_count", 0) or 0),
        "overall_face_accuracy": float(engine_result.get("overall_face_accuracy", 0.0) or 0.0),
        "determined_face_accuracy": float(engine_result.get("determined_face_accuracy", 0.0) or 0.0),
        "unknown_face_accuracy": float(engine_result.get("unknown_face_accuracy", 0.0) or 0.0),
        "pattern_accuracy": float(engine_result.get("pattern_accuracy", 0.0) or 0.0),
        "pattern_and_rotation_accuracy": float(
            engine_result.get("pattern_and_rotation_accuracy", engine_result.get("rotation_accuracy", 0.0)) or 0.0
        ),
        "rotation_accuracy": float(engine_result.get("rotation_accuracy", 0.0) or 0.0),
        "task_metadata": task.metadata,
        "saved_at_utc": utc_timestamp(),
    }


def build_error_payload(
    *,
    task: PuzzleTask | None,
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
        "source_level_path": task.metadata.get("source_level_path") if task else None,
        "model": {
            "model_name": model_name,
            "base_url": QWEN_OPEN_BASE_URL or None,
            "provider": "siliconflow-openai-compatible",
        },
        "raw_model_output": raw_model_output,
        "model_reasoning_output": model_reasoning_output,
        "normalized_answer": None,
        "engine_result": None,
        "evaluation_status": "error",
        "is_fully_correct": False,
        "correct_face_count": 0,
        "total_face_count": 0,
        "determined_face_count": 0,
        "correct_determined_face_count": 0,
        "unknown_face_count": 0,
        "correct_unknown_face_count": 0,
        "correct_pattern_count": 0,
        "correct_pattern_and_rotation_count": 0,
        "correct_rotation_count": 0,
        "overall_face_accuracy": 0.0,
        "determined_face_accuracy": 0.0,
        "unknown_face_accuracy": 0.0,
        "pattern_accuracy": 0.0,
        "pattern_and_rotation_accuracy": 0.0,
        "rotation_accuracy": 0.0,
        "task_metadata": task.metadata if task else {},
        "error_message": error_message,
        "saved_at_utc": utc_timestamp(),
    }


def evaluate_task(
    task: PuzzleTask,
    *,
    task_source: str,
    model_name: str,
) -> dict[str, Any]:
    raw_model_output, answer, model_reasoning_output = request_qwen_open_answer(task, model_name)
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
            print(f"Reason: {describe_skip_reason(exc)}")
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
            print(f"Reason: {describe_skip_reason(exc)}")
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

    success = 0
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
                if cached.get("is_fully_correct"):
                    success += 1
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
        if result.get("is_fully_correct"):
            success += 1

    print("\n========== [Batch Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Fully correct: {success}")
    if completed > 0:
        print(f"Pass rate: {success / completed * 100:.2f}%")
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

    success = 0
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
                if cached.get("is_fully_correct"):
                    success += 1
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
        if result.get("is_fully_correct"):
            success += 1

    print("\n========== [Manifest Summary] ==========")
    print(f"Total tasks: {total}")
    print(f"Completed: {completed}")
    print(f"Fully correct: {success}")
    if completed > 0:
        print(f"Pass rate: {success / completed * 100:.2f}%")
    print("========================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cube reconstruction tasks with Qwen Open.")
    parser.add_argument(
        "target_path",
        type=Path,
        nargs="?",
        default=DEFAULT_OUTPUT_SAMPLE,
        help="Task JSON file, task JSON directory, or task manifest JSONL path.",
    )
    parser.add_argument(
        "--result-namespace",
        default=None,
        help="Optional result subdirectory name. Defaults to the configured model name.",
    )
    parser.add_argument("--skip-existing", action="store_true", help="Skip tasks that already have saved results.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to evaluate.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Task manifest path used when target_path is JSONL or when --sample-id is set.",
    )
    parser.add_argument("--sample-id", type=str, default=None, help="Evaluate only one task by sample_id.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_namespace = build_result_namespace(QWEN_OPEN_MODEL_NAME, args.result_namespace)

    target_path = args.target_path.resolve()
    if len(sys.argv) <= 1 and args.sample_id is None:
        print(f"No target_path provided, defaulting to: {target_path}")

    if args.sample_id:
        result = evaluate_single_manifest_task(
            args.manifest.resolve(),
            args.sample_id,
            model_name=QWEN_OPEN_MODEL_NAME,
            result_namespace=result_namespace,
        )
        if result is None:
            print("\nSkipped: transient API failure or incomplete model output. No result file was written.\n")
        return

    if target_path.suffix.lower() == ".jsonl":
        evaluate_batch_manifest(
            target_path,
            model_name=QWEN_OPEN_MODEL_NAME,
            result_namespace=result_namespace,
            skip_existing=args.skip_existing,
            limit=args.limit,
        )
        return

    if target_path.is_dir():
        evaluate_batch_task_jsons(
            target_path,
            model_name=QWEN_OPEN_MODEL_NAME,
            result_namespace=result_namespace,
            skip_existing=args.skip_existing,
            limit=args.limit,
        )
        return

    if target_path.is_file():
        result = evaluate_single_task_json(
            target_path,
            model_name=QWEN_OPEN_MODEL_NAME,
            result_namespace=result_namespace,
        )
        if result is None:
            print("\nSkipped: transient API failure or incomplete model output. No result file was written.\n")
            return
        print("\n========== [Final Summary] ==========")
        print(
            json.dumps(
                {
                    "sample_id": result.get("sample_id"),
                    "evaluation_status": result.get("evaluation_status"),
                    "is_fully_correct": result.get("is_fully_correct"),
                    "correct_face_count": result.get("correct_face_count"),
                    "total_face_count": result.get("total_face_count"),
                    "pattern_accuracy": result.get("pattern_accuracy"),
                    "pattern_and_rotation_accuracy": result.get("pattern_and_rotation_accuracy"),
                    "determined_face_accuracy": result.get("determined_face_accuracy"),
                    "result_saved": result.get("result_json_path"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("====================================\n")
        return

    raise FileNotFoundError(f"Target path does not exist: {target_path}")


if __name__ == "__main__":
    main()
