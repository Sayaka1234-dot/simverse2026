# 游戏玩法与模型评测说明

本文档分两部分：

- 这一版 Cut the Rope 项目怎么玩
- 如何让模型基于关卡数据、截图、视频和文本指令做自动评测

如果你已经熟悉项目里的道具和文本指令，可以把本文当作总入口使用。

相关文档：

- `TEXT_COMMAND_GUIDE.md`：文本操作指令的完整语法
- `GAME_OBJECT_GUIDE.md`：所有道具、编号和功能说明
- `ai_level_solver_prompt.json`：给模型生成操作序列时可直接参考的提示词模板

## 1. 这是什么项目

这是一个基于 Cut the Rope 改造过的项目。当前项目已经做了很多面向建模和评测的增强，包括：

- 关卡选择页直接可见，不需要额外进入加载动画
- 关卡里加了坐标网格，便于按像素写条件
- 可交互道具增加了编号，方便写文本指令
- 支持用文本指令代替鼠标，执行切绳、点气泵、切换重力、释放灯笼等操作
- 支持无浏览器的离线批量评测

目前关卡数据存放在：

```text
data/task
```

目前这个目录里保留的是你已经筛选后的关卡。

## 2. 游戏怎么玩

### 2.1 目标

大多数关卡的核心目标很简单：

- 让主糖果移动到怪物嘴里
- 尽量多吃星星
- 避开危险道具和错误路径

### 2.2 常见玩法

玩家通常通过这些方式影响糖果运动：

- 切断绳子
- 点击气泵，让糖果改变速度或方向
- 切换重力方向
- 使用泡泡让糖果漂浮，再在合适时机戳破
- 控制卷绳轮收绳或放绳
- 控制转盘顺时针或逆时针旋转
- 点击幽灵、灯笼、蒸汽阀等机关

### 2.3 坐标与编号

为了方便模型判断，项目里已经加入了：

- 坐标网格：从 `(0, 0)` 开始，按固定网格显示像素位置
- 道具编号：例如 `R0`、`P0`、`L0`、`V0`、`S0`

这意味着模型不再需要凭感觉描述“左上角那个气泵”，而是可以直接写：

```text
activate_pump 0
cut_rope 1 when candy_near 320,260,45
release_lantern 0
```

更完整的编号规则请看：

- `GAME_OBJECT_GUIDE.md`

## 3. 模型是怎么控制游戏的

### 3.1 基本思路

模型并不是直接“理解画面然后点鼠标”，而是输出一段文本指令序列。项目里的文本控制器会在每一帧检查条件，条件成立后执行动作。

基本格式：

```text
ACTION [when CONDITION]
```

例如：

```text
cut_rope 0
activate_pump 0 every 0.15 until candy_y > 300
rotate_circle 1 cw when candy_near 280,240,50
stop_rotate_circle 1 when candy_x > 360
```

### 3.2 为什么不用绝对时间

这里主要采用“事件驱动”而不是“绝对时间触发”：

- 不建议写“第 2.3 秒切绳”
- 更建议写“糖果到达某区域时切绳”

这样做的好处是更稳定，也更适合物理类关卡。

### 3.3 条件判断能做什么

当前条件已经支持很多表达方式，例如：

- 糖果坐标
- 糖果速度
- 糖果进入某区域
- 糖果第几次进入某区域
- 糖果在某区域停留多少秒
- 某个抓点或钉子移动到哪里
- 某个编号道具移动到哪里
- `and / or` 组合条件

例如：

```text
cut_rope 1 when candy_near 260,220,45 times 2
cut_rope 0 when candy_near 300,260,50 for 3
activate_pump 0 until candy_x > 320 and candy_y < 260
cut_rope 2 when obj_near valve 0,260,180,30 or obj_x hat 1 > 340
```

完整语法请看：

- `TEXT_COMMAND_GUIDE.md`

## 4. 评测分成哪两种

### 4.1 浏览器内人工查看

适合：

- 观察关卡动态过程
- 调试模型生成的指令
- 人工查看是否真的通关、是否吃到星星

常见做法：

1. 启动开发服务器
2. 打开游戏页面
3. 进入某一关
4. 在文本指令面板输入操作序列
5. 点击运行，观察表现

启动命令：

```bash
npm run dev
```

### 4.2 无浏览器的离线批量评测

适合：

- 一次性跑很多关卡
- 比较不同模型、不同提示词、不同策略的效果
- 将结果保存成文件，便于后续统计

这个项目已经有独立的离线评测脚本，不需要打开浏览器页面。

脚本入口：

```text
scripts/eval-batch.ts
```

对应命令：

```bash
npm run eval:batch -- --input <batch.json> --output <results.json>
```

## 5. 模型评测的输入是什么

模型评测通常有两层输入：

- 关卡信息
- 操作代码

### 5.1 关卡信息

你可以给模型这些材料中的一种或多种：

- 关卡 JSON
- 关卡初始截图
- 关卡初始视频
- 道具说明文档
- 文本指令语法文档

项目里已经有这些资源：

- 关卡 JSON：`data/task`
- 关卡截图：`level_image`
- 关卡视频：`data/video`
- 道具说明：`GAME_OBJECT_GUIDE.md`
- 指令语法：`TEXT_COMMAND_GUIDE.md`
- 模型提示词模板：`ai_level_solver_prompt.json`

### 5.2 操作代码

模型最后需要输出一段文本指令，例如：

```text
cut_rope 0
activate_pump 0 every 0.12 until candy_y > 280
release_lantern 0 when candy_in_lantern
rotate_circle 1 ccw when obj_near rope 2,300,220,40
stop_rotate_circle 1 when candy_near 360,260,35
```

这段文本既可以放进网页里的文本面板，也可以直接送给离线评测脚本。

## 6. 批量评测输入文件怎么写

离线批量评测脚本接受一个 JSON 文件，里面可以包含多个 case。

最简单的格式如下：

```json
[
  {
    "level": "00-01.json",
    "commands": [
      "cut_rope 0"
    ]
  },
  {
    "level": "00-02.json",
    "commands": [
      "cut_rope 0",
      "activate_pump 0 until candy_y > 260"
    ]
  }
]
```

也可以写成带全局默认参数的格式：

```json
{
  "maxSeconds": 30,
  "stepSeconds": 0.0166667,
  "cases": [
    {
      "level": "00-01.json",
      "commands": "cut_rope 0"
    },
    {
      "level": "00-02.json",
      "commands": [
        "cut_rope 0",
        "activate_pump 0 every 0.1 until candy_y > 260"
      ]
    }
  ]
}
```

字段说明：

- `level`：关卡文件名，也可以传绝对路径
- `commands`：字符串或字符串数组
- `maxSeconds`：这条 case 最长仿真多少秒
- `stepSeconds`：仿真步长，默认约等于 `1/60`

## 7. 怎么运行离线评测

假设你准备了一个输入文件：

```text
batch-input.json
```

运行命令：

```bash
npm run eval:batch -- --input batch-input.json --output eval-results.json
```

运行完成后，结果会写入：

```text
eval-results.json
```

## 8. 评测结果会输出什么

输出文件会包含两部分：

- `summary`：总览统计
- `results`：每个关卡的明细

结果示例：

```json
{
  "summary": {
    "total": 2,
    "won": 1,
    "lost": 0,
    "timeout": 1
  },
  "results": [
    {
      "level": "00-01.json",
      "won": true,
      "stars": 3,
      "time": 2.35,
      "score": 3000,
      "reason": "won",
      "frames": 141,
      "commands": [
        "cut_rope 0"
      ]
    },
    {
      "level": "00-02.json",
      "won": false,
      "stars": 1,
      "time": 30,
      "score": 1000,
      "reason": "timeout",
      "frames": 1800,
      "commands": [
        "cut_rope 0",
        "activate_pump 0 until candy_y > 260"
      ]
    }
  ]
}
```

字段说明：

- `won`：是否通关
- `stars`：获得的星星数量
- `time`：仿真结束时的游戏时间
- `score`：游戏分数
- `reason`：结束原因，可能是 `won`、`lost`、`timeout`
- `frames`：一共跑了多少帧

## 9. 推荐的模型评测流程

一个比较稳妥的流程如下：

1. 给模型提供关卡截图或视频
2. 同时提供 `TEXT_COMMAND_GUIDE.md` 和 `GAME_OBJECT_GUIDE.md`
3. 让模型输出文本操作序列
4. 把模型输出写入批量评测输入文件
5. 用 `npm run eval:batch` 批量跑结果
6. 统计每个模型的通关率、平均星星数、失败类型

如果希望模型表现更稳定，推荐一起提供：

- 带网格的关卡截图
- 带编号的道具标记
- `ai_level_solver_prompt.json`

## 10. 实践建议

### 10.1 对模型的提示建议

建议明确告诉模型这些规则：

- 坐标系从左上角 `(0, 0)` 开始
- 编号以画面标签和代码数组顺序为准
- 红色绳子通常拉力更强，棕色绳子拉力较弱
- 转盘和卷绳轮不是同一个道具
- 灯笼不是第二颗糖果，主糖果始终只有一个

### 10.2 条件不要写得太死

由于物理仿真存在一定敏感性，建议优先使用：

- 区域判断
- 停留时间判断
- 多条件组合

而不是只依赖非常精确的单点坐标。

例如：

```text
cut_rope 1 when candy_near 300,240,45 for 0.5
```

通常会比：

```text
cut_rope 1 when candy_x > 301
```

更稳一些。

### 10.3 批量评测时建议保留原始输出

建议把模型原始生成的指令和最终评测结果一起保存，后面便于做：

- 失败案例回放
- 提示词对比
- 条件语法使用统计
- 通关率和星星数分析

## 11. 常见问题

### 11.1 模型输出的指令报错怎么办

优先检查：

- 指令名是否正确
- 编号是否存在
- 条件语法是否符合 `TEXT_COMMAND_GUIDE.md`
- 是否误用了已经下线的旧语法

### 11.2 模型为什么通不过某些关

常见原因有：

- 条件写得太精确，稍微偏一点就错过
- 忽略了动态道具的位置变化
- 混淆了转盘、卷绳轮、灯笼、泡泡等对象
- 没考虑“第几次经过区域”或“停留多久再触发”

### 11.3 离线评测和浏览器结果为什么偶尔不完全一致

理论上两者使用的是同一套引擎逻辑，但如果输入、步长、指令或资源状态不同，表现可能会有轻微差异。做批量对比时，尽量固定：

- 相同的关卡文件
- 相同的指令文本
- 相同的 `maxSeconds`
- 相同的 `stepSeconds`

## 12. 一句话总结

如果你想让模型评测这个项目，可以理解成：

- 用截图、视频、坐标网格和道具编号把关卡状态描述清楚
- 让模型输出文本操作指令
- 再用离线评测脚本批量执行这些指令，统计通关和星星结果
