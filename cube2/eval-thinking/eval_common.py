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
from typing import Any, Dict, Iterable, List


# DEFAULT_MODEL_NAME:
# 默认评测模型名，直接改这里即可。

CURRENT_DIR = Path(__file__).resolve().parent
NEWCUBE_ROOT = CURRENT_DIR.parent
DATA_DIR = NEWCUBE_ROOT / "data2"
TASK_JSON_ROOT = DATA_DIR / "task_jsons"
DEFAULT_MANIFEST_PATH = DATA_DIR / "manifests" / "goal_roll_tasks.jsonl"
DEFAULT_OUTPUT_SAMPLE = TASK_JSON_ROOT / "C001.json"

# =========================
# Config section: edit only these values
# =========================
# DEFAULT_BASE_URL:
# OpenAI 兼容接口地址。留空则使用官方默认地址。

# DEFAULT_API_KEY:
# 默认 API Key。也可以用 OPENAI_API_KEY 环境变量覆盖。

# DEFAULT_TIMEOUT_SECONDS:
# 请求超时时间，单位秒。

# DEFAULT_MAX_TOKENS:
# 模型最大输出 token。

# DEFAULT_TRUST_ENV:
# 是否读取系统代理环境变量。

# DEFAULT_MAX_DIRECTION_STEPS:
# 允许模型输出的最大滚动步数，避免无上界输出。
# DEFAULT_MAX_DIRECTION_STEPS:
# Shared task constraint used by all cube2 evaluation entrypoints.
DEFAULT_MAX_DIRECTION_STEPS = 20


VALID_DIRECTIONS = ["N", "S", "E", "W"]
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

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FaceObservation":
        return cls(
            patternId=str(payload.get("patternId", "?")),
            rotation=int(payload.get("rotation", 0)),
        )

    def to_prompt_text(self) -> str:
        return f"patternId={self.patternId}, rotation={self.rotation}"


@dataclass
class NetCell:
    faceKey: str
    faceLabelZh: str
    row: int
    col: int
    patternId: str
    rotation: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "NetCell":
        return cls(
            faceKey=str(payload.get("faceKey", "")),
            faceLabelZh=str(payload.get("faceLabelZh", "")),
            row=int(payload.get("row", 0)),
            col=int(payload.get("col", 0)),
            patternId=str(payload.get("patternId", "?")),
            rotation=int(payload.get("rotation", 0)),
        )


@dataclass
class TaskImages:
    initialNetImage: str = ""
    targetTopFaceImage: str = ""


@dataclass
class GoalRollTask:
    sample_id: str
    task_type: str
    source_task_type: str
    name: str
    description: str
    net_cells: List[NetCell]
    visible_solution_faces: Dict[str, Dict[str, Any]]
    target_top_face: FaceObservation
    reference_directions: List[str]
    image_paths: TaskImages = field(default_factory=TaskImages)
    metadata: Dict[str, Any] = field(default_factory=dict)
    true_solution_faces: Dict[str, FaceObservation] = field(default_factory=dict)
    # Raw original JSON dict; preserved for fields not lifted to typed attributes
    # (notably the embedded `prompt: {system, user}` for HF-self-contained datasets).
    raw_payload: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GoalRollTask":
        initial_cube = dict(payload.get("initialCube", {}))
        net = dict(initial_cube.get("net", {}))
        visible_solution_faces = {
            str(key): {
                "patternId": str(value.get("patternId", "?")),
                "rotation": int(value.get("rotation", 0)),
            }
            for key, value in dict(initial_cube.get("solutionFaces", {})).items()
        }
        true_solution_faces = {
            str(key): FaceObservation.from_dict(value)
            for key, value in dict(initial_cube.get("trueSolutionFaces", {})).items()
        }

        # SimVerse v1: gold reference lives at payload["answer"]["directions"].
        # Legacy locations: payload["answers"]["directions"] or payload["rollSequence"].
        reference_directions: List[str] = []
        v1_answer = payload.get("answer")
        if isinstance(v1_answer, dict) and isinstance(v1_answer.get("directions"), list):
            reference_directions = [str(item) for item in v1_answer["directions"]]
        if not reference_directions:
            legacy_answers = payload.get("answers")
            if isinstance(legacy_answers, dict) and isinstance(legacy_answers.get("directions"), list):
                reference_directions = [str(item) for item in legacy_answers["directions"]]
        if not reference_directions and isinstance(payload.get("rollSequence"), list):
            reference_directions = [str(item) for item in payload["rollSequence"]]

        return cls(
            sample_id=str(payload.get("code") or payload.get("sample_id")),
            task_type=str(payload.get("taskType", "roll_to_target_top_face")),
            source_task_type=str(payload.get("sourceTaskType", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            net_cells=[NetCell.from_dict(item) for item in net.get("cells", [])],
            visible_solution_faces=visible_solution_faces,
            true_solution_faces=true_solution_faces,
            target_top_face=FaceObservation.from_dict(payload.get("targetTopFace", {})),
            reference_directions=reference_directions,
            image_paths=TaskImages(**dict(payload.get("imagePaths", {}))),
            metadata=dict(payload.get("metadata", {})),
            raw_payload=dict(payload),
        )


@dataclass
class ModelAnswer:
    sample_id: str
    directions: List[str]
    raw_text: str = ""


class ModelOutputParseError(Exception):
    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.raw_text = raw_text


def sanitize_namespace(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._-")
    return normalized or "default"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_task_json(task_json_path: str | Path) -> tuple[Path, GoalRollTask]:
    path = Path(task_json_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Task JSON does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, GoalRollTask.from_dict(payload)


def iter_manifest_tasks(manifest_path: str | Path) -> Iterable[GoalRollTask]:
    manifest = Path(manifest_path).resolve()
    if not manifest.exists():
        raise FileNotFoundError(f"Task manifest does not exist: {manifest}")
    with manifest.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield GoalRollTask.from_dict(json.loads(line))


def load_task_from_manifest_by_id(manifest_path: str | Path, sample_id: str) -> GoalRollTask:
    for task in iter_manifest_tasks(manifest_path):
        if task.sample_id == sample_id:
            return task
    raise FileNotFoundError(f"sample_id={sample_id!r} not found in {manifest_path}")


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


def format_net_layout_for_prompt(task: GoalRollTask) -> str:
    cells_by_key = {cell.faceKey: cell for cell in task.net_cells}
    row0 = cells_by_key.get("BACK")
    row1_left = cells_by_key.get("LEFT")
    row1_mid = cells_by_key.get("TOP")
    row1_right = cells_by_key.get("RIGHT")
    row2 = cells_by_key.get("FRONT")
    row3 = cells_by_key.get("BOTTOM")

    def cell_text(cell: NetCell | None) -> str:
        if cell is None:
            return "[empty]"
        return f"[{cell.faceKey}: patternId={cell.patternId}, rotation={cell.rotation}]"

    return "\n".join(
        [
            f"  {cell_text(row0)}",
            f"{cell_text(row1_left)} {cell_text(row1_mid)} {cell_text(row1_right)}",
            f"  {cell_text(row2)}",
            f"  {cell_text(row3)}",
        ]
    )


def format_net_faces_list_for_prompt(task: GoalRollTask) -> str:
    ordered = sorted(task.net_cells, key=lambda item: (item.row, item.col, item.faceKey))
    lines = []
    for cell in ordered:
        lines.append(
            f"- {cell.faceKey}: patternId={cell.patternId}, rotation={cell.rotation}"
        )
    return "\n".join(lines)


def build_rotation_legend_text() -> str:
    return (
        "The number shown under each visible net cell is the clockwise rotation from the original upright pattern, "
        "measured in degrees."
    )


def build_output_schema_text() -> str:
    return "\n".join(
        [
            "{",
            '  "directions": ["N", "E"]',
            "}",
        ]
    )


# 中文对照：
# - 任务不是还原六个面，而是设计一个滚动序列。
# - 可以内部思考，但绝对不要输出思考过程。
# - 只输出一个 JSON 对象，顶层只保留 directions。
def build_system_prompt_for_eval() -> str:
    """SimVerse v1: delegates to prompts.build_system_prompt."""
    from prompts import build_system_prompt
    return build_system_prompt()


# 中文对照：
# - 题面给的是当前可见十字展开图和目标顶面图案。
# - 目标判定按“俯视立方体顶面”的图案与朝向比较。
# - 允许多解，不要求和参考序列一致。
def build_user_prompt_for_eval(task: GoalRollTask) -> str:
    """SimVerse v1: delegates to prompts.build_user_prompt."""
    from prompts import build_user_prompt
    return build_user_prompt(task)


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


def extract_json_object(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return json.loads(candidate)
            if "\n" in candidate:
                maybe_json = candidate.split("\n", 1)[1].strip()
                if maybe_json.startswith("{") and maybe_json.endswith("}"):
                    return json.loads(maybe_json)

    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append(payload)

    if candidates:
        return candidates[-1]

    match = JSON_BLOCK_PATTERN.search(stripped)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ModelOutputParseError(f"Invalid JSON in matched block: {exc}", raw_text=raw_text) from exc
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
                "dns",
                "proxy error",
                "rate limit",
                "too many requests",
                "bad gateway",
                "gateway timeout",
                "service unavailable",
                "internal server error",
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


def normalize_direction_token(token: Any) -> str:
    value = str(token).strip().upper()
    mapping = {
        "N": "N",
        "UP": "N",
        "NORTH": "N",
        "↑": "N",
        "上": "N",
        "上滚": "N",
        "S": "S",
        "DOWN": "S",
        "SOUTH": "S",
        "↓": "S",
        "下": "S",
        "下滚": "S",
        "E": "E",
        "RIGHT": "E",
        "EAST": "E",
        "→": "E",
        "右": "E",
        "右滚": "E",
        "W": "W",
        "LEFT": "W",
        "WEST": "W",
        "←": "W",
        "左": "W",
        "左滚": "W",
    }
    if value in mapping:
        return mapping[value]
    raise ModelOutputParseError(f"Invalid direction token: {token}")


def normalize_direction_list(raw_value: Any, raw_text: str) -> list[str]:
    if isinstance(raw_value, list):
        directions = [normalize_direction_token(item) for item in raw_value]
    elif isinstance(raw_value, str):
        pieces = [part for part in re.split(r"[\s,\-;>]+", raw_value) if part]
        directions = [normalize_direction_token(item) for item in pieces]
    else:
        raise ModelOutputParseError("The directions field must be a list or string.", raw_text=raw_text)

    if len(directions) > DEFAULT_MAX_DIRECTION_STEPS:
        raise ModelOutputParseError(
            f"Direction sequence exceeds the allowed maximum of {DEFAULT_MAX_DIRECTION_STEPS}.",
            raw_text=raw_text,
        )
    return directions


def normalize_answer_payload(payload: dict[str, Any], sample_id: str, raw_text: str) -> ModelAnswer:
    candidate = payload
    if "directions" in candidate:
        directions = normalize_direction_list(candidate["directions"], raw_text)
    elif "moves" in candidate:
        directions = normalize_direction_list(candidate["moves"], raw_text)
    elif "sequence" in candidate:
        directions = normalize_direction_list(candidate["sequence"], raw_text)
    elif "answer" in candidate and isinstance(candidate["answer"], dict):
        nested = candidate["answer"]
        for key in ("directions", "moves", "sequence"):
            if key in nested:
                directions = normalize_direction_list(nested[key], raw_text)
                break
        else:
            raise ModelOutputParseError("Missing directions field in nested answer object.", raw_text=raw_text)
    else:
        raise ModelOutputParseError("Missing directions field.", raw_text=raw_text)

    return ModelAnswer(sample_id=sample_id, directions=directions, raw_text=raw_text)


def parse_model_answer_or_raise(raw_text: str, sample_id: str) -> ModelAnswer:
    payload = extract_json_object(raw_text)
    return normalize_answer_payload(payload, sample_id, raw_text)


def resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "cube2":
        path = Path(*path.parts[1:])
    return (DATA_DIR / path).resolve()


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


def build_multimodal_messages_for_eval(task: GoalRollTask) -> list[dict[str, Any]]:
    """SimVerse v1: delegates to prompts.build_messages."""
    from prompts import build_messages
    return build_messages(task, project_root=NEWCUBE_ROOT)


def request_model_answer(
    task: GoalRollTask,
    model_name: str,
    *,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
    trust_env: bool,
    max_tokens: int,
) -> tuple[str, ModelAnswer, str]:
    if not api_key:
        raise RuntimeError("DEFAULT_API_KEY is empty. Please edit cube2/eval-thinking/eval_local.py.")
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
            }
            response = client.chat.completions.create(**request_kwargs)
            raw_text, reasoning_output = extract_message_output_parts(response.choices[0].message)
            print(f"\n[Model Raw Output] {task.sample_id} | {model_name}")
            print(raw_text)
            print("[End Model Raw Output]\n")

            answer = parse_model_answer_or_raise(raw_text, task.sample_id)
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
