from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

from engine_interface import evaluate_solution
from validator import validate_task_answer
from eval_common.dataset_io import load_task_json, resolve_task_target_paths
from eval_common.model_io import ModelOutputParseError, build_chat_completion_request, extract_text_content, split_reasoning_and_final_output
from eval_common.network_errors import extract_raw_model_output, format_skip_message
from eval_common.payloads import build_error_payload, build_success_payload
from eval_common.prompting import build_multimodal_messages
from eval_common.result_io import (
    build_result_path,
    format_result_saved,
    format_skip_existing,
    format_task_progress,
    infer_results_dir_name,
    save_result_json,
)

DEFAULT_MODEL_NAME = os.getenv("EVAL_MODEL_NAME", "gpt-5.4")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://xiaoai.plus/v1")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_MAX_TOKENS = 20_000


def build_openai_client() -> tuple[Any, httpx.Client]:
    from openai import OpenAI

    timeout = httpx.Timeout(timeout=DEFAULT_TIMEOUT_SECONDS, connect=min(DEFAULT_TIMEOUT_SECONDS, 30.0))
    http_client = httpx.Client(timeout=timeout, trust_env=False)
    client = OpenAI(
        api_key=DEFAULT_API_KEY or None,
        base_url=DEFAULT_BASE_URL or None,
        timeout=timeout,
        http_client=http_client,
    )
    return client, http_client


def evaluate_task(task: Any, *, task_source: str, model_name: str) -> dict[str, Any]:
    if not DEFAULT_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for eval-thinking/eval_local.py")

    messages = build_multimodal_messages(task, project_root=PROJECT_ROOT)

    client, http_client = build_openai_client()
    try:
        response = client.chat.completions.create(
            **build_chat_completion_request(
                model_name=model_name,
                messages=messages,
                max_tokens=DEFAULT_MAX_TOKENS,
            )
        )
        raw_model_output = extract_text_content(response.choices[0].message.content)
    finally:
        http_client.close()

    prompt_reasoning, raw_final_content = split_reasoning_and_final_output(raw_model_output)
    parsed_answer = validate_task_answer(task, raw_final_content)
    engine_result = evaluate_solution(
        origin=dict(task.public.get("arm_base", {})),
        segments=task.segments,
        angles=parsed_answer.angles,
        target=dict(task.validator.get("target", {})),
        light_radius=float(dict(task.validator.get("success_rule", {})).get("radius", task.light_radius)),
        obstacles=list(task.public.get("obstacles", [])),
    )
    return build_success_payload(
        task=task,
        task_source=task_source,
        model_name=model_name,
        base_url=DEFAULT_BASE_URL or None,
        provider="openai-compatible-thinking",
        raw_model_output=raw_model_output,
        raw_reasoning_content=prompt_reasoning,
        raw_final_content=raw_final_content,
        engine_result=engine_result,
    )


def evaluate_single_task_json(task_json_path: Path, *, model_name: str) -> dict[str, Any] | None:
    task_path, task = load_task_json(task_json_path)
    results_dir_name = infer_results_dir_name(task_path)

    try:
        payload = evaluate_task(task, task_source=str(task_path), model_name=model_name)
        print(f"[{task.sample_id}] Solved: {payload.get('is_valid_solution')}")
        print(f"[{task.sample_id}] Final: {payload.get('raw_final_content')}\n")
    except ModelOutputParseError as exc:
        raw_model_output = extract_raw_model_output(exc)
        if getattr(exc, "error_kind", "validation") != "validation":
            print(f"[{task.sample_id}] json_parse_error: {exc}")
            if raw_model_output:
                print(f"[{task.sample_id}] Raw model output:")
                print(raw_model_output)
            print(f"[{task.sample_id}] Skipping current sample without saving result.\n")
            return None

        raw_reasoning_content, raw_final_content = split_reasoning_and_final_output(raw_model_output) if raw_model_output else ("", "")
        payload = build_error_payload(
            task=task,
            task_source=str(task_path),
            model_name=model_name,
            base_url=DEFAULT_BASE_URL or None,
            provider="openai-compatible-thinking",
            error_message=str(exc),
            raw_model_output=raw_model_output,
            raw_reasoning_content=raw_reasoning_content,
            raw_final_content=raw_final_content,
            evaluation_status="validation_error",
            error_kind="validation",
        )
        print(f"[{task.sample_id}] validation_error: {exc}")
        if raw_model_output:
            print(f"[{task.sample_id}] Raw model output:")
            print(raw_model_output)
        print(f"[{task.sample_id}] Saving validation_error result.\n")
    except Exception as exc:
        print(format_skip_message(task.sample_id, exc))
        raw_model_output = extract_raw_model_output(exc)
        if raw_model_output:
            print(f"[{task.sample_id}] Raw model output:")
            print(raw_model_output)
        print(f"[{task.sample_id}] Skipping current sample without saving result.\n")
        return None

    result_path = save_result_json(task.sample_id, payload, model_name=model_name, results_dir_name=results_dir_name)
    payload["result_json_path"] = str(result_path)
    print(format_result_saved(task.sample_id, result_path))
    return payload


def evaluate_task_target(task_target: Path, *, model_name: str, skip_existing: bool, limit: int | None = None) -> None:
    task_paths = resolve_task_target_paths(task_target, project_root=PROJECT_ROOT)
    if limit is not None:
        task_paths = task_paths[:limit]
    total = len(task_paths)
    solved = 0

    for task_index, task_path in enumerate(task_paths, start=1):
        result_path = build_result_path(task_path.stem, model_name=model_name, results_dir_name=infer_results_dir_name(task_path))
        if skip_existing and result_path.exists():
            print(format_skip_existing(task_path, result_path, index=task_index, total=total))
            continue
        print(format_task_progress(task_path, index=task_index, total=total))
        result = evaluate_single_task_json(task_path, model_name=model_name)
        if result is None:
            continue
        if result.get("is_valid_solution"):
            solved += 1

    print(json.dumps({"total_tasks": total, "solved_tasks": solved}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate mechanical lamp tasks in thinking mode with an OpenAI-compatible model.")
    parser.add_argument("task_target", nargs="?", default=str(PROJECT_ROOT / "task"), help="Task JSON or task directory")
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSONL path")
    parser.add_argument("--skip-existing", action="store_true", help="Skip tasks that already have saved results")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to evaluate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = DEFAULT_MODEL_NAME

    target = args.manifest.resolve() if args.manifest else Path(args.task_target).resolve()
    evaluate_task_target(target, model_name=model_name, skip_existing=args.skip_existing, limit=args.limit)


if __name__ == "__main__":
    main()
