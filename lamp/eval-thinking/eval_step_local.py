from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

import httpx

from engine_interface import evaluate_solution
from validator import validate_task_answer
from eval_common.dataset_io import load_task_json, resolve_task_target_paths
from eval_common.model_io import ModelOutputParseError, extract_text_content, parse_model_answer
from eval_common.network_errors import extract_raw_model_output, format_skip_message
from eval_common.prompting import build_multimodal_messages
from eval_common.result_io import (
    build_result_path,
    format_result_saved,
    format_skip_existing,
    format_task_progress,
    infer_results_dir_name,
    save_result_json,
    utc_timestamp,
)


# ---------------------------------------------------------------------------
# Step Configuration
# ---------------------------------------------------------------------------

STEP_MODEL_NAME = os.getenv("EVAL_MODEL_NAME", "step-1o-turbo-vision")
STEP_BASE_URL = os.getenv("STEP_BASE_URL", "https://api.stepfun.com/v1")
STEP_API_KEY = os.getenv("STEP_API_KEY", "3ZYoEQ57sctL5wZezPEiOYZ25lYRQZOEzkdAYJ1yzRSETWLOp5zE0JVZQSlZQW6N3")
STEP_TIMEOUT_SECONDS = 180.0
STEP_TRUST_ENV = False

# Step models are rate-limited to ~10 requests per minute.
STEP_MIN_REQUEST_INTERVAL_SECONDS = 6.5

_LAST_STEP_REQUEST_AT = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_reasoning_effort_unsupported(exc: BaseException) -> bool:
    message = str(exc).lower()
    if "reasoning_effort" not in message and "reasoning effort" not in message:
        return False
    return any(
        marker in message
        for marker in (
            "unsupported", "not support", "unknown parameter",
            "invalid parameter", "invalid param", "not allowed",
            "unexpected keyword argument",
        )
    )


def wait_for_step_request_slot() -> None:
    global _LAST_STEP_REQUEST_AT

    now = time.monotonic()
    elapsed = now - _LAST_STEP_REQUEST_AT
    remaining = STEP_MIN_REQUEST_INTERVAL_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)
    _LAST_STEP_REQUEST_AT = time.monotonic()


def build_step_client() -> tuple[Any, httpx.Client]:
    from openai import OpenAI

    timeout = httpx.Timeout(timeout=STEP_TIMEOUT_SECONDS, connect=min(STEP_TIMEOUT_SECONDS, 30.0))
    http_client = httpx.Client(timeout=timeout, trust_env=STEP_TRUST_ENV)
    client = OpenAI(
        api_key=STEP_API_KEY or None,
        base_url=STEP_BASE_URL or None,
        timeout=timeout,
        http_client=http_client,
    )
    return client, http_client


def extract_step_stream_text(chunk: Any) -> str:
    """Extract text content from a streaming chunk."""
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return ""
    content = getattr(delta, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
                continue
            if isinstance(item, dict):
                dict_text = item.get("text")
                if isinstance(dict_text, str):
                    parts.append(dict_text)
        return "".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

def build_success_payload(
    *, task: Any, task_source: str, model_name: str,
    raw_model_output: str, engine_result: dict[str, Any],
) -> dict[str, Any]:
    normalized_angles = list(engine_result.get("normalized_angles", []))
    normalized_actions = [
        {"joint": index + 1, "angle": angle}
        for index, angle in enumerate(normalized_angles)
    ]
    return {
        "sample_id": task.sample_id,
        "task_source": task_source,
        "model": {
            "model_name": model_name,
            "base_url": STEP_BASE_URL or None,
            "provider": "step-openai-compatible",
        },
        "raw_model_output": raw_model_output,
        "normalized_answer": {"actions": normalized_actions},
        "engine_result": engine_result,
        "evaluation_status": engine_result.get("evaluation_status"),
        "is_valid_format": True,
        "is_valid_solution": bool(engine_result.get("is_valid_solution", False)),
        "distance": engine_result.get("distance"),
        "task_metadata": task.metadata,
        "saved_at_utc": utc_timestamp(),
    }


def build_error_payload(
    *, task: Any, task_source: str, model_name: str,
    error_message: str, raw_model_output: str = "",
    evaluation_status: str = "format_error",
    error_kind: str = "validation",
) -> dict[str, Any]:
    return {
        "sample_id": task.sample_id,
        "task_source": task_source,
        "model": {
            "model_name": model_name,
            "base_url": STEP_BASE_URL or None,
            "provider": "step-openai-compatible",
        },
        "raw_model_output": raw_model_output,
        "normalized_answer": None,
        "engine_result": None,
        "evaluation_status": evaluation_status,
        "is_valid_format": False,
        "is_valid_solution": False,
        "distance": None,
        "task_metadata": task.metadata,
        "error_kind": error_kind,
        "error_message": error_message,
        "saved_at_utc": utc_timestamp(),
    }


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_task(task: Any, *, task_source: str, model_name: str) -> dict[str, Any]:
    if not STEP_API_KEY or STEP_API_KEY == "YOUR_STEPFUN_APIKEY":
        raise RuntimeError("STEP_API_KEY is empty. Please set STEP_API_KEY.")

    messages = build_multimodal_messages(task, project_root=PROJECT_ROOT)

    client, http_client = build_step_client()
    try:
        wait_for_step_request_slot()
        request_kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "reasoning_effort": "none",
        }
        try:
            response = client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            if not is_reasoning_effort_unsupported(exc):
                raise
            request_kwargs.pop("reasoning_effort", None)
            response = client.chat.completions.create(**request_kwargs)

        chunks: list[str] = []
        for chunk in response:
            text = extract_step_stream_text(chunk)
            if text:
                chunks.append(text)

        raw_model_output = "".join(chunks).strip()
    finally:
        http_client.close()

    validate_task_answer(task, raw_model_output)
    answer = parse_model_answer(
        raw_model_output,
        segment_count=task.segment_count,
        angle_min=int(task.angle_constraints.get("min", -180)),
        angle_max=int(task.angle_constraints.get("max", 180)),
        angle_step=int(task.angle_constraints.get("step", 15)),
    )
    engine_result = evaluate_solution(
        origin=dict(task.public.get("arm_base", {})),
        segments=task.segments,
        angles=answer.angles,
        target=dict(task.validator.get("target", {})),
        light_radius=float(dict(task.validator.get("success_rule", {})).get("radius", task.light_radius)),
        obstacles=list(task.public.get("obstacles", [])),
    )
    return build_success_payload(
        task=task, task_source=task_source, model_name=model_name,
        raw_model_output=raw_model_output, engine_result=engine_result,
    )


def evaluate_single_task_json(task_json_path: Path, *, model_name: str) -> dict[str, Any] | None:
    task_path, task = load_task_json(task_json_path)
    results_dir_name = infer_results_dir_name(task_path)

    try:
        payload = evaluate_task(task, task_source=str(task_path), model_name=model_name)
        print(f"[{task.sample_id}] Solved: {payload.get('is_valid_solution')}")
        print(f"[{task.sample_id}] Output: {payload.get('raw_model_output')}\n")
    except ModelOutputParseError as exc:
        raw_model_output = extract_raw_model_output(exc)
        if getattr(exc, "error_kind", "validation") != "validation":
            print(f"[{task.sample_id}] json_parse_error: {exc}")
            if raw_model_output:
                print(f"[{task.sample_id}] Raw model output:")
                print(raw_model_output)
            print(f"[{task.sample_id}] Skipping current sample without saving result.\n")
            return None

        payload = build_error_payload(
            task=task,
            task_source=str(task_path),
            model_name=model_name,
            error_message=str(exc),
            raw_model_output=raw_model_output,
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate mechanical lamp tasks with Step model.")
    parser.add_argument("task_target", nargs="?", default=str(PROJECT_ROOT / "task"), help="Task JSON or task directory")
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSONL path")
    parser.add_argument("--skip-existing", action="store_true", help="Skip tasks that already have saved results")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to evaluate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = STEP_MODEL_NAME

    target = args.manifest.resolve() if args.manifest else Path(args.task_target).resolve()
    evaluate_task_target(target, model_name=model_name, skip_existing=args.skip_existing, limit=args.limit)


if __name__ == "__main__":
    main()
