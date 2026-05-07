# VOI data

**Languages: English (this file) | [中文](README_zh.md)**

The `levels/` and `images/` subdirectories of this folder are **not committed to git**. They are hosted on HuggingFace and downloaded into this directory on demand.

## Get the data

From the project root, run:

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks voi
```

After that, you should see:

```
VOI/data/
├── levels/
│   ├── voi-000.json
│   ├── ...
│   └── voi-599.json   (600 files)
└── images/            # rendered target + per-shape images
```

The HuggingFace source: <https://huggingface.co/datasets/SimVer-ano/simverse2026> (anonymized for double-blind review).

## Per-record schema

Each `levels/voi-XXX.json` has:

| Field | Type | Note |
|---|---|---|
| `gridSize` | int | Grid is `gridSize × gridSize` |
| `inventory` | `{shapeId: {V1:[x,y], V2:[x,y], ...}}` | Base shape vertex coords |
| `target` | list of polygons | XOR target pattern |
| `imageAssets.target` | string | Path to target render |
| `imageAssets.shapes` | `{shapeId: path}` | Per-shape renders |
| `prompt.system` / `prompt.user` | string | Verbatim prompt the benchmark presents |
| `answer.placements` | list | Reference solution per [PROMPT_SKELETON.md §3.1](../../docs/PROMPT_SKELETON.md) |
| `legacy_answer` | string | Pre-v1 text DSL (kept for back-compat) |
| `solutionText` | string | Same as legacy_answer; engine reference mask source |
