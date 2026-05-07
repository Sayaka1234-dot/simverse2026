from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))

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
# GLM Configuration
# ---------------------------------------------------------------------------

GLM_MODEL_NAME = os.getenv("EVAL_MODEL_NAME", "glm-5v-turbo")
GLM_API_KEY = os.getenv("GLM_API_KEY", "1042338736b9443d980979cdfe935688.Zi0RmJGJCvkKP9ZW")
GLM_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
GLM_THINKING = {"type": "disabled"}
GLM_MAX_TOKENS = 8000


# ---------------------------------------------------------------------------
# GLM Client
# ---------------------------------------------------------------------------

def build_glm_client() -> Any:
    try:
        from zai import ZhipuAiClient
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The official ZAI SDK is not installed. "
            "Please install: pip install zai"
        ) from exc

    return ZhipuAiClient(api_key=GLM_API_KEY)


def extract_glm_message_text(message: Any) -> str:
    """Extract text from a GLM response message object."""
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return extract_text_content(content)


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
            "base_url": GLM_BASE_URL,
            "provider": "zhipu-zai",
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
            "base_url": GLM_BASE_URL,
            "provider": "zhipu-zai",
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
    if not GLM_API_KEY or GLM_API_KEY == "YOUR_GLM_API_KEY":
        raise RuntimeError("GLM_API_KEY is empty. Please set GLM_API_KEY.")

    messages = build_multimodal_messages(task, project_root=PROJECT_ROOT)

    client = build_glm_client()
    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "max_tokens": GLM_MAX_TOKENS,
        "thinking": GLM_THINKING,
    }

    response = client.chat.completions.create(**request_kwargs)
    raw_model_output = extract_glm_message_text(response.choices[0].message).strip()

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
    parser = argparse.ArgumentParser(description="Evaluate mechanical lamp tasks with GLM model.")
    parser.add_argument("task_target", nargs="?", default=str(PROJECT_ROOT / "task"), help="Task JSON or task directory")
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSONL path")
    parser.add_argument("--skip-existing", action="store_true", help="Skip tasks that already have saved results")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to evaluate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = GLM_MODEL_NAME

    target = args.manifest.resolve() if args.manifest else Path(args.task_target).resolve()
    evaluate_task_target(target, model_name=model_name, skip_existing=args.skip_existing, limit=args.limit)


if __name__ == "__main__":
    main()
