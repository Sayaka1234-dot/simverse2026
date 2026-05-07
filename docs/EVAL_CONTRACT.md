# Eval Contract

**Languages: English (this file) | [中文](EVAL_CONTRACT_zh.md)**

What the five tasks' evaluation pipelines must agree on. Each task implements its own runner, parser, and validator; they share **no code** but **identical interfaces**.

## 1. CLI surface (canonical target for every `run_eval*.py`)

```
--level <id|json_path>          single sample (mutually exclusive with --all)
--all                           run every sample under the dataset directory
--level-list-json <path>        run only ids listed in this JSON
--data-dir <path>               override default dataset directory
--results-dir <path>            override default <eval>/results/<sanitize(model)>/
--limit <int>                   cap number of samples
--model <str>                   model name passed to the API
--base-url <str>                OpenAI-compatible endpoint
--api-key <str>                 API key (defaults to env, never hardcoded)
--timeout-seconds <float>       per-request timeout
--trust-env / --no-trust-env    pass HTTP proxy env to the client
--max-tokens <int>              maximum output tokens
--max-retries <int>             retries for transient failures (default 1)
--fallback-model <str>          optional fallback after retries are exhausted
--thinking-enabled / --no-thinking-enabled
                                request the provider's reasoning mode when supported
--skip-existing                 don't re-run a sample whose result file already exists
```

> **Conformance note.** As of the SimVerse v1 migration the five tasks expose
> roughly the same flag set on their primary entrypoints, but the legacy
> provider variants (`run_eval_qwen.py`, `eval_step_local.py`, …) inherited
> task-specific argparser layouts and have not yet been unified verbatim. The
> shared **functional contract** — same dataset schema, same prompt skeleton,
> same parser → validator → result-payload pipeline — IS uniform across all
> five tasks (this is the load-bearing part for cross-task comparison). Any
> remaining flag heterogeneity is a future polish item; new code should target
> the canonical surface above.

## 2. Result file shape (every per-sample JSON)

```json
{
  "task": "VOI | cube1 | cube2 | cutRope | lamp",
  "sample_id": "voi-000",
  "model": "claude-opus-4-6",
  "provider_label": "openai-compatible",
  "started_at": "2026-05-07T11:00:00Z",
  "finished_at": "2026-05-07T11:00:42Z",
  "raw_output": "string — full assistant message",
  "reasoning": "string — extracted reasoning content if any",
  "final_json_text": "string — the raw FINAL_JSON: line",
  "parsed_answer": { /* the JSON object after the FINAL_JSON: prefix */ },
  "evaluation": {
    "status": "passed | failed | invalid_output | network_error",
    "score": 0.0,
    "errors": ["short, machine-readable strings"]
  },
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

Field rules:

- `parsed_answer` exactly mirrors the schema in [PROMPT_SKELETON.md §3](PROMPT_SKELETON.md). Never task-specific extras.
- `final_json_text` is the literal extracted line (after stripping the `FINAL_JSON: ` prefix). Useful for offline reparsing.
- `evaluation.status` enum is the same across tasks. `score` semantics:
    - `1.0` — perfect pass
    - `0.0` — fail
    - fractional values allowed for partial-credit tasks (e.g. cube1: fraction of correctly identified faces)
- `evaluation.errors` are short identifiers (`"angle_out_of_range"`, `"non_unique_shape"`), not free-form prose.

## 3. Output extractor (per-task `parsers.py`)

Each task implements its own `parsers.py` exporting:

```python
def extract_final_json(raw_text: str) -> tuple[str, dict]:
    """Find the last line starting with 'FINAL_JSON:' and parse the rest as JSON.
    Returns (final_json_text, parsed_dict).
    Raises ModelOutputParseError on malformed output."""
```

Uniform behavior:

- Looks for the **last** non-empty line whose left-stripped form starts with `FINAL_JSON:`.
- Strips the prefix, parses the remainder with `json.loads`.
- If the line is wrapped in `` ``` ``, unwraps once.
- On failure, raises `ModelOutputParseError(reason, raw_text)`.

The five `parsers.py` files reimplement this independently to keep tasks decoupled, but their behavior is interchangeable.

## 4. Validator interface (every task's `validator.py`)

```python
@dataclass
class Verdict:
    status: str         # "passed" | "failed" | "invalid_output"
    score: float        # 0.0 .. 1.0
    errors: list[str]   # machine-readable identifiers
    detail: dict        # task-specific extras (e.g. per-face correctness)


def validate(
    *,
    parsed_answer: dict,     # FINAL_JSON payload, schema per PROMPT_SKELETON.md §3
    gold_answer: dict,       # task JSON's "answer" field, same schema
    task: dict,              # the full task JSON
    project_root: Path,      # for resolving image / video assets if needed
) -> Verdict: ...
```

Hard rules:

- `parsed_answer` and `gold_answer` use the same JSON schema; the validator does not need format conversion adapters.
- The validator may run the task's underlying engine (cube2 simulator, cutRope replayer, lamp geometry checker) but must not call out to LLM APIs.
- For open-ended tasks (cube2, cutRope), the validator does not require equality with `gold_answer` — `gold_answer` is only a coverage reference. The `Verdict` is determined by engine simulation against `parsed_answer`.
- Validator errors should be **stable string identifiers** so downstream summaries can group them. Per-task error vocabulary is documented in each task's eval README.

## 5. Dataset `answer` field

Every dataset JSON (per-sample) has an `answer` field that is **structurally identical** to the model's `FINAL_JSON` payload schema. Concretely:

| Task | Sample JSON path | `answer` shape |
|---|---|---|
| VOI | [VOI/data/levels/*.json](../VOI/data/levels/) | `{"placements": [...]}` |
| cube1 | [cube1/data/task_jsons/*.json](../cube1/data/task_jsons/) | `{"faces": {...}}` |
| cube2 | [cube2/data2/task_jsons/*.json](../cube2/data2/task_jsons/) | `{"directions": [...]}` |
| cutRope | [cutRope/data/task/*.json](../cutRope/data/task/) | `{"commands": "...", "reason": "...", "confidence": 1.0}` |
| lamp | [lamp/data/levels/*.json](../lamp/data/levels/) | `{"actions": [...]}` |

Migration scripts under each task's `eval*/` directory convert the legacy formats to this schema. Original strings/arrays are preserved under `legacy_answer` for one release cycle, then removed.

## 6. Summarizer (per-task `summarize_results.py`)

CLI:

```
python summarize_results.py <results_dir> [--out summary.json] [--csv summary.csv]
```

Prints a uniform table: `model | n_passed / n_total | mean_score | mean_latency_s | invalid_output_rate`. Per-task scoring nuances live in the task's summarizer, but the column set is identical across tasks for cross-task reports.

## 7. File locations (canonical)

```
<task>/
  eval*/                       # eval-thinking/ for cube1 cube2 lamp; eval/ for VOI cutRope
    run_eval.py                # canonical entrypoint
    run_eval_<provider>.py     # provider-specific variants share same CLI surface
    prompts.py                 # builds system + user + messages (per PROMPT_SKELETON.md)
    parsers.py                 # extracts FINAL_JSON (per §3 above)
    validator.py               # validates parsed_answer vs gold (per §4 above)
    summarize_results.py       # aggregates results dir (per §6 above)
    eval_common.py             # task-internal utilities (no cross-task imports)
    requirements.txt
    results/<sanitize(model)>/<sample_id>.json
```

The five `eval*/` directories share zero Python imports. Code review enforces it.
