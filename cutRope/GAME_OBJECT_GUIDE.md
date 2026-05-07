# Cut the Rope 道具说明

本文档说明当前项目中保留的主要道具、画面编号和文本指令中的引用方式。编号以游戏画面上的标注为准。

## 糖果

| 对象 | 条件前缀 | 说明 |
| --- | --- | --- |
| 主糖果 | `candy_*` | 普通关卡中的糖果。不要写 `main_candy_*`。 |
| 左半糖果 | `left_candy_*` | 半糖果关卡中的左半部分。 |
| 右半糖果 | `right_candy_*` | 半糖果关卡中的右半部分。 |

常用条件：

```text
candy_x > 300
candy_y < 200
candy_near 300,240,60
candy_near 300,240,60 times 2
candy_near 300,240,60 for 1.5
candy_velocity_y > 20
candy_in_bubble
candy_still for 2
```

## 绳子和抓点

| 画面标注 | 数组 | 说明 |
| --- | --- | --- |
| `R0`、`R1`... | `bungees[]` | 绳子、抓点、自动生成绳子的抓点、枪型抓点等都按这个数组编号。 |

常用操作：

```text
cut_rope N
fire_gun N
kick_rope N
move_grab N X
move_grab N X Y
```

红色或绷紧的硬绳子有张力，可以拉动糖果并产生反弹；棕色或松弛的软绳子张力较小。蜘蛛抓点已经批量转换为普通抓点。

## 星星和怪物

星星用于计分，怪物用于通关。当前筛选后的关卡中，限时星星已经改为永久星星。

## 气泡

| 画面标注 | 数组 | 说明 |
| --- | --- | --- |
| `B0`、`B1`... | `bubbles[]` | 自由气泡、包住糖果后的气泡、被灯泡捕获的气泡，都沿用同一个编号。 |

常用操作：

```text
pop_bubble
pop_bubble N
pop_bubble_left
pop_bubble_right
pop_lightbulb_bubble N
```

`pop_bubble N` 会按 `bubbles[N]` 查找实时状态，因此气泡移动、包住糖果、或被灯泡捕获后，编号仍然有效。

## 气泵

| 画面标注 | 数组 | 说明 |
| --- | --- | --- |
| `P0`、`P1`... | `pumps[]` | 点击后吹动糖果。 |

```text
activate_pump N
activate_pump N times C
activate_pump N every S until CONDITION
```

## 重力按钮

| 画面标注 | 条件对象 | 说明 |
| --- | --- | --- |
| `G0` | `gravity` | 点击后反转重力。 |

```text
toggle_gravity
obj_near gravity 0,300,240,60
```

## 灯笼

| 画面标注 | 数组 | 说明 |
| --- | --- | --- |
| `L0`、`L1`... | `lanterns[]` | 灯笼是唤醒或释放糖果的道具，不是第二颗糖果。 |

```text
release_lantern N
lantern_has_candy N
candy_in_lantern
obj_near lantern N,300,240,60
```

## 灯泡

| 画面标注 | 数组 | 说明 |
| --- | --- | --- |
| `LB0`、`LB1`... | `lightbulbs[]` | 可以捕获气泡。 |

```text
pop_lightbulb_bubble N
obj_near lightbulb N,300,240,60
```

## 幽灵、蒸汽阀、帽子、弹跳垫、老鼠、传送带

| 画面标注 | 文本 KIND | 说明 |
| --- | --- | --- |
| `GH0`、`GH1`... | `ghost` | 幽灵。 |
| `V0`、`V1`... | `valve` | 蒸汽阀或蒸汽管控制点。 |
| `H0`、`H1`... | `hat` | 帽子或袜子传送道具。 |
| `BN0`、`BN1`... | `bouncer` | 弹跳垫。 |
| `M0`、`M1`... | `mouse` | 老鼠。 |
| `CV0`、`CV1`... | `conveyor` | 传送带。 |

通用位置判断：

```text
obj_x KIND N > 300
obj_y KIND N < 200
obj_near KIND N,300,240,60
```

## 转盘和船舵

| 画面标注 | 指令 | 说明 |
| --- | --- | --- |
| `RC0`、`RC1`... | `rotate_circle` | 转盘，上面可能固定抓点，需要指定旋转方向和可选角度。 |
| `R0`、`R1`... 的船舵抓点 | `rotate_wheel` | 船舵，用于伸长或缩短绳子，不使用角度。 |

```text
rotate_circle N cw
rotate_circle N ccw
rotate_circle N cw D
rotate_circle N ccw D
stop_rotate_circle N

rotate_wheel N extend
rotate_wheel N shorten
stop_rotate_wheel N
```

## 已移除或不推荐规划的道具

当前关卡数据已经删除尖刺和电刺，蜘蛛抓点已转换为普通抓点。模型做规划时不需要再使用 `spike` 条件，也不需要安排躲避蜘蛛。
