from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
TASK_JSON_ROOT = DATA_DIR / "task_jsons"
DEFAULT_MANIFEST_PATH = DATA_DIR / "manifests" / "reconstruct_tasks.jsonl"
DEFAULT_OUTPUT_SAMPLE = TASK_JSON_ROOT / "C001.json"


ANSWER_FACE_ORDER = ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"]
JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
RETRY_AFTER_SECONDS_PATTERN = re.compile(r"retry[_ -]?after[^0-9]{0,20}(\d+)", re.IGNORECASE)

TRANSIENT_RETRY_ATTEMPTS = max(1, int(os.getenv("EVAL_TRANSIENT_RETRY_ATTEMPTS", "3")))
TRANSIENT_RETRY_BASE_DELAY_SECONDS = max(0.0, float(os.getenv("EVAL_TRANSIENT_RETRY_BASE_DELAY_SECONDS", "2")))
TRANSIENT_RETRY_MAX_DELAY_SECONDS = max(
    TRANSIENT_RETRY_BASE_DELAY_SECONDS,
    float(os.getenv("EVAL_TRANSIENT_RETRY_MAX_DELAY_SECONDS", "120")),
)


@dataclass
class FaceObservation:
    patternId: str
    rotation: int
    flipHorizontal: bool = False
    flipVertical: bool = False

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FaceObservation":
        return cls(
            patternId=str(payload.get("patternId", "?")),
            rotation=int(payload.get("rotation", 0)),
            flipHorizontal=bool(payload.get("flipHorizontal", False)),
            flipVertical=bool(payload.get("flipVertical", False)),
        )


@dataclass
class FaceAnswer:
    patternId: str
    rotation: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FaceAnswer":
        return cls(
            patternId=str(payload.get("patternId", "?")),
            rotation=int(payload.get("rotation", 0)),
        )


@dataclass
class TaskImages:
    blank_net_image: str
    path_sequence_image: str


@dataclass
class PuzzleTask:
    sample_id: str
    text_description: str
    net_layout: str
    roll_sequence: List[str]
    observed_path_faces: List[FaceObservation]
    image_paths: TaskImages
    answer: Optional[Dict[str, FaceAnswer]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Raw original JSON dict; preserved for fields that aren't lifted to typed
    # attributes (notably the embedded `prompt: {system, user}` field added by
    # populate_prompts.py for HF-self-contained datasets).
    raw_payload: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["observed_path_faces"] = [asdict(face) for face in self.observed_path_faces]
        if self.answer is not None:
            payload["answer"] = {
                key: asdict(value) for key, value in self.answer.items()
            }
        # raw_payload is internal; don't surface it in the dict serialization.
        payload.pop("raw_payload", None)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PuzzleTask":
        answer = payload.get("answer")
        normalized_answer = None
        if isinstance(answer, dict):
            # SimVerse v1 schema: {"faces": {TOP: ..., ...}}.
            # Legacy schema: top-level is the face map directly.
            face_map: Dict[str, Any] | None = None
            if "faces" in answer and isinstance(answer["faces"], dict):
                face_map = answer["faces"]
            elif all(face_key in answer for face_key in ANSWER_FACE_ORDER):
                face_map = answer
            if face_map is not None:
                normalized_answer = {
                    key: FaceAnswer.from_dict(value)
                    for key, value in face_map.items()
                }

        return cls(
            sample_id=str(payload["sample_id"]),
            text_description=str(payload.get("text_description", "")),
            net_layout=str(payload.get("net_layout", "standard_cross")),
            roll_sequence=[str(item) for item in payload.get("roll_sequence", [])],
            observed_path_faces=[
                FaceObservation.from_dict(face)
                for face in payload.get("observed_path_faces", [])
            ],
            image_paths=TaskImages(**payload["image_paths"]),
            answer=normalized_answer,
            metadata=dict(payload.get("metadata", {})),
            raw_payload=dict(payload),
        )


@dataclass
class ModelAnswer:
    sample_id: str
    answer: Dict[str, FaceAnswer]
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "answer": {key: asdict(value) for key, value in self.answer.items()},
            "raw_text": self.raw_text,
        }


class ModelOutputParseError(Exception):
    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.raw_text = raw_text


def try_load_json_object_from_candidate(candidate: str) -> dict[str, Any] | None:
    variants: list[str] = [candidate.strip()]

    if any(token in candidate for token in ("\\n", "\\r", "\\t")):
        normalized_whitespace = (
            candidate.replace("\\r", "\r")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .strip()
        )
        if normalized_whitespace not in variants:
            variants.append(normalized_whitespace)

    for variant in variants:
        try:
            payload = json.loads(variant)
        except json.JSONDecodeError:
            continue

        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            inner = payload.strip()
            if inner and inner != variant:
                try:
                    nested_payload = json.loads(inner)
                except json.JSONDecodeError:
                    continue
                if isinstance(nested_payload, dict):
                    return nested_payload

    return None


def sanitize_namespace(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._-")
    return normalized or "default"

def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (DATA_DIR / path).resolve()


def load_task_json(task_json_path: str | Path) -> tuple[Path, PuzzleTask]:
    path = Path(task_json_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Task JSON does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, PuzzleTask.from_dict(payload)


def iter_manifest_tasks(manifest_path: str | Path) -> Iterable[PuzzleTask]:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        raise FileNotFoundError(f"Task manifest does not exist: {manifest}")

    with manifest.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield PuzzleTask.from_dict(json.loads(line))


def load_task_from_manifest_by_id(manifest_path: str | Path, sample_id: str) -> PuzzleTask:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        raise FileNotFoundError(f"Task manifest does not exist: {manifest}")

    with manifest.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("sample_id") == sample_id:
                return PuzzleTask.from_dict(payload)

    raise FileNotFoundError(f"sample_id={sample_id!r} not found in {manifest}")


def iter_task_json_files(target_dir: str | Path) -> list[Path]:
    directory = Path(target_dir).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Task directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Task target is not a directory: {directory}")

    ignored = {"model_summary.json", "sample_manifest.json"}
    return sorted(path for path in directory.rglob("*.json") if path.name not in ignored)


def build_result_namespace(model_name: str, explicit_namespace: str | None = None) -> str:
    if explicit_namespace:
        return sanitize_namespace(explicit_namespace)
    return sanitize_namespace(model_name)


def get_results_dir(model_name: str, result_namespace: str | None = None) -> Path:
    model_root = CURRENT_DIR / "results" / sanitize_namespace(model_name)
    namespace = sanitize_namespace(result_namespace or model_name)
    return model_root / namespace


def build_result_path(
    task_json_path: str | Path,
    *,
    model_name: str,
    result_namespace: str | None = None,
) -> Path:
    task_path = Path(task_json_path).resolve()
    result_root = get_results_dir(model_name, result_namespace)
    try:
        relative = task_path.relative_to(TASK_JSON_ROOT.resolve())
    except ValueError:
        relative = Path(task_path.name)
    return (result_root / relative).resolve()


def build_result_path_for_sample(
    sample_id: str,
    *,
    model_name: str,
    result_namespace: str | None = None,
) -> Path:
    return (get_results_dir(model_name, result_namespace) / f"{sample_id}.json").resolve()


def save_result_json(
    task_json_path: str | Path,
    payload: dict[str, Any],
    *,
    model_name: str,
    result_namespace: str | None = None,
) -> Path:
    result_path = build_result_path(
        task_json_path,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


def save_result_json_for_sample(
    sample_id: str,
    payload: dict[str, Any],
    *,
    model_name: str,
    result_namespace: str | None = None,
) -> Path:
    result_path = build_result_path_for_sample(
        sample_id,
        model_name=model_name,
        result_namespace=result_namespace,
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


def build_output_schema_text() -> str:
    lines = [
        "{",
        '  "TOP": {"patternId": "...", "rotation": 0},',
        '  "BOTTOM": {"patternId": "...", "rotation": 0},',
        '  "FRONT": {"patternId": "...", "rotation": 0},',
        '  "BACK": {"patternId": "...", "rotation": 0},',
        '  "LEFT": {"patternId": "...", "rotation": 0},',
        '  "RIGHT": {"patternId": "...", "rotation": 0}',
        "}",
    ]
    return "\n".join(lines)


def collect_allowed_pattern_ids_for_prompt(task: PuzzleTask) -> list[str]:
    allowed: list[str] = []
    seen: set[str] = set()

    for face in task.observed_path_faces:
        pattern_id = str(face.patternId)
        if pattern_id and pattern_id not in seen:
            allowed.append(pattern_id)
            seen.add(pattern_id)

    if "?" not in seen:
        allowed.append("?")

    return allowed


def build_observed_faces_text_for_prompt(task: PuzzleTask) -> str:
    lines: list[str] = []
    for index, face in enumerate(task.observed_path_faces, 1):
        flags: list[str] = []
        if face.flipHorizontal:
            flags.append("flipHorizontal=true")
        if face.flipVertical:
            flags.append("flipVertical=true")
        flag_text = ", ".join(flags) if flags else "no_flip"
        lines.append(
            f"- Step {index}: patternId={face.patternId}, rotation={face.rotation}, {flag_text}"
        )
    return "\n".join(lines) if lines else "- No observed path faces provided."


# 中文对照：
# - 只返回一个合法 JSON 对象，不要输出分析过程。
# - 顶层键必须是 TOP / BOTTOM / FRONT / BACK / LEFT / RIGHT。
# - 每个面都必须包含 patternId 和 rotation。
# - rotation 只能是 0 / 90 / 180 / 270。
# - 如果某个面无法唯一确定，就输出 patternId="?" 且 rotation=0。
# - patternId 只能从用户消息里给出的候选列表中选择，不能瞎猜新图案。
def build_system_prompt_for_eval() -> str:
    """SimVerse v1: delegates to prompts.build_system_prompt for a single source of truth.
    Kept under the legacy name so the provider variants keep importing it."""
    from prompts import build_system_prompt
    return build_system_prompt()


# 中文对照：
# - 题面由两张图组成：空白十字展开图、路径俯视图案图。
# - 额外给模型滚动序列、观测图案元数据、可用 patternId 列表。
# - 模型只能在这些 patternId 里选答案，不能输出列表之外的内容。
def build_user_prompt_for_eval(task: PuzzleTask) -> str:
    """SimVerse v1: delegates to prompts.build_user_prompt."""
    from prompts import build_user_prompt
    return build_user_prompt(task)


def encode_image(image_path: Path) -> str:
    with image_path.open("rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def build_client(
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
    trust_env: bool,
) -> tuple[Any, Any]:
    import httpx
    from openai import OpenAI

    timeout = httpx.Timeout(
        timeout=timeout_seconds,
        connect=min(timeout_seconds, 30.0),
    )
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    client = OpenAI(
        api_key=api_key or None,
        base_url=base_url or None,
        timeout=timeout,
        http_client=http_client,
    )
    return client, http_client


def extract_text_content(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
                content_text = item.get("content")
                if isinstance(content_text, str):
                    parts.append(content_text)
                    continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
                continue
            content_text = getattr(item, "content", None)
            if isinstance(content_text, str):
                parts.append(content_text)
        return "\n".join(part for part in parts if part).strip()

    if isinstance(content, dict):
        for key in ("text", "content", "reasoning", "reasoning_content", "analysis", "thinking"):
            value = content.get(key)
            extracted = extract_text_content(value)
            if extracted:
                return extracted
        return json.dumps(content, ensure_ascii=False)

    return str(content).strip()


def extract_reasoning_content(message: Any) -> str:
    if message is None:
        return ""

    values: list[Any] = []
    for key in ("reasoning_content", "reasoning", "thinking", "analysis", "reasoning_text"):
        if isinstance(message, dict) and key in message:
            values.append(message.get(key))
            continue
        value = getattr(message, key, None)
        if value is not None:
            values.append(value)

    parts: list[str] = []
    for value in values:
        extracted = extract_text_content(value)
        if extracted:
            parts.append(extracted)

    return "\n".join(part for part in parts if part).strip()


def split_reasoning_from_raw_output(raw_text: str) -> tuple[str, str]:
    stripped = raw_text.strip()
    if not stripped:
        return "", ""

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return stripped, ""

    reasoning_prefix = stripped[:start].strip()
    reasoning_suffix = stripped[end + 1 :].strip()
    reasoning = "\n\n".join(part for part in (reasoning_prefix, reasoning_suffix) if part)
    json_text = stripped[start : end + 1].strip()
    return reasoning, json_text


def extract_message_output_parts(message: Any) -> tuple[str, str]:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")

    raw_output = extract_text_content(content)
    reasoning_output = extract_reasoning_content(message)
    if not reasoning_output and raw_output:
        reasoning_output, _ = split_reasoning_from_raw_output(raw_output)

    return raw_output, reasoning_output


def extract_completion_output_parts(completion: Any) -> tuple[str, str]:
    if completion is None:
        return "", ""

    if isinstance(completion, str):
        raw_output = completion.strip()
        reasoning_output, _ = split_reasoning_from_raw_output(raw_output)
        return raw_output, reasoning_output

    if isinstance(completion, dict):
        choices = completion.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message") or first_choice.get("delta") or first_choice
            else:
                message = getattr(first_choice, "message", None) or getattr(first_choice, "delta", None) or first_choice
            return extract_message_output_parts(message)

        return extract_message_output_parts(completion)

    choices = getattr(completion, "choices", None)
    if choices:
        first_choice = choices[0]
        message = getattr(first_choice, "message", None) or getattr(first_choice, "delta", None) or first_choice
        return extract_message_output_parts(message)

    return extract_message_output_parts(completion)


def extract_stream_chunk_parts(chunk: Any) -> tuple[str, str]:
    """Extract raw content and reasoning from a single streaming delta."""
    if chunk is None:
        return "", ""
        
    choices = getattr(chunk, "choices", None)
    if isinstance(chunk, dict) and choices is None:
        choices = chunk.get("choices")
        
    if not choices:
        return "", ""
        
    first_choice = choices[0]
    if isinstance(first_choice, dict):
        delta = first_choice.get("delta") or first_choice.get("message") or first_choice
    else:
        delta = getattr(first_choice, "delta", None) or getattr(first_choice, "message", None) or first_choice

    if delta is None:
        return "", ""

    content = getattr(delta, "content", None)
    if content is None and isinstance(delta, dict):
        content = delta.get("content")
        
    raw_output = extract_text_content(content)
    reasoning_output = extract_reasoning_content(delta)
    
    return raw_output, reasoning_output


def extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                payload = try_load_json_object_from_candidate(candidate)
                if payload is not None:
                    return payload
            if "\n" in candidate:
                maybe_json = candidate.split("\n", 1)[1].strip()
                if maybe_json.startswith("{") and maybe_json.endswith("}"):
                    payload = try_load_json_object_from_candidate(maybe_json)
                    if payload is not None:
                        return payload

    if stripped.startswith("{") and stripped.endswith("}"):
        payload = try_load_json_object_from_candidate(stripped)
        if payload is not None:
            return payload

    decoder = json.JSONDecoder()
    candidates: list[tuple[dict[str, Any], int]] = []
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, end_index = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append((payload, end_index))

    if candidates:
        full_answer_candidates = [
            (payload, end_index)
            for payload, end_index in candidates
            if all(face_key in payload for face_key in ANSWER_FACE_ORDER)
        ]
        if full_answer_candidates:
            full_answer_candidates.sort(
                key=lambda item: (item[1], len(item[0])),
            )
            return full_answer_candidates[-1][0]

        candidates.sort(key=lambda item: (item[1], len(item[0])))
        return candidates[-1][0]

    match = JSON_BLOCK_PATTERN.search(stripped)
    if match:
        payload = try_load_json_object_from_candidate(match.group(0))
        if payload is not None:
            return payload
        raise ModelOutputParseError("Invalid JSON in matched block.", raw_text=raw_text)

    raise ModelOutputParseError("Model output does not contain a valid JSON object.", raw_text=raw_text)


def is_api_network_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))

        module_name = type(current).__module__
        class_name = type(current).__name__
        message = str(current).lower()
        status_code = getattr(current, "status_code", None)

        if module_name.startswith("httpx") or module_name.startswith("httpcore"):
            # Treat transport/connectivity failures as transient.
            if isinstance(status_code, int):
                if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
                    return True
            if any(
                marker in class_name.lower()
                for marker in (
                    "connect",
                    "timeout",
                    "network",
                    "proxy",
                    "remoteprotocol",
                    "read",
                    "write",
                )
            ):
                return True

        if module_name.startswith("openai") and (
            "connection" in class_name.lower() or "timeout" in class_name.lower()
        ):
            return True

        if isinstance(status_code, int) and status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
            return True

        if any(
            marker in message
            for marker in (
                "connection error",
                "api connection",
                "timed out",
                "timeout",
                "connection reset",
                "connection aborted",
                "connection refused",
                "temporary failure in name resolution",
                "name or service not known",
                "nodename nor servname provided",
                "dns",
                "remote protocol error",
                "server disconnected",
                "network is unreachable",
                "read error",
                "write error",
                "proxy error",
                "rate limit",
                "too many requests",
                "bad gateway",
                "gateway timeout",
                "service unavailable",
                "temporarily unavailable",
                "internal server error",
                "upstream",
                "overloaded",
                "429",
                "502",
                "503",
                "504",
            )
        ):
            return True

        current = current.__cause__ or current.__context__

    return False


def is_model_output_parse_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, ModelOutputParseError):
            return True
        current = current.__cause__ or current.__context__

    return False


def should_skip_result_write(exc: BaseException) -> bool:
    return is_api_network_error(exc) or is_model_output_parse_error(exc)


def describe_skip_reason(exc: BaseException) -> str:
    current: BaseException | None = exc
    visited: set[int] = set()
    parts: list[str] = []

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        name = type(current).__name__
        message = str(current).strip()
        parts.append(f"{name}: {message}" if message else name)
        current = current.__cause__ or current.__context__

    return " -> ".join(parts) if parts else repr(exc)


def extract_retry_after_seconds(exc: BaseException) -> float | None:
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))

        value = getattr(current, "retry_after", None)
        if isinstance(value, (int, float)) and value >= 0:
            return float(value)

        response = getattr(current, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers is not None:
                retry_after_header = None
                if isinstance(headers, dict):
                    retry_after_header = headers.get("retry-after") or headers.get("Retry-After")
                else:
                    retry_after_header = headers.get("retry-after") or headers.get("Retry-After")
                if retry_after_header is not None:
                    try:
                        return float(retry_after_header)
                    except (TypeError, ValueError):
                        pass

        message = str(current)
        match = RETRY_AFTER_SECONDS_PATTERN.search(message)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        current = current.__cause__ or current.__context__

    return None


def compute_transient_retry_delay_seconds(exc: BaseException, attempt_index: int) -> float:
    retry_after_seconds = extract_retry_after_seconds(exc)
    if retry_after_seconds is not None:
        return min(max(0.0, retry_after_seconds), TRANSIENT_RETRY_MAX_DELAY_SECONDS)

    exponential_delay = TRANSIENT_RETRY_BASE_DELAY_SECONDS * (2 ** max(attempt_index, 0))
    return min(exponential_delay, TRANSIENT_RETRY_MAX_DELAY_SECONDS)


def normalize_answer_payload(payload: dict[str, Any], sample_id: str, raw_text: str) -> ModelAnswer:
    # SimVerse v1: model output is `{"faces": {...}}`. Legacy: bare face map.
    if isinstance(payload, dict) and "faces" in payload and isinstance(payload["faces"], dict):
        faces = payload["faces"]
    else:
        faces = payload

    answer: dict[str, FaceAnswer] = {}
    for face_key in ANSWER_FACE_ORDER:
        if face_key not in faces:
            raise ModelOutputParseError(f"Missing answer face: {face_key}", raw_text=raw_text)

        face_payload = faces[face_key]
        answer[face_key] = FaceAnswer(
            patternId=str(face_payload["patternId"]),
            rotation=int(face_payload["rotation"]),
        )

    return ModelAnswer(sample_id=sample_id, answer=answer, raw_text=raw_text)


def parse_model_answer_or_raise(raw_text: str, sample_id: str) -> ModelAnswer:
    payload = extract_json_object(raw_text)
    return normalize_answer_payload(payload, sample_id, raw_text)


def build_multimodal_messages_for_eval(task: PuzzleTask) -> list[dict[str, Any]]:
    """SimVerse v1: delegates to prompts.build_messages."""
    from prompts import build_messages
    return build_messages(task)


def request_model_answer(
    task: PuzzleTask,
    model_name: str,
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
    trust_env: bool,
    max_tokens: int,
) -> tuple[str, ModelAnswer, str]:
    if not api_key:
        raise RuntimeError("DEFAULT_API_KEY is empty. Please edit the config section in eval-thinking/eval_local.py.")
    messages = build_multimodal_messages_for_eval(task)
    last_error: Exception | None = None

    for attempt_index in range(TRANSIENT_RETRY_ATTEMPTS):
        client, http_client = build_client(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            trust_env=trust_env,
        )
        try:
            request_kwargs = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "stream": True,
            }
            response = client.chat.completions.create(**request_kwargs)
            
            raw_parts: list[str] = []
            reasoning_parts: list[str] = []
            
            for chunk in response:
                chunk_raw, chunk_reasoning = extract_stream_chunk_parts(chunk)
                if chunk_raw:
                    raw_parts.append(chunk_raw)
                if chunk_reasoning:
                    reasoning_parts.append(chunk_reasoning)
                    
            raw_text = "".join(raw_parts)
            reasoning_output = "".join(reasoning_parts)
            
            if not reasoning_output and raw_text:
                reasoning_output, _ = split_reasoning_from_raw_output(raw_text)
            if not raw_text and reasoning_output:
                raw_text = reasoning_output
                
            print(f"\n[Model Raw Output] {task.sample_id} | {model_name}")
            print(raw_text)
            print("[End Model Raw Output]\n")

            payload = extract_json_object(raw_text)
            answer = normalize_answer_payload(payload, task.sample_id, raw_text)
            return raw_text, answer, reasoning_output
        except Exception as exc:
            last_error = exc
            is_retryable = is_api_network_error(exc)
            has_next_attempt = attempt_index < TRANSIENT_RETRY_ATTEMPTS - 1
            if not is_retryable or not has_next_attempt:
                raise

            delay_seconds = compute_transient_retry_delay_seconds(exc, attempt_index)
            print(
                f"[Retry {attempt_index + 1}/{TRANSIENT_RETRY_ATTEMPTS - 1}] "
                f"{task.sample_id} after transient failure. Waiting {delay_seconds:.1f}s."
            )
            print(f"Retry reason: {describe_skip_reason(exc)}")
            time.sleep(delay_seconds)
        finally:
            http_client.close()

    assert last_error is not None
    raise last_error
