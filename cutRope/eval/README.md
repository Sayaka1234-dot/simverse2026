# cutRope Eval (SimVerse v1)

Evaluation pipeline for the **Cut the Rope video → command script** task: watch a short gameplay video and output a deterministic command script that wins the level when replayed.

## Dataset (two coexisting layouts — both ship together for HF)

cutRope is the only task with **two different data directories that both need to ship**:

| Directory | Used by | Notes |
|---|---|---|
| [`cutRope/data/task/`](../data/task/) | **frontend** (via [`vite.config.js`](../vite.config.js) `levelDataBridgePlugin` mapping `/data/boxes/levels/*.json` → `data/task/*.json`) | The author-facing level schema. Each file carries `textCommandSolution` etc. |
| [`cutRope/eval/data/`](data/) | **eval pipeline** ([`run_eval.py`](run_eval.py), [`validator.py`](validator.py)) | Built from `data/task/` + recorded MP4 videos via [`build_data.py`](build_data.py). Adds `prompt_level`, `object_counts`, video paths, and the v1 `answer` field. |

For a HuggingFace upload that "just works on download", **ship both directories** — they are not redundant: the eval pipeline genuinely needs the `prompt_level` metadata that `build_data.py` precomputes (object counts, canvas dimensions, etc.).

If a downstream user edits `data/task/*.json` after downloading, they should re-run:
```bash
python build_data.py --force
```
to refresh `eval/data/*.json`.

Eval items in [`cutRope/eval/data/rope-*.json`](data/) (272 levels) carry the gold answer in the field `answer` per [docs/PROMPT_SKELETON.md §3.4](../../docs/PROMPT_SKELETON.md):

```json
{
  "answer": {
    "commands": "cut_rope 2\npop_bubble 3\ncut_rope 1 when candy_still for 0.3\n...",
    "reason": "reference solution",
    "confidence": 1.0
  }
}
```

cutRope is **open-ended**: many command scripts may win the same level. The validator runs a real simulator (Playwright + the in-repo Cut the Rope engine) on the model's `commands` and reports passed/failed based on the actual win/star outcome. `gold_answer.commands` is one known-3-star reference.

The legacy `reference_solution` string is kept alongside the new `answer` field for the build-data pipeline; the original was preserved by [`migrate_dataset.py`](migrate_dataset.py).

## Module layout

| File | Role |
|---|---|
| [`prompts.py`](prompts.py) | 5-section system + 9-section user prompt + multimodal messages (`build_messages`). |
| [`parsers.py`](parsers.py) | `extract_final_json` and `parse_cutrope_answer`: pulls `FINAL_JSON: {...}` and validates the commands schema (non-empty, no `wait_frames`, confidence in `[0,1]`). |
| [`validator.py`](validator.py) | `validate(parsed_answer, gold_answer, task) -> Verdict`. Runs the browser/headless simulator on the model's commands and scores the outcome. Also retains the legacy `evaluate_with_simulator(item, commands, ...)` entry. |
| [`build_data.py`](build_data.py) | Builds `eval/data/*.json` from `data/task/` + recorded MP4 videos. |
| [`eval_common.py`](eval_common.py) | Internal helpers (data I/O, video frame extraction, transient retries). The legacy `build_system_message` / `build_prompt` / `build_video_content` names are now thin shims around [`prompts.py`](prompts.py). |
| `run_eval.py`, `run_eval_<provider>.py` | Provider-specific runners. They keep importing the legacy names but transparently use the new prompts. |

## Model output contract

```
FINAL_JSON: {"commands":"<one cmd per line, joined with \n>","reason":"<intent>","confidence":<0..1>}
```

`wait_frames` is not allowed; use condition-based waits like `candy_still for 0.3` or `candy_y > 500`.

## Running

```bash
export OPENAI_API_KEY=...

# Build the eval data items (run once after dataset changes)
python build_data.py --force

# One sample
python run_eval.py --level rope-000

# All
python run_eval.py --all --skip-existing

# Other providers
python run_eval_qwen.py --level rope-000
python run_eval_qwen_open.py --level rope-000
python run_eval_gpt.py --level rope-000
```

The validator simulator requires the project's npm deps (`npm install` from [`cutRope/`](../)) and Playwright browsers (`npx playwright install`).

## Migrating

```bash
python migrate_dataset.py            # in place
python migrate_dataset.py --dry-run  # report only
```
