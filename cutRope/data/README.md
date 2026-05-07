# cutRope data

**Languages: English (this file) | [中文](README_zh.md)**

The `task/` and `video/` subdirectories of this folder are **not committed to git**. They are hosted on HuggingFace and downloaded into this directory on demand.

## Get the data

From the project root, run:

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks cutrope
```

After that, you should see:

```
cutRope/data/
├── task/
│   ├── manifest.json
│   ├── rope-000.json
│   ├── ...
│   └── rope-271.json   (272 levels)
└── video/
    ├── rope-000.mp4
    ├── ...
    └── rope-271.mp4    (272 short MP4 clips, ~245MB total)
```

The same downloader also populates `cutRope/eval/data/` (the eval-time-derived JSONs, with `prompt_level` metadata precomputed).

The HuggingFace source: <https://huggingface.co/datasets/SimVer-ano/simverse2026> (anonymized for double-blind review).

## Why two directories?

- **`data/task/*.json`** — author-facing level schema; the frontend reads these via the vite middleware bridge in [`vite.config.js`](../vite.config.js).
- **`eval/data/*.json`** — eval-time format; built from `data/task/` + `data/video/` via [`eval/build_data.py`](../eval/build_data.py). Adds `prompt_level`, `object_counts`, and the v1 `answer` field.

If you regenerate `data/task/`, refresh the eval format with:

```bash
python cutRope/eval/build_data.py --force
```
