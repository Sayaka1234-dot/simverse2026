# Eval 接口契约

**语言：[English](EVAL_CONTRACT.md) | 中文（本文件）**

五个任务的测评流水线必须达成的一致约定。每个任务实现自己的 runner、parser、validator——它们**不共享代码**但**接口完全一致**。

## 1. CLI 接口（每个 `run_eval*.py` 都接受这些）

```
--level <id|json_path>          单个样本（与 --all 互斥）
--all                           跑数据集目录下的所有样本
--level-list-json <path>        仅跑这个 JSON 列出的 id
--data-dir <path>               覆盖默认数据集目录
--results-dir <path>            覆盖默认 <eval>/results/<sanitize(model)>/
--limit <int>                   样本数量上限
--model <str>                   传给 API 的模型名
--base-url <str>                OpenAI 兼容端点
--api-key <str>                 API key（默认从 env 读，永远不硬编码）
--timeout-seconds <float>       单次请求超时
--trust-env / --no-trust-env    是否把 HTTP 代理 env 传给 client
--max-tokens <int>              最大输出 token
--max-retries <int>             暂态失败重试次数（默认 1）
--fallback-model <str>          重试用尽后的可选 fallback 模型
--thinking-enabled / --no-thinking-enabled
                                目标 API 支持时请求 reasoning 模式
--skip-existing                 已有结果文件的样本跳过
```

> **遵循度说明：** 截至 SimVerse v1 迁移，五个任务在主入口的 flag 集合大致相同，但 legacy provider 变体（`run_eval_qwen.py`、`eval_step_local.py` 等）继承了任务特定的 argparser layout，还没逐字统一。共享的**功能契约**——同一份数据 schema、同一份 prompt 骨架、同一份 parser → validator → result-payload 流水线——在 5 个任务上**是**统一的（这是跨任务对比的承重部分）。剩下的 flag 异质性是 polish 项；新代码应当对齐上述 canonical surface。

## 2. 结果文件 shape（每个 per-sample JSON）

```json
{
  "task": "VOI | cube1 | cube2 | cutRope | lamp",
  "sample_id": "voi-000",
  "model": "claude-opus-4-6",
  "provider_label": "openai-compatible",
  "started_at": "2026-05-07T11:00:00Z",
  "finished_at": "2026-05-07T11:00:42Z",
  "raw_output": "string — 完整的 assistant 回复",
  "reasoning": "string — 抽出的 reasoning 内容（如果有）",
  "final_json_text": "string — FINAL_JSON: 那一行原文",
  "parsed_answer": { /* 去掉 FINAL_JSON: 前缀后解析出的 JSON 对象 */ },
  "evaluation": {
    "status": "passed | failed | invalid_output | network_error",
    "score": 0.0,
    "errors": ["机器可读的短字符串"]
  },
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

字段规则：

- `parsed_answer` 严格符合 [PROMPT_SKELETON.md §3](PROMPT_SKELETON.md) 里的 schema。永远不放任务特定的额外字段
- `final_json_text` 是抽出的字面量行（已去掉 `FINAL_JSON: ` 前缀）。便于离线再 parse
- `evaluation.status` 枚举跨任务一致。`score` 语义：
    - `1.0` — 完美通过
    - `0.0` — 失败
    - 部分得分允许使用小数（如 cube1：正确识别面的比例）
- `evaluation.errors` 是短标识符（`"angle_out_of_range"`、`"non_unique_shape"`），不是自由文本

## 3. 输出抽取器（各任务的 `parsers.py`）

每个任务实现自己的 `parsers.py`，暴露：

```python
def extract_final_json(raw_text: str) -> tuple[str, dict]:
    """找到最后一行以 'FINAL_JSON:' 开头的，把后面解析为 JSON。
    返回 (final_json_text, parsed_dict)。
    格式错误时抛 ModelOutputParseError。"""
```

统一行为：

- 找**最后**一行（去除前导空白后）以 `FINAL_JSON:` 开头的
- 去掉前缀，用 `json.loads` 解析剩下的部分
- 如果这行被 ` ``` ` 包裹，剥离一层
- 失败时抛 `ModelOutputParseError(reason, raw_text)`

五个 `parsers.py` 文件各自重复实现，以保持任务解耦，但行为可互换。

## 4. Validator 接口（每个任务的 `validator.py`）

```python
@dataclass
class Verdict:
    status: str         # "passed" | "failed" | "invalid_output"
    score: float        # 0.0 .. 1.0
    errors: list[str]   # 机器可读的标识符
    detail: dict        # 任务特定的额外信息（如 per-face 正确性）


def validate(
    *,
    parsed_answer: dict,     # FINAL_JSON payload，schema 见 PROMPT_SKELETON.md §3
    gold_answer: dict,       # 任务 JSON 的 "answer" 字段，同一 schema
    task: dict,              # 完整任务 JSON
    project_root: Path,      # 解析图像/视频资源时用
) -> Verdict: ...
```

硬性规则：

- `parsed_answer` 和 `gold_answer` 用同一份 JSON schema；validator 不需要格式转换 adapter
- Validator 可以跑任务底层的 engine（cube2 的模拟器、cutRope 的重放器、lamp 的几何 checker），但**不能**调 LLM API
- 对于开放解任务（cube2、cutRope），validator **不要求** 与 `gold_answer` 等价——`gold_answer` 只是覆盖率参考。`Verdict` 由 engine 模拟 `parsed_answer` 决定
- Validator 的 errors 应该是**稳定的字符串标识符**，下游 summary 可以聚合。每个任务的 error 词表在该任务的 eval README 里说明

## 5. 数据集 `answer` 字段

每个数据集 JSON（per-sample）的 `answer` 字段**在结构上**等同于模型 `FINAL_JSON` payload schema。具体：

| 任务 | 样本 JSON 路径 | `answer` shape |
|---|---|---|
| VOI | [VOI/data/levels/*.json](../VOI/data/levels/) | `{"placements": [...]}` |
| cube1 | [cube1/data/task_jsons/*.json](../cube1/data/task_jsons/) | `{"faces": {...}}` |
| cube2 | [cube2/data2/task_jsons/*.json](../cube2/data2/task_jsons/) | `{"directions": [...]}` |
| cutRope | [cutRope/data/task/*.json](../cutRope/data/task/) | `{"commands": "...", "reason": "...", "confidence": 1.0}` |
| lamp | [lamp/data/levels/*.json](../lamp/data/levels/) | `{"actions": [...]}` |

每个任务的 eval 目录下有迁移脚本，把 legacy 格式转成此 schema。原始字符串/数组保留在 `legacy_answer` 字段下，过一个 release cycle 之后删除。

## 6. 汇总器（各任务的 `summarize_results.py`）

CLI：

```
python summarize_results.py <results_dir> [--out summary.json] [--csv summary.csv]
```

输出统一表格：`model | n_passed / n_total | mean_score | mean_latency_s | invalid_output_rate`。每个任务的评分细节在该任务的 summarizer 里，但列集跨任务一致，便于做跨任务对比报告。

## 7. 文件位置（canonical）

```
<task>/
  eval*/                       # cube1 cube2 lamp 用 eval-thinking/；VOI cutRope 用 eval/
    run_eval.py                # canonical 入口
    run_eval_<provider>.py     # provider 特定变体共享同一 CLI surface
    prompts.py                 # 构造 system + user + messages（按 PROMPT_SKELETON.md）
    parsers.py                 # 抽取 FINAL_JSON（按上面 §3）
    validator.py               # 校验 parsed_answer vs gold（按上面 §4）
    summarize_results.py       # 聚合 results 目录（按上面 §6）
    eval_common.py             # 任务内部工具（不跨任务 import）
    requirements.txt
    results/<sanitize(model)>/<sample_id>.json
```

5 个 `eval*/` 目录之间共享 0 个 Python import。代码 review 强制约束。
