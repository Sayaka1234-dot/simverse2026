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
from eval_common.model_io import (
    ModelOutputParseError,
    build_chat_completion_request,
    extract_reasoning_content,
    extract_text_content,
    split_reasoning_and_final_output,
)
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

DEFAULT_MODEL_NAME = os.getenv("QWEN_OPEN_MODEL_NAME", "Qwen/Qwen3.5-397B-A17B")
DEFAULT_BASE_URL = os.getenv(
    "QWEN_OPEN_BASE_URL",
    os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
)
DEFAULT_API_KEY = os.getenv(
    "QWEN_OPEN_API_KEY",
    os.getenv("SILICONFLOW_API_KEY", ""),
)
DEFAULT_TIMEOUT_SECONDS = float(
    os.getenv("QWEN_OPEN_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "900"))
)
DEFAULT_TRUST_ENV = os.getenv(
    "QWEN_OPEN_TRUST_ENV",
    os.getenv("OPENAI_TRUST_ENV", "false"),
).strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_MAX_TOKENS = int(os.getenv("QWEN_OPEN_MAX_TOKENS", "10000"))


def build_openai_client(
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
    trust_env: bool,
) -> tuple[Any, httpx.Client]:
    from openai import OpenAI

    timeout = httpx.Timeout(timeout=timeout_seconds, connect=min(timeout_seconds, 30.0))
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    client = OpenAI(
        api_key=api_key or None,
        base_url=base_url or None,
        timeout=timeout,
        http_client=http_client,
    )
    return client, http_client


def evaluate_task(
    task: Any,
    *,
    task_source: str,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    trust_env: bool,
    max_tokens: int,
) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("QWEN_OPEN_API_KEY or SILICONFLOW_API_KEY is required for eval-thinking/eval_qwen_open_local.py")

    messages = build_multimodal_messages(task, project_root=PROJECT_ROOT)

    client, http_client = build_openai_client(
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        trust_env=trust_env,
    )
    try:
        response = client.chat.completions.create(
            **build_chat_completion_request(
                model_name=model_name,
                messages=messages,
                max_tokens=max_tokens,
            )
        )
        message = response.choices[0].message
        raw_model_output = extract_text_content(message.content)
        reasoning_from_provider = extract_reasoning_content(message)
    finally:
        http_client.close()

    prompt_reasoning, raw_final_content = split_reasoning_and_final_output(raw_model_output)
    raw_reasoning_content = reasoning_from_provider or prompt_reasoning
    parsed_answer = validate_task_answer(
        task,
        raw_final_content,
        allow_missing_joints=True,
        missing_joint_default_angle=0,
    )
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
        base_url=base_url or None,
        provider="siliconflow-openai-compatible-thinking",
        raw_model_output=raw_model_output,
        raw_reasoning_content=raw_reasoning_content,
        raw_final_content=raw_final_content,
        engine_result=engine_result,
    )


def evaluate_single_task_json(
    task_json_path: Path,
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    trust_env: bool,
    max_tokens: int,
) -> dict[str, Any] | None:
    task_path, task = load_task_json(task_json_path)
    results_dir_name = infer_results_dir_name(task_path)

    try:
        payload = evaluate_task(
            task,
            task_source=str(task_path),
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            trust_env=trust_env,
            max_tokens=max_tokens,
        )
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
            base_url=base_url or None,
            provider="siliconflow-openai-compatible-thinking",
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


def evaluate_task_target(
    task_target: Path,
    *,
    model_name: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    trust_env: bool,
    max_tokens: int,
    skip_existing: bool,
    limit: int | None = None,
) -> None:
    task_paths = resolve_task_target_paths(task_target, project_root=PROJECT_ROOT)
    if limit is not None:
        task_paths = task_paths[:limit]
    total = len(task_paths)
    solved = 0

    for task_index, task_path in enumerate(task_paths, start=1):
        result_path = build_result_path(
            task_path.stem,
            model_name=model_name,
            results_dir_name=infer_results_dir_name(task_path),
        )
        if skip_existing and result_path.exists():
            print(format_skip_existing(task_path, result_path, index=task_index, total=total))
            continue
        print(format_task_progress(task_path, index=task_index, total=total))
        result = evaluate_single_task_json(
            task_path,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            trust_env=trust_env,
            max_tokens=max_tokens,
        )
        if result is None:
            continue
        if result.get("is_valid_solution"):
            solved += 1

    print(json.dumps({"total_tasks": total, "solved_tasks": solved}, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate mechanical lamp tasks in thinking mode with Qwen Open models.")
    parser.add_argument("task_target", nargs="?", default=str(PROJECT_ROOT / "task"), help="Task JSON, task directory, selection JSON, or manifest JSONL")
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSONL path")
    parser.add_argument("--skip-existing", action="store_true", help="Skip tasks that already have saved results")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to evaluate")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--trust-env",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_TRUST_ENV,
        help="Whether to trust proxy settings from environment variables.",
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    target = args.manifest.resolve() if args.manifest else Path(args.task_target).resolve()
    evaluate_task_target(
        target,
        model_name=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        trust_env=args.trust_env,
        max_tokens=args.max_tokens,
        skip_existing=args.skip_existing,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
