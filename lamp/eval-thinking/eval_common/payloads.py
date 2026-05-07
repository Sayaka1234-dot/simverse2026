from __future__ import annotations

from typing import Any

from eval_common.result_io import utc_timestamp


def build_success_payload(
    *,
    task: Any,
    task_source: str,
    model_name: str,
    base_url: str | None,
    provider: str,
    raw_model_output: str,
    raw_reasoning_content: str,
    raw_final_content: str,
    engine_result: dict[str, Any],
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
            "base_url": base_url,
            "provider": provider,
        },
        "raw_model_output": raw_model_output,
        "raw_reasoning_content": raw_reasoning_content,
        "raw_final_content": raw_final_content,
        "normalized_answer": {
            "actions": normalized_actions,
        },
        "engine_result": engine_result,
        "evaluation_status": engine_result.get("evaluation_status"),
        "is_valid_format": True,
        "is_valid_solution": bool(engine_result.get("is_valid_solution", False)),
        "distance": engine_result.get("distance"),
        "task_metadata": task.metadata,
        "saved_at_utc": utc_timestamp(),
    }


def build_error_payload(
    *,
    task: Any,
    task_source: str,
    model_name: str,
    base_url: str | None,
    provider: str,
    error_message: str,
    raw_model_output: str = "",
    raw_reasoning_content: str = "",
    raw_final_content: str = "",
    evaluation_status: str = "format_error",
    error_kind: str = "validation",
) -> dict[str, Any]:
    return {
        "sample_id": task.sample_id,
        "task_source": task_source,
        "model": {
            "model_name": model_name,
            "base_url": base_url,
            "provider": provider,
        },
        "raw_model_output": raw_model_output,
        "raw_reasoning_content": raw_reasoning_content,
        "raw_final_content": raw_final_content,
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
