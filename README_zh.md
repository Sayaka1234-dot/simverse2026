# SimVerse

**语言：[English](README.md) | 中文（本文件）**

> ⚠️ **双盲评审匿名版本。** 本仓库正在接受同行评审。作者、所属机构、联系方式、引用等字段均刻意留作占位符或留空，正式署名信息将在评审结束后补充。请勿尝试反向识别仓库维护者。

一个面向多模态 LLM 的多任务 benchmark，专注**可交互模拟谜题**。包含五个相互独立的任务，每个都有各自的浏览器演示、数据集和测评流水线。

**代码托管在 GitHub，数据托管在 HuggingFace**（5 个 config 共约 360MB）：<https://huggingface.co/datasets/Sayaka123/simverse2026>。克隆完仓库后，运行 `python scripts/download_dataset.py` 把数据拉到本地各任务的对应路径——见下方 [Setup](#setup)。

## 任务列表

| 任务 | 目录 | 模态 | 输出 |
|---|---|---|---|
| Text-VOI 空间拼图 | [VOI/](VOI/) | 图像（目标 + 基础形状） | 形状放置序列 |
| 立方体重建（六面） | [cube1/](cube1/) | 图像（空白展开图 + 路径图） | 面 → patternId 映射 |
| 立方体目标滚动（顶面） | [cube2/](cube2/) | 图像（初始展开图 + 目标顶面） | 滚动方向序列 |
| Cut the Rope（视频 → 指令） | [cutRope/](cutRope/) | 游戏视频 | 文本指令脚本 |
| 机械臂台灯（多关节） | [lamp/](lamp/) | 图像（机械臂 + 障碍） | 各关节角度列表 |

每个任务都是**完全独立**的子项目，有自己的数据、prompt、validator 和测评 runner。五个任务**只共享命名规范和 prompt 结构**（见 [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md) 和 [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)），不存在跨任务的代码 import。

## Setup

```bash
# 1. 克隆
git clone https://huggingface.co/datasets/Sayaka123/simverse2026   # 数据
git clone https://github.com/Sayaka1234-dot/simverse2026.git       # 代码

# 2. 把数据下载到本地各任务目录
pip install -U huggingface_hub
python scripts/download_dataset.py                  # 5 个任务全下（约 360MB）
# 或：python scripts/download_dataset.py --tasks lamp voi   # 仅下指定任务

# 3. 复制 env 文件并填写你的模型 provider key
cp .env.example .env
# 编辑 .env（填入 OPENAI_API_KEY、DASHSCOPE_API_KEY 等）

# 4. Python 依赖（每个任务有自己的 requirements.txt，按需安装）
cd VOI/eval && pip install -r requirements.txt   # 或其它任务

# 5. Node 依赖（仅 cutRope 和 lamp 用了 Vite 跑前端 demo）
cd cutRope && npm install
cd lamp && npm install
```

**本仓库 vs HuggingFace 数据集分工：**

| 在哪里 | 内容 |
|---|---|
| **GitHub（本仓库）** | 代码：生成器、测评流水线、prompt 构造器、parser、validator、前端 demo |
| **HuggingFace 数据集** | 数据：2486 个谜题实例 + 约 360MB 渲染图像/视频片段，每条记录都嵌入了 prompt 文本和参考答案 |

两者解耦设计——你可以独立使用数据集（每条记录都自带原始 prompt 文本，见 [docs/PROMPT_SKELETON.md §3](docs/PROMPT_SKELETON.md)），也可以用本仓库跑 bundled eval / 重新生成数据 / 玩 web demo。

## 跑一个任务

所有任务用统一的 eval CLI 接口（见 [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)）：

```bash
# 指定模型，跑全部关卡
python <task>/eval*/run_eval.py --all --model <model_name>

# 跑单关
python <task>/eval*/run_eval.py --level <id_or_path>

# 汇总结果
python <task>/eval*/summarize_results.py <task>/eval*/results/<model>/
```

Web demo：

| 任务 | 启动命令 | URL |
|---|---|---|
| VOI | `python -m http.server 8001`（在 [VOI/](VOI/) 内） | http://127.0.0.1:8001/ |
| cube1 | `python -m http.server 8002`（在 [cube1/](cube1/) 内） | http://127.0.0.1:8002/ |
| cube2 | `python -m http.server 8003`（在 [cube2/](cube2/) 内） | http://127.0.0.1:8003/ |
| cutRope | `npm run dev`（在 [cutRope/](cutRope/) 内） | http://localhost:5173/ |
| lamp | `npm run dev`（在 [lamp/](lamp/) 内） | http://localhost:5174/ |

## 仓库统一约定

- 五个任务都把最终答案输出为单行 `FINAL_JSON: {...}`，schema 锁定在 [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md)
- 所有标答存在数据集 JSON 的 `answer` 字段下，shape 跟模型的 `FINAL_JSON` payload 一致
- Validator 接受 `(model_answer, gold_answer, task)`，返回统一的 `Verdict`（见 [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md)）
- 各任务结果文件共享统一 schema，每个任务自己的 `summarize_results.py` 负责任务特定的评分细节

## 文档索引

- [docs/PROMPT_SKELETON.md](docs/PROMPT_SKELETON.md) — 9 段 prompt 骨架规范 + 5 个任务的 JSON schema
- [docs/EVAL_CONTRACT.md](docs/EVAL_CONTRACT.md) — CLI 参数、结果文件 shape、validator 接口

## HuggingFace 数据包结构

为了让 HF 用户下载数据后**前端**和**测评**都能直接跑，每个任务上传以下目录：

| 任务 | 上传内容 | 前端读 | Eval 读 |
|---|---|---|---|
| VOI | [`VOI/data/levels/`](VOI/data/levels/) | 同目录 | 同目录 |
| cube1 | [`cube1/data/task_jsons/`](cube1/data/task_jsons/) **和** [`cube1/levels/index.json`](cube1/levels/index.json) | catalog `levels/index.json`（胖文件） | per-level 文件 `data/task_jsons/` |
| cube2 | [`cube2/data2/`](cube2/data2/) | catalog `data2/index.json` + per-level `data2/task_jsons/<code>.json` | per-level `data2/task_jsons/<code>.json` |
| cutRope | [`cutRope/data/task/`](cutRope/data/task/) **和** [`cutRope/eval/data/`](cutRope/eval/data/) | `data/task/*.json`（通过 vite 中间件） | `eval/data/*.json`（由 `data/task/` + 视频元数据派生） |
| lamp | [`lamp/data/levels/`](lamp/data/levels/)（含 `manifest.json`） | 同目录 | 同目录 |

对于上传两个目录的两个任务（cube1、cutRope），两个目录**不是冗余的**：

- **cube1**：`data/task_jsons/<id>.json` 是 per-level 的 source-of-truth（eval 和 v1 schema 都用这个）。`levels/index.json` 是前端专用的胖 catalog，可以通过 [`cube1/regenerate_catalog.py`](cube1/regenerate_catalog.py) 从 per-level 文件重新生成。如果使用者修改了 `data/task_jsons/`，应重跑这个脚本同步 catalog
- **cutRope**：`data/task/<id>.json` 是作者面向的关卡 schema；`eval/data/<id>.json` 多了预先计算好的 `prompt_level` 元数据、`object_counts` 和视频指针——这才是 eval 流水线读的。通过 `python build_data.py --force` 刷新

### 嵌入的 prompt 文本

每个 per-level eval 文件都有一个顶层 `prompt` 字段：

```json
{
  "prompt": {
    "system": "<模型实际收到的 system prompt 文本>",
    "user":   "<模型实际收到的 9 段 user prompt 文本>"
  },
  "answer": { /* 标答，schema 见 docs/PROMPT_SKELETON.md §3 */ },
  ...
}
```

这意味着 HF 用户可以**完全不用**安装本仓库或跑任何 prompt 构造代码——prompt 字符串本身就是数据集的一部分。本仓库的 `prompts.py` 在加载时自动读取这个缓存字段，没有时再回落到现场构造。如果你修改了 prompt 模板想刷新所有数据，重跑 `python <task>/eval*/populate_prompts.py`（幂等）。

### 幂等的维护脚本

每个任务的 eval 目录里有两个幂等脚本——在新下载的数据上重跑等于啥都没干：

- [`migrate_dataset.py`](VOI/eval/migrate_dataset.py) — 把 legacy `answer` shape 升到 v1 schema（已应用过；输出 `Migrated 0/N`）
- [`populate_prompts.py`](VOI/eval/populate_prompts.py) — 把 `prompt: {system, user}` 嵌入到每个 level（在新下载的数据上输出 `0 updated, N unchanged`）
