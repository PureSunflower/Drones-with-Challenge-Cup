# 第一阶段软件测试报告

环境为 Windows、Python 3.13.7、Pytest 9.2.0，实验使用默认随机种子 42，数据来源均为 **SIMULATION**。

## 自动化结果

`python -m pytest -q` 共 39 项通过。覆盖 JSON 往返、非法消息、重复与过期、传感器来源标签、六节点本地状态隔离、乱序资料、心跳超时与恢复、评分和必要能力门槛、并发认领、四票门槛、任务终态同步、重新分配、旧 epoch 与租约过期、分区与恢复，以及 CLI、SQLite、日志和 CSV 集成。

## 命令行实验

每行均通过 `python main.py --scenario <场景>` 实际运行。单节点掉线额外使用了 `--csv data/single-outage.csv`。

| 场景 | 实验结束时的执行节点 | SQLite 实验 ID |
| --- | --- | --- |
| normal | 001 | ad1df1551c2c4b30964da89db69f65d8 |
| single-outage | 002 | 31428145b6da448ca878ef99cf8d650e |
| double-outage | 003 | c6d8b93e950a44b9b5df24f1dde37aa3 |
| loss | 001 | 1d78335f6916402fa6ebf023a5f24c20 |
| duplicate | 001 | f79b77d583284219b2923ce88aabe456 |
| delay | 001 | 5c67dacedb8d4bada830efcd3aca0602 |
| partition | 无 | 0d319d1b14d846a1a6e8696b90058964 |
| recovery | 001 | ab068231363f409ba1990eeac8f4fbc7 |
| competition | 001 | 3c59c83227654062a2b9c2c43e26a830 |

SQLite 位于 `data/experiments.sqlite3`，完整日志位于 `logs/simulation.log`。断言另外检查了竞争场景中 001 与 002 均实际发起认领，并逐步检查孤立旧执行者与新执行者的租约无重叠。真实 STM32、E22/E34、雷达和视觉设备的验证待接口资料确认后开展。

## 第二阶段自动化结果

Windows、Python 3.13.7、PySide6 Essentials 6.12.0、Matplotlib 3.11.2、Pytest 9.2.0。执行 python -m pytest -q 共 44 项通过，包括原有 39 项测试。

新增场景覆盖单节点失联并重分配、实际采样统计及 CSV、分区中取消任务并在恢复后传播、任务截止、Qt 离屏运行时通过界面发布任务和模拟节点掉电恢复、窗口渲染与正常关闭，以及用测试串口桩验证分片、握手和断开行为。硬件适配测试使用测试桩，真实设备尚未验证。
