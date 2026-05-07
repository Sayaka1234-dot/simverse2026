from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from statistics import median
from typing import Any, Iterable


STATUS_MEANINGS = {
    "matched": "模型输出生成的图案与目标图案完全一致，可以视为通关成功。",
    "mismatched": "模型输出可以被引擎解析，但最终图案与目标图案不完全一致。",
    "invalid_output": "模型输出文本不符合操作代码语法，或引用了不存在的图形、顶点等。",
    "request_error": "旧版结果中的请求失败状态。当前新版评测脚本默认会跳过这类样本，不再写入结果文件。",
}


METRIC_DEFINITIONS = {
    "total_levels": "纳入本次统计的关卡总数。",
    "scored_levels": "真正进入引擎判定阶段的关卡数。对于历史结果，通常等于总关卡数减去 request_error 数量。",
    "matched_levels": "图案完全匹配目标图案的关卡数量。",
    "match_rate": "完全匹配率，计算公式为 matched_levels / total_levels。",
    "mismatched_levels": "模型输出被成功解析，但最终图案未完全匹配目标图案的关卡数量。",
    "invalid_output_levels": "模型回答格式不合法或引用非法图形时的关卡数量。",
    "request_error_levels": "历史结果中由请求失败造成的样本数量。新版评测脚本通常不会再产生这类结果文件。",
    "exact_instruction_match_levels": "模型输出文本与标准答案文本完全一致的关卡数量。",
    "exact_instruction_match_rate": "标准答案文本完全一致的比例。注意它比图案匹配更严格。",
    "average_pattern_iou": "平均 IoU，衡量模型图案与目标图案的重合度。1 表示完全一致，0 表示完全不重合。",
    "median_pattern_iou": "IoU 的中位数，能减少少数极端样本对整体均值的影响。",
    "average_dice_score": "平均 Dice 系数，也是常用图案重合指标，通常会比 IoU 稍高。",
    "average_precision": "平均精确率，表示模型画出的像素里，有多少比例确实属于目标图案。",
    "average_recall": "平均召回率，表示目标图案里的像素，有多少被模型正确覆盖到。",
    "average_pixel_accuracy": "平均像素准确率，表示整张栅格图上的像素判断正确比例。",
    "average_required_shape_count": "平均标准答案所需图形数量，用于观察任务复杂度。",
    "average_distractor_shape_count": "平均干扰图形数量，用于观察干扰强度。",
    "average_grid_size": "平均网格边长，例如 6 表示 6x6 网格。",
    "average_ignored_text_line_count": "模型回答中被验证器忽略的文本行数均值，越高通常说明输出越不干净。",
    "timed_levels": "结果中带有耗时统计的关卡数量。旧版结果如果没有 timing 字段，不会被纳入这部分时间指标。",
    "average_model_response_seconds": "模型请求平均耗时，单位为秒，包含截断重试累计时间。",
    "median_model_response_seconds": "模型请求耗时的中位数，单位为秒，比均值更不容易受极端慢样本影响。",
    "p90_model_response_seconds": "模型请求耗时的 P90，单位为秒。90% 的样本耗时不会超过这个值，用于观察长尾延迟。",
    "average_engine_evaluation_seconds": "本地引擎验证平均耗时，单位为秒，即将模型输出送入游戏规则判定的时间。",
    "average_total_level_seconds": "单关总平均耗时，单位为秒，约等于模型请求 + 本地验证 + 脚本处理的总时间。",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def average(values: Iterable[float]) -> float:
    value_list = list(values)
    if not value_list:
        return 0.0
    return sum(value_list) / len(value_list)


def round_metric(value: float) -> float:
    return round(float(value), 6)


def percentile(values: Iterable[float], percent: int) -> float:
    value_list = sorted(float(value) for value in values)
    if not value_list:
        return 0.0
    rank = max(1, ceil((percent / 100) * len(value_list)))
    return value_list[rank - 1]


def load_result_payloads(results_dir: Path) -> list[dict[str, Any]]:
    result_paths = sorted(results_dir.glob("level*.json"))
    payloads: list[dict[str, Any]] = []
    for result_path in result_paths:
        payloads.append(json.loads(result_path.read_text(encoding="utf-8")))
    return payloads


def get_timing_value(payload: dict[str, Any], key: str) -> float | None:
    timing = payload.get("timing", {})
    if key in timing:
        try:
            return float(timing.get(key))
        except (TypeError, ValueError):
            return None

    if key == "model_response_seconds":
        completion = payload.get("completion", {})
        try:
            return float(completion.get("request_duration_seconds"))
        except (TypeError, ValueError):
            return None

    return None


def build_status_breakdown(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total = len(payloads)
    counter = Counter(str(item.get("evaluation_status", "unknown")) for item in payloads)
    breakdown: dict[str, dict[str, Any]] = {}

    for status, count in sorted(counter.items()):
        breakdown[status] = {
            "count": count,
            "ratio": round_metric(count / total) if total else 0.0,
            "meaning": STATUS_MEANINGS.get(status, "未预定义的状态，请结合 evaluation_status 原值理解。"),
        }

    return breakdown


def summarize_group(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    total_levels = len(payloads)
    scored_payloads = [
        item for item in payloads if str(item.get("evaluation_status")) != "request_error"
    ]

    matched_levels = sum(bool(item.get("is_pattern_matched")) for item in payloads)
    mismatched_levels = sum(
        1 for item in payloads if str(item.get("evaluation_status")) == "mismatched"
    )
    invalid_output_levels = sum(
        1 for item in payloads if str(item.get("evaluation_status")) == "invalid_output"
    )
    request_error_levels = sum(
        1 for item in payloads if str(item.get("evaluation_status")) == "request_error"
    )
    exact_instruction_match_levels = sum(
        bool(item.get("engine_result", {}).get("exact_instruction_match")) for item in payloads
    )

    pattern_ious = [safe_float(item.get("pattern_iou")) for item in scored_payloads]
    dice_scores = [
        safe_float(item.get("engine_result", {}).get("dice_score"))
        for item in scored_payloads
    ]
    precisions = [
        safe_float(item.get("engine_result", {}).get("precision"))
        for item in scored_payloads
    ]
    recalls = [
        safe_float(item.get("engine_result", {}).get("recall"))
        for item in scored_payloads
    ]
    pixel_accuracies = [
        safe_float(item.get("engine_result", {}).get("pixel_accuracy"))
        for item in scored_payloads
    ]
    ignored_text_line_counts = [
        safe_float(item.get("engine_result", {}).get("ignored_text_line_count"))
        for item in scored_payloads
    ]

    required_shape_counts = [safe_float(item.get("required_shape_count")) for item in payloads]
    distractor_shape_counts = [
        safe_float(item.get("distractor_shape_count")) for item in payloads
    ]
    grid_sizes = [safe_float(item.get("grid_size")) for item in payloads]

    model_response_seconds = [
        value
        for value in (get_timing_value(item, "model_response_seconds") for item in payloads)
        if value is not None
    ]
    engine_evaluation_seconds = [
        value
        for value in (get_timing_value(item, "engine_evaluation_seconds") for item in payloads)
        if value is not None
    ]
    total_level_seconds = [
        value
        for value in (get_timing_value(item, "total_level_seconds") for item in payloads)
        if value is not None
    ]

    return {
        "total_levels": total_levels,
        "scored_levels": len(scored_payloads),
        "matched_levels": matched_levels,
        "match_rate": round_metric(matched_levels / total_levels) if total_levels else 0.0,
        "mismatched_levels": mismatched_levels,
        "invalid_output_levels": invalid_output_levels,
        "request_error_levels": request_error_levels,
        "exact_instruction_match_levels": exact_instruction_match_levels,
        "exact_instruction_match_rate": (
            round_metric(exact_instruction_match_levels / total_levels) if total_levels else 0.0
        ),
        "average_pattern_iou": round_metric(average(pattern_ious)),
        "median_pattern_iou": round_metric(median(pattern_ious)) if pattern_ious else 0.0,
        "average_dice_score": round_metric(average(dice_scores)),
        "average_precision": round_metric(average(precisions)),
        "average_recall": round_metric(average(recalls)),
        "average_pixel_accuracy": round_metric(average(pixel_accuracies)),
        "average_required_shape_count": round_metric(average(required_shape_counts)),
        "average_distractor_shape_count": round_metric(average(distractor_shape_counts)),
        "average_grid_size": round_metric(average(grid_sizes)),
        "average_ignored_text_line_count": round_metric(average(ignored_text_line_counts)),
        "timed_levels": len(model_response_seconds),
        "average_model_response_seconds": round_metric(average(model_response_seconds)),
        "median_model_response_seconds": (
            round_metric(median(model_response_seconds)) if model_response_seconds else 0.0
        ),
        "p90_model_response_seconds": round_metric(percentile(model_response_seconds, 90)),
        "average_engine_evaluation_seconds": round_metric(average(engine_evaluation_seconds)),
        "average_total_level_seconds": round_metric(average(total_level_seconds)),
    }


def build_grouped_summary(
    payloads: list[dict[str, Any]],
    group_key: str,
    label_key: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)

    for item in payloads:
        group_value = item.get(group_key)
        label_value = item.get(label_key) if label_key else None
        grouped[(group_value, label_value)].append(item)

    def sort_key(entry: tuple[Any, Any]) -> tuple[int, str]:
        primary = entry[0]
        if isinstance(primary, int):
            return (0, str(primary).zfill(4))
        if isinstance(primary, float):
            return (0, f"{primary:08.3f}")
        return (1, str(primary))

    rows: list[dict[str, Any]] = []
    for (group_value, label_value) in sorted(grouped.keys(), key=sort_key):
        summary = summarize_group(grouped[(group_value, label_value)])
        row = {group_key: group_value}
        if label_key:
            row[label_key] = label_value
        row.update(summary)
        rows.append(row)
    return rows


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize Text-VOI evaluation result JSON files from a result directory."
    )
    parser.add_argument(
        "results_dir",
        type=Path,
        help="Directory that contains model result JSON files, for example results/gpt-4o.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional custom summary output path. Default: <results_dir>/summary.json",
    )
    return parser


def build_summary_payload(results_dir: Path, payloads: list[dict[str, Any]]) -> dict[str, Any]:
    sample_model_name = None
    if payloads:
        sample_model_name = payloads[0].get("model", {}).get("model_name")

    return {
        "summary_version": "1.2",
        "generated_at_utc": utc_timestamp(),
        "source_results_dir": str(results_dir),
        "model_name": sample_model_name or results_dir.name,
        "metric_definitions": METRIC_DEFINITIONS,
        "status_definitions": STATUS_MEANINGS,
        "overall": summarize_group(payloads),
        "status_breakdown": build_status_breakdown(payloads),
        "by_difficulty_tier": build_grouped_summary(
            payloads,
            group_key="difficulty_tier",
            label_key="difficulty_label",
        ),
        "by_grid_size": build_grouped_summary(payloads, group_key="grid_size"),
        "by_shape_pool_complexity": build_grouped_summary(
            payloads,
            group_key="shape_pool_complexity",
        ),
    }


def print_console_summary(summary_payload: dict[str, Any]) -> None:
    overall = summary_payload["overall"]
    print("=== Evaluation Summary ===")
    print(f"results_dir             : {summary_payload['source_results_dir']}")
    print(f"model_name              : {summary_payload['model_name']}")
    print(f"total_levels            : {overall['total_levels']}")
    print(f"matched_levels          : {overall['matched_levels']}")
    print(f"match_rate              : {overall['match_rate']}")
    print(f"average_pattern_iou     : {overall['average_pattern_iou']}")
    print(f"median_pattern_iou      : {overall['median_pattern_iou']}")
    print(f"average_dice_score      : {overall['average_dice_score']}")
    print(f"average_precision       : {overall['average_precision']}")
    print(f"average_recall          : {overall['average_recall']}")
    print(f"average_pixel_accuracy  : {overall['average_pixel_accuracy']}")
    print(f"timed_levels            : {overall['timed_levels']}")
    print(f"average_model_seconds   : {overall['average_model_response_seconds']}")
    print(f"median_model_seconds    : {overall['median_model_response_seconds']}")
    print(f"p90_model_seconds       : {overall['p90_model_response_seconds']}")
    print(f"average_engine_seconds  : {overall['average_engine_evaluation_seconds']}")
    print(f"average_total_seconds   : {overall['average_total_level_seconds']}")
    print()
    print("=== Status Breakdown ===")
    print(json.dumps(summary_payload["status_breakdown"], ensure_ascii=False, indent=2))
    print()


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    results_dir = args.results_dir.resolve()
    if not results_dir.exists():
        raise SystemExit(f"结果目录不存在: {results_dir}")
    if not results_dir.is_dir():
        raise SystemExit(f"输入路径不是文件夹: {results_dir}")

    payloads = load_result_payloads(results_dir)
    if not payloads:
        raise SystemExit(f"结果目录中没有 level*.json 文件: {results_dir}")

    summary_payload = build_summary_payload(results_dir, payloads)
    output_path = (args.output or (results_dir / "summary.json")).resolve()
    output_path.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print_console_summary(summary_payload)
    print(f"Summary saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
