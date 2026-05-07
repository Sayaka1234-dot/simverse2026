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


DEFAULT_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-5.4")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://xiaoai.plus/v1")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "600"))
DEFAULT_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "20000"))
DEFAULT_TRUST_ENV = os.getenv("OPENAI_TRUST_ENV", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def supports_openai_reasoning_effort(model_name: str) -> bool:
    lowered = model_name.lower()
    return lowered.startswith(("o1", "o3", "o4", "gpt-5"))


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
        thinking_mode = "provider-default-enabled"
        if supports_openai_reasoning_effort(args.model):
            request_kwargs["reasoning_effort"] = args.reasoning_effort
            thinking_mode = f"reasoning_effort:{args.reasoning_effort}"

    response = client.chat.completions.create(**request_kwargs)
    duration = time.perf_counter() - started_at
    choice = response.choices[0] if response.choices else None
    message = choice.message if choice is not None else None
    raw_text, reasoning = extract_message_output_parts(message)
    return {
        "raw_content_text": raw_text,
        "finish_reason": getattr(choice, "finish_reason", None),
        "response_id": getattr(response, "id", None),
        "response_model": getattr(response, "model", args.model),
        "usage": serialize_usage(getattr(response, "usage", None)),
        "request_duration_seconds": round(duration, 6),
        "reasoning_char_count": len(reasoning),
        "reasoning_content": reasoning,
        "thinking_request_mode": thinking_mode,
    }


def build_openai_compatible_argument_parser():
    parser = build_argument_parser(
        "Run Cut the Rope video-to-command evaluation with an OpenAI-compatible model.",
        default_model=DEFAULT_MODEL_NAME,
    )
    parser.set_defaults(
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        trust_env=DEFAULT_TRUST_ENV,
        max_tokens=DEFAULT_MAX_TOKENS,
        video_part_type="image_frames",
        video_max_frames=8,
        video_frame_width=640,
    )
    return parser


def main() -> int:
    parser = build_openai_compatible_argument_parser()
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set OPENAI_API_KEY or pass --api-key.")

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
        provider="openai-compatible",
        request_completion=request_completion,
    )


if __name__ == "__main__":
    raise SystemExit(main())
