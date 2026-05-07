# Cut the Rope 文本指令系统说明

本文档说明网页命令行和批量评测中可使用的文本操作指令。坐标使用游戏画布坐标，左上角为 `(0,0)`，`x` 向右增大，`y` 向下增大。

## 1. 基本格式

```text
ACTION [when CONDITION]
```

示例：

```text
cut_rope 0
cut_rope 0,1 when candy_y > 300
cut_rope 1 when candy_y > 300
pop_bubble 0 when candy_still for 1.5
activate_pump 0 every 0.2 until candy_y < 180
```

- 没有 `when` 时，动作会在轮到该行时立即执行。
- 有 `when` 时，动作会等条件满足后执行。
- 条件支持 `and`、`or` 和括号。
- 注释行可以使用 `#` 或 `//` 开头。

## 2. 糖果条件

主糖果始终使用 `candy_*`，不要写 `main_candy_*`。

```text
candy_x > 300
candy_y < 200
candy_near 250,320,40
candy_near 250,320,40 times 2
candy_near 250,320,40 for 1.5
candy_velocity_y > 20
candy_in_bubble
candy_in_lantern
candy_still for 3
candy_still for 3 speed 8
```

半糖果关卡使用左右前缀：

```text
left_candy_x > 200
left_candy_y < 180
left_candy_near 260,300,50
left_candy_near 260,300,50 times 2
left_candy_near 260,300,50 for 1.5
left_candy_velocity_y < 10
left_candy_in_bubble
left_candy_still for 2

right_candy_x > 200
right_candy_y < 180
right_candy_near 260,300,50
right_candy_near 260,300,50 times 2
right_candy_near 260,300,50 for 1.5
right_candy_velocity_y < 10
right_candy_in_bubble
right_candy_still for 2
```

`candy_still for S` 表示糖果的最终画面坐标连续稳定达到 `S` 秒后触发。默认稳定速度阈值为 `5` 像素/秒，也可以写 `speed T` 调整阈值。

## 3. 空间与状态条件

```text
rope_cut N
no_rope
wait_frames N
mouse_has_candy
lantern_has_candy N
```

抓点位置：

```text
grab_x N > 300
grab_y N < 200
grab_near N,300,240,50
grab_near N,300,240,50 times 2
grab_near N,300,240,50 for 1.5
```

通用道具位置：

```text
obj_x KIND N > 300
obj_y KIND N < 200
obj_near KIND N,300,240,50
obj_near KIND N,300,240,50 times 2
obj_near KIND N,300,240,50 for 1.5
```

可用 `KIND`：

| KIND | 含义 |
| --- | --- |
| `rope` / `grab` | 绳子抓点，对应 `bungees[]` |
| `pump` | 气泵 |
| `ghost` | 幽灵 |
| `valve` / `steam_tube` | 蒸汽阀 |
| `lantern` | 灯笼 |
| `lightbulb` / `bulb` | 灯泡 |
| `hat` | 帽子 |
| `bouncer` | 弹跳垫 |
| `circle` / `turntable` | 转盘 |
| `mouse` | 老鼠 |
| `conveyor` | 传送带 |
| `gravity` | 重力按钮 |
| `bubble` | 气泡 |

说明：当前筛选后的关卡数据已经删除尖刺道具，蜘蛛抓点也已经转换为普通抓点，因此模型不需要再规划躲避尖刺或蜘蛛追逐。

## 4. 动作指令

### 4.1 绳子

```text
cut_rope N
cut_rope N,M,K
cut_rope N M K
kick_rope N
fire_gun N
move_grab N X
move_grab N X Y
```

- `cut_rope N`：切断第 `N` 根绳子。
- `cut_rope N,M,K`：在同一个条件触发时同时切断多根绳子，例如 `cut_rope 0,1 when candy_y > 300`。
- `cut_rope N M K`：等价的空格写法，例如 `cut_rope 0 1 2 when candy_near 300,240,60`。
- `kick_rope N`：释放可踢开的粘性绳子。
- `fire_gun N`：触发枪型抓点。
- `move_grab N X [Y]`：移动可移动抓点。
- 红色/绷紧的硬绳子有张力，可以拉动糖果并产生反弹；棕色/松弛软绳子张力较小。

### 4.2 气泡

```text
pop_bubble
pop_bubble N
pop_bubble_left
pop_bubble_right
pop_lightbulb_bubble N
```

- `pop_bubble`：戳破当前包裹糖果的气泡。普通关卡戳主糖果；半糖果关卡会优先戳存在的半糖果气泡。
- `pop_bubble N`：按 `bubbles[N]` 的编号戳破气泡。这个编号会跟随气泡状态：自由气泡、被糖果吸住后随糖果移动的气泡、被左/右半糖果吸住的气泡、被灯泡捕获的气泡，都可以继续用同一个 `N` 戳破。
- `pop_bubble_left`：戳破左半糖果气泡。
- `pop_bubble_right`：戳破右半糖果气泡。
- `pop_lightbulb_bubble N`：戳破第 `N` 个灯泡捕获的气泡。

### 4.3 气泵

```text
activate_pump N
activate_pump N times C
activate_pump N times C every S
activate_pump N until CONDITION
activate_pump N every S until CONDITION
```

示例：

```text
activate_pump 0 every 0.15 until candy_y < 180
activate_pump 0 until candy_near 1100,430,50
activate_pump 1 times 4 every 0.2
```

`activate_pump N until CONDITION` 会持续激活第 `N` 个气泵，直到 `CONDITION` 满足后停止。没有写 `every S` 时，默认每 `0.05` 秒激活一次。

### 4.4 重力、灯笼、幽灵与其他

```text
toggle_gravity
release_lantern N
tap_ghost N
toggle_steam_tube N
tap_mouse
drag_conveyor N D
```

- `toggle_gravity`：点击重力按钮。
- `release_lantern N`：点击第 `N` 个灯笼，释放/唤醒糖果。
- `tap_ghost N`：切换第 `N` 个幽灵状态。
- `toggle_steam_tube N`：切换第 `N` 个蒸汽阀。
- `tap_mouse`：点击当前拿着糖果的老鼠。
- `drag_conveyor N D`：拖动第 `N` 条手动传送带距离 `D`。

### 4.5 转盘与船舵

转盘是承载抓点的圆形机构：

```text
rotate_circle N cw
rotate_circle N ccw
rotate_circle N cw D
rotate_circle N ccw D
stop_rotate_circle N
```

船舵是控制绳子伸长/缩短的机构：

```text
rotate_wheel N extend
rotate_wheel N shorten
stop_rotate_wheel N
```

## 5. 组合条件示例

```text
cut_rope 0 when candy_y > 260 and candy_x < 420
cut_rope 1 when candy_near 300,260,50 times 2
cut_rope 0,1,2 when candy_still for 0.8
pop_bubble 0 when candy_still for 1.2
activate_pump 0 every 0.2 until candy_near 420,180,60 or candy_y < 150
release_lantern 0 when lantern_has_candy 0 and obj_near lantern 0,300,240,80
```
