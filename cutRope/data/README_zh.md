# cutRope 数据

**语言：[English](README.md) | 中文（本文件）**

`task/` 和 `video/` 这两个子目录**不在 git 里**——它们托管在 HuggingFace，按需下载到本目录。

## 拉数据

从项目根运行：

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks cutrope
```

跑完后此目录长这样：

```
cutRope/data/
├── task/
│   ├── manifest.json
│   ├── rope-000.json
│   ├── ...
│   └── rope-271.json   （272 个关卡）
└── video/
    ├── rope-000.mp4
    ├── ...
    └── rope-271.mp4    （272 个短视频，约 245MB）
```

同一个下载脚本同时把 `cutRope/eval/data/`（eval 时派生的 JSON，预先算好了 `prompt_level` 元数据）也填好。

HuggingFace 源：<https://huggingface.co/datasets/SimVer-ano/simverse2026>（双盲匿名版）。

## 为什么有两个目录？

- **`data/task/*.json`** — 作者面向的关卡 schema；前端通过 [`vite.config.js`](../vite.config.js) 里的 vite 中间件桥接读这些
- **`eval/data/*.json`** — eval 时格式；通过 [`eval/build_data.py`](../eval/build_data.py) 从 `data/task/` + `data/video/` 派生而来。多了 `prompt_level`、`object_counts` 和 v1 `answer` 字段

如果你重新生成了 `data/task/`，刷新 eval 派生文件：

```bash
python cutRope/eval/build_data.py --force
```
