# Prompt 骨架规范

**语言：[English](PROMPT_SKELETON.md) | 中文（本文件）**

每个任务的 prompt 构造器都必须遵守的契约。五个任务各自在自己的 `eval*/prompts.py`（或 `prompts.py`，与各任务 `run_eval.py` 同目录）中实现自己的 prompt 构造器。这五个文件**不共享代码**——它们只共享下面这个骨架，由代码 review 强制约束。

## 1. System prompt（5 段，固定顺序）

```
[1] ROLE       — 一句话："You are a <task type> solver. <一句任务概述>"。
[2] INPUT      — 一段话：列出每种输入模态（图像 / 视频 / 结构化字段）。
[3] REASONING  — 原文：
                 "You may reason step by step before the final answer.
                  Place your final answer on the very last line of your reply,
                  in the form: FINAL_JSON: <one-line JSON>"
[4] OUTPUT     — 一段话：声明所需 JSON 对象的 schema 名称和硬性规则——
                 FINAL_JSON 周围不要 Markdown 代码栅栏，FINAL_JSON 之后
                 不要任何额外文本，整个回复有且仅有一行 FINAL_JSON。
[5] FAILSAFE   — 一段话：当信息不足时，模型仍须输出一个合法的 FINAL_JSON
                 （使用 "?" 这样的哨兵值）而不是拒答或返回纯文本。
```

每段都必须出现在每个任务的 system prompt 里。总长大约 120-200 词。

## 2. User prompt（9 段，固定顺序，固定标题）

标题逐字相同——直接照抄：

```
## 1. TASK
   一句话：目标。
   一句话：胜利条件。

## 2. WORLD MODEL
   每个游戏元素术语（candy、joint、face、shape、cube、...）的项目符号列表。
   每个术语配一句话定义。

## 3. VISUAL LEGEND
   解释输入图像/视频中每种颜色、符号、覆盖层的项目符号列表。
   坐标系约定：原点位置、轴方向、单位。

## 4. INPUT FIELDS
   所有结构化任务参数（关卡 id、网格大小、段长度、滚动序列、观察序列、
   允许角度范围、...）的项目符号列表。
   格式："- key: value"。

## 5. ACTION VOCABULARY
   每个合法动作原子或答案原子的项目符号列表。
   每个原子：名字、参数、可选条件子句。

## 6. CONSTRAINTS
   合法答案必须满足的硬约束的项目符号列表
   （角度步长、序列长度上限、唯一性、不重叠、...）。

## 7. SOLVING ADVICE
   可选的通用启发式项目符号列表。保持中性；不要倾向于
   当前任务实例的某个特定答案。

## 8. OUTPUT SCHEMA
   内联的 FINAL_JSON 示例（用占位符），加上每个字段的类型和取值描述。

## 9. FINAL INSTRUCTION
   原文，两句话：
   "You may include reasoning above, but the very last line of your reply must
    start with FINAL_JSON: followed by exactly one valid JSON object.
    Do not wrap FINAL_JSON in code fences and do not write anything after it."
```

每段都必须出现在每个任务的 user prompt 中。如果某任务确实在某段没东西可写（如：没有障碍物 → 空的 constraints 子列表），段标题仍然出现，下面写一行 `(none for this task)`。

## 3. 各任务 JSON schema（已锁定）

每个任务的 `FINAL_JSON: <object>` 匹配下面对应的 schema。数据集的标答 `answer` 字段使用**同一个** schema，所以同一个 JSON loader 既能服务模型输出又能服务 ground truth。

每个 per-level 数据集文件还有一个顶层的 `prompt` 字段，包含 benchmark 实际呈现给模型的原始文本，这样 HuggingFace 数据集用户**不用**重新构造 prompt 也能复现：

```json
{
  "prompt": {
    "system": "<5 段 system prompt 文本——见 §1>",
    "user":   "<9 段 user prompt 文本——见 §2>"
  },
  "answer": { /* 各任务 schema 见下 */ },
  "...": "...任务特定字段"
}
```

每个任务的 `prompts.py` 优先读 `task.prompt.system` / `task.prompt.user`（如果有的话），否则现场构造。如果你改了 `prompts.py` 里的模板想刷新嵌入的 prompt，重跑 `python <task>/eval*/populate_prompts.py`（幂等）。

### 3.1 VOI — `placements`

模型 `FINAL_JSON` payload 和数据集 `answer` 字段：

```json
{
  "placements": [
    {"shape": "S1", "angle": 180, "vertex": "V2", "grid": [4, 2]},
    {"shape": "S2", "angle":  90, "vertex": "V3", "grid": [5, 2]}
  ]
}
```

- `shape` — 字符串，必须等于任务 JSON 库存中的某个 shape id
- `angle` — 整数，取值 `{0, 90, 180, 270}` 之一（绕局部原点顺时针旋转）
- `vertex` — 字符串，旋转后的顶点 id
- `grid` — `[int, int]`，所选顶点映射到的全局网格坐标
- 每个 shape **最多用一次**。placements 顺序对评分无关

### 3.2 cube1 — `faces`

```json
{
  "faces": {
    "TOP":    {"patternId": "smile",    "rotation":  90},
    "BOTTOM": {"patternId": "triangle", "rotation":  90},
    "FRONT":  {"patternId": "5",        "rotation": 180},
    "BACK":   {"patternId": "?",        "rotation":   0},
    "LEFT":   {"patternId": "?",        "rotation":   0},
    "RIGHT":  {"patternId": "?",        "rotation":   0}
  }
}
```

- 六个 face key 必须全在，逐字：`TOP, BOTTOM, FRONT, BACK, LEFT, RIGHT`
- `patternId` — 字符串，必须来自任务的 `allowed_pattern_ids` 列表，或字面值 `"?"`（表示该面无法唯一确定）
- `rotation` — 整数，取值 `{0, 90, 180, 270}` 之一
- 当 `patternId == "?"` 时，`rotation` 必须为 `0`（哨兵对规则）

### 3.3 cube2 — `directions`

```json
{
  "directions": ["N", "E", "S"]
}
```

- `directions` — 方向 token 数组，每个 token 取值 `{"N", "S", "E", "W"}` 之一（向上/下/左/右滚）
- 长度 ≤ 任务定义的 `MAX_DIRECTION_STEPS`
- 开放解：任何能产生目标顶面的序列都合法；engine 通过模拟来验证
- 数据集 `answer` 存放**一个**已知有效的参考序列，用于求解覆盖率统计

### 3.4 cutRope — `commands`

```json
{
  "commands": "cut_rope 2\npop_bubble 3\ncut_rope 1 when candy_still for 0.3",
  "reason":   "drop candy onto the upper rope swing, then release after the bubble pop",
  "confidence": 0.85
}
```

- `commands` — 字符串，每行一条指令。词汇表固定（见 prompt §5）
- `reason` — 短字符串（约一句话）解释意图
- `confidence` — 浮点数，`[0, 1]`
- Validator 跑 headless 重放器；多个正确指令脚本都合法
- 数据集 `answer` 存放一个已知有效的脚本，`confidence: 1.0`、`reason: "reference solution"`

### 3.5 lamp — `actions`

```json
{
  "actions": [
    {"joint": 1, "angle":  -60},
    {"joint": 2, "angle": -135},
    {"joint": 3, "angle":  140},
    {"joint": 4, "angle":  -15},
    {"joint": 5, "angle":  165}
  ]
}
```

- `actions` — 长度等于任务 `segment_count` 的数组，每个 joint 都不能缺
- `joint` — 1-indexed 整数，对应 `INPUT FIELDS` 中的段 id
- `angle` — 整数（度），落在任务允许的 `[angleMin, angleMax]` 范围内、是 `angleStep` 的整数倍。绝对角度从正 x 轴量起（**不是**跨关节累加）

## 4. 写作规则

- 长度：每个任务的 system+user 总文本应落在相近大小区间内。目标 600-900 词，±20%。避免某个任务 200 词另一个 1500 词——段落密度必须可比
- 章节标题：`## 1. TASK`、`## 2. WORLD MODEL`、…、`## 9. FINAL INSTRUCTION` 这些字面字符串五个任务**逐字一致**复制粘贴
- "Solving advice"（第 7 段）必须**任务类别通用**，不能 instance-specific。永远不要写 "for this level, try …"
- 永远不要把标答放进 prompt（哪怕是改写）
- 多模态图像/视频在 user prompt 文本**之后**附加，每个 asset 前一行文本说明它是什么

## 5. Prompt 构造器的位置

每个任务的 `prompts.py` 都在自己的 eval 目录下：

| 任务 | Prompt 文件 |
|---|---|
| VOI | [VOI/eval/prompts.py](../VOI/eval/) |
| cube1 | [cube1/eval-thinking/prompts.py](../cube1/eval-thinking/) |
| cube2 | [cube2/eval-thinking/prompts.py](../cube2/eval-thinking/) |
| cutRope | [cutRope/eval/prompts.py](../cutRope/eval/) |
| lamp | [lamp/eval-thinking/prompts.py](../lamp/eval-thinking/) |

每个 `prompts.py` 暴露恰好三个函数：

```python
def build_system_prompt() -> str: ...
def build_user_prompt(task) -> str: ...
def build_messages(task, *, project_root) -> list[dict]: ...   # OpenAI 兼容的 chat messages
```

五个文件之间不互相 import。
