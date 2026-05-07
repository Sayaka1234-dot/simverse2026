# data2

**Languages: English (this file) | [中文](README_zh.md)**

> ⚠️ **`task_jsons/`, `manifests/`, `index.json` are not committed to git** — they are hosted on HuggingFace. After cloning, run:
>
> ```bash
> pip install -U huggingface_hub
> python scripts/download_dataset.py --tasks cube2
> ```
>
> HF source (anonymized for double-blind review): <https://huggingface.co/datasets/Sayaka123/simverse2026>

This directory stores the regenerated `cube2` tasks for the top-face target gameplay.

## Task definition

- Input: the visible cross net of the cube's unfolded outer surface.
- The number under each visible face is the clockwise rotation in degrees from the original upright pattern.
- Goal: output a roll sequence so that the cube's top face, seen from above, matches the target image exactly.
- Multiple sequences may be valid. The validator decides correctness.

## Directory structure

- `task_jsons/`: one JSON file per task.
- `manifests/goal_roll_tasks.jsonl`: the full task manifest.
- `manifests/sampled_150_seed20260425.jsonl`: the fixed sampled manifest used for evaluation.
- `index.json`: dataset overview for the web app.
- `../images/<LEVEL_CODE>/`: the paired initial-net and target-top-face images.
- `../source_data/task_jsons/`: the bundled source snapshot used to rebuild the dataset.

## Regeneration

```powershell
python cube2\generate_goal_roll_dataset.py
python cube2\retarget_data2_dataset.py
```
