from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from eval_common import (
    build_argument_parser,
    build_system_message,
    build_video_content,
    extract_message_output_parts,
    run_eval_loop,
    serialize_usage,
)


DEFAULT_MODEL_NAME = os.getenv("GLM_MODEL_NAME", "glm-5v-turbo")
DEFAULT_BASE_URL = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
DEFAULT_API_KEY = os.getenv("GLM_API_KEY", "1042338736b9443d980979cdfe935688.Zi0RmJGJCvkKP9ZW")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("GLM_TIMEOUT_SECONDS", "600"))
DEFAULT_MAX_TOKENS = int(os.getenv("GLM_MAX_TOKENS", "20000"))
DEFAULT_THINKING_ENABLED = os.getenv("GLM_THINKING_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("GLM_MIN_REQUEST_INTERVAL_SECONDS", "6.5"))

_LAST_GLM_REQUEST_MONOTONIC: float | None = None


def compute_glm_request_delay_seconds(
    last_request_monotonic: float | None,
    *,
    now_monotonic: float,
    min_interval_seconds: float,
) -> float:
    if last_request_monotonic is None or min_interval_seconds <= 0:
        return 0.0
    elapsed = max(0.0, now_monotonic - last_request_monotonic)
    return max(0.0, min_interval_seconds - elapsed)


def throttle_glm_request_rate(
    min_interval_seconds: float,
    *,
    now_fn: Any = time.monotonic,
    sleep_fn: Any = time.sleep,
) -> float:
    global _LAST_GLM_REQUEST_MONOTONIC

    now_monotonic = now_fn()
    delay_seconds = compute_glm_request_delay_seconds(
        _LAST_GLM_REQUEST_MONOTONIC,
        now_monotonic=now_monotonic,
        min_interval_seconds=min_interval_seconds,
    )
    if delay_seconds > 0:
        print(f"[Throttle] Sleeping {delay_seconds:.2f}s before the next GLM request.")
        sleep_fn(delay_seconds)
        now_monotonic = now_fn()

    _LAST_GLM_REQUEST_MONOTONIC = now_monotonic
    return delay_seconds


def build_glm_client(api_key: str, base_url: str, timeout_seconds: float):
    from zai import ZhipuAiClient

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    if timeout_seconds:
        kwargs["timeout"] = timeout_seconds
    try:
        return ZhipuAiClient(**kwargs)
    except TypeError:
        return ZhipuAiClient(api_key=api_key)


def request_completion(client: Any, item_path: Path, eval_item: dict[str, Any], args, retry_note: str | None) -> dict[str, Any]:
    waited = throttle_glm_request_rate(args.min_request_interval_seconds)
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
    thinking_mode = "enabled" if args.thinking_enabled else "disabled"
    request_kwargs["thinking"] = {"type": thinking_mode}

    try:
        response = client.chat.completions.create(**request_kwargs)
    except TypeError:
        request_kwargs.pop("thinking", None)
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
        "rate_limit_wait_seconds": round(waited, 6),
        "reasoning_char_count": len(reasoning_text),
        "reasoning_content": reasoning_text,
        "thinking_request_mode": thinking_mode,
    }


def build_glm_argument_parser():
    parser = build_argument_parser(
        "Run Cut the Rope video-to-command evaluation with GLM models.",
        default_model=DEFAULT_MODEL_NAME,
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=float,
        default=DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
        help="Minimum delay between GLM requests. Defaults to 6.5 seconds.",
    )
    parser.set_defaults(
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        max_tokens=DEFAULT_MAX_TOKENS,
        thinking_enabled=DEFAULT_THINKING_ENABLED,
    )
    return parser


def main() -> int:
    parser = build_glm_argument_parser()
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set GLM_API_KEY or pass --api-key.")

    client = build_glm_client(args.api_key, args.base_url, args.timeout_seconds)
    return run_eval_loop(
        args=args,
        client=client,
        close_client=None,
        provider="zhipu-glm",
        request_completion=request_completion,
    )


if __name__ == "__main__":
    raise SystemExit(main())
