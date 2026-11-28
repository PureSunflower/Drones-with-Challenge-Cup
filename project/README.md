# 六节点空地协同仿真

第一阶段 Python 软件原型。六个虚拟节点使用独立的本地状态，通过 JSON 消息交换心跳、能力、任务和投票。终端输出、实验库、日志和导出均标记为 `SIMULATION`。

## 启动

在 `D:\Drones\project` 下使用 Python 3.11+。以下命令适用于 PowerShell。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --scenario single-outage --csv data/single-outage.csv
.\.venv\Scripts\python.exe -m pytest -q
```

`main.py --help` 列出所有参数。使用 `--seed` 复现实验，使用 `--min-delay`、`--max-delay`（秒）、`--loss` 和 `--duplicate`（0～1）覆盖场景默认网络条件。默认数据库为 `data/experiments.sqlite3`，日志为 `logs/simulation.log`。用 `--db`、`--log` 和 `--csv` 指定路径。每次运行有独立的 `run_id`，CSV 导出本次运行的全部事件，最后一条 `scenario_finished` 包含各节点视角的结果。事件时间为仿真秒，实验起始时间在 SQLite 中以 UTC 存储。

| 场景 | 操作 |
| --- | --- |
| normal | 六节点上线并竞争示例任务 |
| single-outage | 执行者 001 掉电、重新分配、001 恢复 |
| double-outage | 001 和 002 掉电、重新分配、两节点恢复 |
| loss | 每个接收方的传输有 20% 丢包概率 |
| duplicate | 每个接收方的传输有 60% 概率生成副本 |
| delay | 每次投递延迟为 0.50～1.25 仿真秒 |
| partition | 3∶3 分区，任一侧均无法形成多数 |
| recovery | 先进行 3∶3 分区，连通恢复后重新认领 |
| competition | 临时阻断 001 到 002 的单向链路，使两者各自发出正式认领 |

也可直接编排实验。时间按 `Settings.tick` 推进，`advance` 执行从当前时间开始的半开区间内的时钟步。

```python
from simulator.simulation_engine import Simulation

sim = Simulation()
sim.advance(2)
sim.publish("006", "demo", (0, 0), frozenset({"COMM"}))
sim.advance(7)
sim.power("001", False)
sim.advance(16)
sim.power("001", True)
sim.advance(3)
for node_id, node in sim.nodes.items():
    view = node.local_task_table.get("demo")
    print(node_id, node.node_status, view and (view.epoch, view.owner, view.status))
```

`set_link(src, dst, enabled)` 控制单向链路，`partition(group)` 隔离两组，`heal()` 恢复链路。六个节点的类型和能力来自任务书。配置中的电量、位置、距离比例及示例任务均为可替换的合成实验输入。心跳、超时和认领时长在 `config/settings.py`。

## 工程结构

| 路径 | 职责 |
| --- | --- |
| main.py | 场景入口、参数、终端摘要和持久化 |
| config/ | 虚拟节点能力、合成初值和仿真时间参数 |
| communication/ | JSON 消息与校验、总线、网络条件、串口及帧接口预留 |
| node_manager/ | 本地节点、邻居注册表与心跳超时 |
| task_manager/ | 任务数据、适配度、排序、投票、租约和重新评估 |
| simulator/ | 六节点时钟、链路开关、故障和内置场景 |
| storage/ | Logging、SQLite 和 CSV 导出 |
| tests/ | Pytest 单元和集成测试 |
| data/、logs/ | 本地生成的实验记录 |

## 消息协议

示例 JSON 信封如下。版本固定为 1，`timestamp` 和 `ttl` 均为仿真秒。收件目标可为具体节点或 `ALL`；`seq` 由源节点递增生成，模拟恢复时保留序列。接收端检查信封和相关业务字段，按 `(src, seq)` 去重，在 `timestamp + ttl` 判定过期。无效、重复、超时消息记入实验日志。

```json
{"protocol_version":1,"msg_type":"HEARTBEAT","src":"001","dst":"ALL","seq":1,"timestamp":0,"ttl":8,"payload":{"node_type":"MULTIROTOR","capabilities":["COMM","VISION","RADAR"],"battery":0.95,"position":[0,0]}}
```

| 消息 | 载荷和语义 |
| --- | --- |
| NODE_JOIN、HEARTBEAT | 节点类型、能力、电量和位置，同时更新邻居存活时间 |
| NODE_STATUS | 同样的资料字段，用序号防止旧资料回写 |
| NODE_LEAVE | 空对象，较新的离开通知立即将邻居视为离线；突然掉电走超时检测 |
| TASK_ANNOUNCE、TASK_UPDATE | task_id、publisher、position、required、preferred、starts_at；发布或重播任务定义 |
| TASK_BID、TASK_CLAIM | task_id、epoch、score；分别用于意向和正式认领 |
| TASK_ACK | task_id、epoch、candidate；源节点是这一票的投票人 |
| TASK_COMPLETE、TASK_RELEASE | task_id、epoch、owner、finished_at、result；上报完成或明确失败，接收端验证该轮票据 |
| SENSOR_DATA | sensor_id、sensor_type、source_node、timestamp、coordinate_frame、measurement、confidence、origin；支持 RADAR、VISION、GNSS、IMU |
| LINK_STATUS | 预留的链路状态载荷对象，由接收方记录；仿真链路故障由场景驱动 |

`communication/serial_transport.py` 提供 PySerial 打开接口和独立的帧编解码接口。串口参数由调用方明确提供。真实设备的帧边界、地址、校验、串口参数及原始传感器格式待确认。

## 认领与故障恢复

1. 发布节点发出任务定义。了解定义的节点周期性重播，供新加入或恢复节点补齐状态。
2. 每轮前 3 秒为竞标窗口。各节点自行检查必要能力，用 0.4×距离 + 0.3×电量 + 0.2×能力 + 0.1×负载计算适配度。距离是 `max(0, 1 - 欧氏距离 / distance_scale)`，能力是必要与偏好能力并集的匹配比例，空集按 1 处理，负载是 `1/(1+本地活跃租约数)`。
3. 随后 2 秒为正式认领窗口。各节点按各自收到的意向选择最高分，平分选字典序较小的节点 ID。候选节点重发认领。不同消息视图可能产生多个认领。
4. 各成员在认领窗口结束后，从合法候选中各投至多一票。认领者只有收到 4 个不同成员的同向投票才进入 `EXECUTING`，见证者显示 `ASSIGNED`。六成员的任意两组四票必相交。
5. 每轮最多 14 秒，到期后旧授权失效。未确认终态的任务重新竞标。心跳 3 秒转 `SUSPECT`，5 秒转 `OFFLINE`；在现有租约上观察到执行者离线时标记 `REASSIGNING` 和结果未知。换人后记录 `task_reassigned`。节点恢复时重收心跳、任务、各成员重放的投票及已验证终态。

仿真安全性依赖共同时间轴、固定且可信的成员身份、节点保存每轮唯一投票，以及只有持有效租约的节点执行。投票分裂、消息严重延迟或不足四节点互通时，当前轮可能停配，待下一轮重试。原型使用固定时段，无论旧执行者是否在线，尚未终结的任务在到期后均重新竞标。任务结果未传开时后续轮可能重做，执行必须可重试；这套流程提供仿真条件下的互斥租约，严格分布式共识、跨进程持久化及恰好一次执行超出当前实现。投票历史为恢复和结果同步保存在仿真节点内存，长时间运行会增长。

## 交付状态

- 已完成六节点仿真、协议、心跳、竞标和恢复、九个场景、SQLite 和 CSV、自动化测试。
- 本阶段执行动作以节点状态表示。场景层可使用 `node.tasks.finish(task_id, sim.now)` 上报完成，或传 `success=False` 上报明确失败。
- 后续集成包括 GUI、真实串口帧适配、STM32 联调及真实雷达和视觉驱动。待确认节点地址映射、E22/E34 通信参数、STM32 帧接口和传感器原始数据规范。
- 实测结果见 [TEST_REPORT.md](TEST_REPORT.md)。
