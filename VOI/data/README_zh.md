# VOI 数据

**语言：[English](README.md) | 中文（本文件）**

`levels/` 和 `images/` 这两个子目录**不在 git 里**，它们托管在 HuggingFace，按需下载到本目录。

## 拉数据

从项目根运行：

```bash
pip install -U huggingface_hub
python scripts/download_dataset.py --tasks voi
```

跑完后此目录长这样：

```
VOI/data/
├── levels/
│   ├── voi-000.json
│   ├── ...
│   └── voi-599.json   （600 个文件）
└── images/            # 渲染好的目标图 + 各形状图
```

HuggingFace 源：<https://huggingface.co/datasets/SimVer-ano/simverse2026>（双盲匿名版）。

## Per-record schema

每个 `levels/voi-XXX.json`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `gridSize` | int | 网格大小 `gridSize × gridSize` |
| `inventory` | `{shapeId: {V1:[x,y], V2:[x,y], ...}}` | 各基础形状的顶点坐标 |
| `target` | 多边形列表 | XOR 目标图案 |
| `imageAssets.target` | 字符串 | 目标渲染图路径 |
| `imageAssets.shapes` | `{shapeId: path}` | 各形状渲染图 |
| `prompt.system` / `prompt.user` | 字符串 | benchmark 实际呈现给模型的 prompt 原文 |
| `answer.placements` | 列表 | 标答，schema 见 [PROMPT_SKELETON.md §3.1](../../docs/PROMPT_SKELETON.md) |
| `legacy_answer` | 字符串 | 迁移前的旧 DSL 文本（暂存以兼容） |
| `solutionText` | 字符串 | 同 legacy_answer；engine 用它构建参考 mask |
