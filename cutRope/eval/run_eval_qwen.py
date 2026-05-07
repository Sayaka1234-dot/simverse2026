from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from eval_common import (
    build_argument_parser,
    build_openai_client,
    build_system_message,
    build_video_content,
    extract_message_output_parts,
    run_eval_loop,
    serialize_usage,
)


DEFAULT_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen3.6-plus")
DEFAULT_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
DEFAULT_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("QWEN_TIMEOUT_SECONDS", "600"))
DEFAULT_MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "10000"))
DEFAULT_TRUST_ENV = os.getenv("QWEN_TRUST_ENV", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def request_completion(client: Any, item_path: Path, eval_item: dict[str, Any], args, retry_note: str | None) -> dict[str, Any]:
    started_at = time.perf_counter()
    request_kwargs: dict[str, Any] = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": build_system_message()},
            {
                "role": "user",
                "content": build_video_content(
                    item_path,
                    eval_item,
                    retry_note=retry_note,
                    video_source=args.video_source,
                    video_part_type=args.video_part_type,
                    video_detail=args.video_detail,
                    video_max_frames=args.video_max_frames,
                    video_fps=args.video_fps,
                    video_frame_width=args.video_frame_width,
                    video_frame_quality=args.video_frame_quality,
                ),
            },
        ],
        "max_tokens": args.max_tokens,
    }
    thinking_mode = "disabled"
    if args.thinking_enabled:
        request_kwargs["extra_body"] = {"enable_thinking": True}
        thinking_mode = "enabled"

    try:
        response = client.chat.completions.create(**request_kwargs)
    except TypeError:
        request_kwargs.pop("extra_body", None)
        response = client.chat.completions.create(**request_kwargs)
        thinking_mode = "request-unsupported"
    choice = response.choices[0] if response.choices else None
    message = choice.message if choice is not None else None
    raw_text, reasoning_text = extract_message_output_parts(message)
    return {
        "raw_content_text": raw_text,
        "finish_reason": getattr(choice, "finish_reason", None),
        "response_id": getattr(response, "id", None),
        "response_model": getattr(response, "model", args.model),
        "usage": serialize_usage(getattr(response, "usage", None)),
        "request_duration_seconds": round(time.perf_counter() - started_at, 6),
        "reasoning_char_count": len(reasoning_text),
        "reasoning_content": reasoning_text,
        "thinking_request_mode": thinking_mode,
    }


def build_qwen_argument_parser():
    parser = build_argument_parser(
        "Run Cut the Rope video-to-command evaluation with DashScope Qwen models.",
        default_model=DEFAULT_MODEL_NAME,
    )
    parser.set_defaults(
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        trust_env=DEFAULT_TRUST_ENV,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    return parser


def main() -> int:
    parser = build_qwen_argument_parser()
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set DASHSCOPE_API_KEY or pass --api-key.")

    client, http_client = build_openai_client(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
        trust_env=args.trust_env,
    )
    return run_eval_loop(
        args=args,
        client=client,
        close_client=http_client.close,
        provider="dashscope-qwen",
        request_completion=request_completion,
    )


if __name__ == "__main__":
    raise SystemExit(main())
