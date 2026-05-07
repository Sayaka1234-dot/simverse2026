# cube1 data

**Languages: English (this file) | [中文](README.md)**

`data/` only stores eval data; no code logic.

> ⚠️ **`data/task_jsons/`, `data/images/`, `data/manifests/` are not committed to git** — they live on HuggingFace. From the project root:
>
> ```bash
> pip install -U huggingface_hub
> python scripts/download_dataset.py --tasks cube1
> ```
>
> HF source (anonymized for double-blind review): <https://huggingface.co/datasets/SimVer-ano/simverse2026>

After download, this directory will contain:

- `data/task_jsons/` — one JSON per puzzle (502 total)
- `data/images/blank_nets/` — blank cross-net images
- `data/images/path_sequences/` — path imprint images
- `data/manifests/reconstruct_tasks.jsonl` — task manifest for batch eval

## Regenerating data

If you edit a level / image style / task description, regenerate the eval data:

```powershell
python eval/build_eval_assets.py --input levels/reconstruct
```

## Related scripts

The actual consumers of these data files live in `eval/`:

- `eval/build_eval_assets.py`
- `eval/eval_local.py`
- `eval/run_sampled_eval_local.py`
- `eval/summarize_model_results.py`

## Model config

Model name, API base URL, API key, timeout, etc. are configured in:

- `eval/eval_common.py`
