# SimVerse

**Languages: English (this file) | [中文](README_zh.md)**

> ⚠️ **Anonymized for double-blind review.** This repository is currently undergoing peer review. Author, organization, contact, and citation fields are deliberately left as placeholders or omitted. Permanent ownership and citation info will be added after the review process concludes. Please do not attempt to deanonymize the maintainers.

A multi-task benchmark for evaluating multimodal LLMs on interactive simulation puzzles. Five independent tasks, each with its own browser-based playable demo, dataset, and evaluation pipeline.

**Code lives here on GitHub. Data lives on HuggingFace** (~360MB across 5 configs): <https://huggingface.co/datasets/Sayaka123/simverse2026>. After cloning, run `python scripts/download_dataset.py` to fetch the data into the right local paths — see [Setup](#setup) below.

## Tasks

| Task | Folder | Modality | Output |
|---|---|---|---|
| Text-VOI spatial puzzle | [VOI/](VOI/) | image (target + shapes) | shape placements |
| Cube reconstruction (six faces) | [cube1/](cube1/) | image (blank net + path) | face → patternId map |
| Cube goal-roll (top face) | [cube2/](cube2/) | image (initial net + target top) | roll direction sequence |
| Cut the Rope (video → commands) | [cutRope/](cutRope/) | gameplay video | text command script |
| Mechanical lamp (multi-segment arm) | [lamp/](lamp/) | image (arm + obstacles) | per-joint angle list |

Each task is a **fully independent** subproject: its own data, prompts, validator, and evaluation runner. The five share **only naming conventions and prompt structure** (see [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md) and [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)). No cross-task imports.

## Setup

```bash
# 1. Clone
git clone https://huggingface.co/datasets/Sayaka123/simverse2026   # data
git clone https://github.com/Sayaka1234-dot/simverse2026.git       # code

# 2. Download the data into the local task directories
pip install -U huggingface_hub
python scripts/download_dataset.py                  # all 5 tasks (~360MB)
# or:  python scripts/download_dataset.py --tasks lamp voi   # subset

# 3. Copy env file and fill in your provider keys
cp .env.example .env
# edit .env (add OPENAI_API_KEY, DASHSCOPE_API_KEY, etc.)

# 4. Python deps (each task has its own requirements.txt; install per task as needed)
cd VOI/eval && pip install -r requirements.txt   # or whichever task

# 5. Node deps (only for cutRope and lamp, which use Vite for the web demo)
cd cutRope && npm install
cd lamp && npm install
```

**What's in this repo vs on HuggingFace:**

| Where | What |
|---|---|
| **GitHub (this repo)** | Code: generators, eval pipelines, prompt builders, parsers, validators, frontend demos |
| **HuggingFace dataset** | Data: 2,486 puzzle instances + ~360MB of rendered images / video clips, with embedded prompt text and gold answers |

The two are decoupled by design — you can use the dataset standalone (it carries the literal prompt text in each record, see [docs/PROMPT_SKELETON.md §3](docs/PROMPT_SKELETON.md)), or you can use this repo to run the bundled eval / regenerate the dataset / play the web demos.

## Running a task

Every task uses the same evaluation CLI surface (see [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)):

```bash
# Run all levels with the configured model
python <task>/eval*/run_eval.py --all --model <model_name>

# Run one level
python <task>/eval*/run_eval.py --level <id_or_path>

# Aggregate results
python <task>/eval*/summarize_results.py <task>/eval*/results/<model>/
```

Web demos:

| Task | Run command | URL |
|---|---|---|
| VOI | `python -m http.server 8001` (in [VOI/](VOI/)) | http://127.0.0.1:8001/ |
| cube1 | `python -m http.server 8002` (in [cube1/](cube1/)) | http://127.0.0.1:8002/ |
| cube2 | `python -m http.server 8003` (in [cube2/](cube2/)) | http://127.0.0.1:8003/ |
| cutRope | `npm run dev` (in [cutRope/](cutRope/)) | http://localhost:5173/ |
| lamp | `npm run dev` (in [lamp/](lamp/)) | http://localhost:5174/ |

## Repository conventions

- All five tasks output their final answer as a single line `FINAL_JSON: {...}` whose schema is defined in [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md).
- All gold answers live in the dataset JSON under the `answer` field, in the same shape as the model's `FINAL_JSON` payload.
- Validators take `(model_answer, gold_answer, task)` and return a uniform `Verdict` (see [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)).
- Result files share a uniform schema across tasks; `summarize_results.py` per task is responsible for task-specific scoring details.

## Documentation

- [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md) — the canonical 9-section prompt skeleton and 5 per-task JSON schemas.
- [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md) — CLI args, result file shape, validator interface.

## HuggingFace dataset bundles

To upload each task's dataset to HuggingFace such that downloading the bundle is enough to drive **both** the playable demo and the eval pipeline, ship the directories below:

| Task | What to upload | Frontend reads | Eval reads |
|---|---|---|---|
| VOI | [`VOI/data/levels/`](VOI/data/levels/) | same dir | same dir |
| cube1 | [`cube1/data/task_jsons/`](cube1/data/task_jsons/) **and** [`cube1/levels/index.json`](cube1/levels/index.json) | the catalog `levels/index.json` (fat file) | the per-level files in `data/task_jsons/` |
| cube2 | [`cube2/data2/`](cube2/data2/) | catalog `data2/index.json` + per-level `data2/task_jsons/<code>.json` | per-level `data2/task_jsons/<code>.json` |
| cutRope | [`cutRope/data/task/`](cutRope/data/task/) **and** [`cutRope/eval/data/`](cutRope/eval/data/) | `data/task/*.json` (via vite middleware) | `eval/data/*.json` (built from `data/task/` + video metadata) |
| lamp | [`lamp/data/levels/`](lamp/data/levels/) (includes `manifest.json`) | same dir | same dir |

For the two tasks that ship two directories, they are **not redundant**:

- **cube1**: `data/task_jsons/<id>.json` is the canonical per-level source-of-truth (used by eval and the v1 schema). `levels/index.json` is a frontend-only fat catalog regenerable from the per-level files via [`cube1/regenerate_catalog.py`](cube1/regenerate_catalog.py). If a downloader edits `data/task_jsons/`, they should re-run that script to refresh the catalog.
- **cutRope**: `data/task/<id>.json` is the author-facing level schema. `eval/data/<id>.json` adds precomputed `prompt_level` metadata, `object_counts`, and video pointers — this is what the eval pipeline reads. Refresh via `python build_data.py --force`.

### Embedded prompts

Each per-level eval file carries a top-level `prompt` field:

```json
{
  "prompt": {
    "system": "<exact system prompt text the model receives>",
    "user":   "<exact 9-section user prompt text>"
  },
  "answer": { /* gold answer per docs/PROMPT_SKELETON.md §3 */ },
  ...
}
```

This means a HuggingFace user can reproduce a benchmark run **without** installing this repo or running any prompt-builder code — the prompt strings ARE the dataset. The runtime `prompts.py` modules in this repo automatically read the cached prompt when present and only construct fresh if absent. To refresh prompts after editing the templates, re-run `python <task>/eval*/populate_prompts.py` (idempotent).

### Idempotent refresh scripts

Inside each task's eval folder, the maintenance scripts are idempotent — re-running on a fresh download is a no-op:

- [`migrate_dataset.py`](VOI/eval/migrate_dataset.py) — moves legacy `answer` shape to v1 schema (already applied; output `Migrated 0/N`).
- [`populate_prompts.py`](VOI/eval/populate_prompts.py) — embeds `prompt: {system, user}` into each level (output `0 updated, N unchanged` on a fresh dataset).
