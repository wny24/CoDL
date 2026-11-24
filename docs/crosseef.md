# SAPIEN 环境接入与四个任务场景

本接入为 uni-robot-agent 提供基于 **SAPIEN 3** 的双臂仿真环境，包含四个操作任务场景。机器人统一使用 **双 xArm7 + G2 平行夹爪**，复用框架的环境服务、Direct/Clean 工具、MCP 调用和 Web 监控。

CLI 接入名称保留为 `crosseef`。当前场景实现依赖外部 `cross_eef_sim` 源码，通过 `--native-root` 指定位置。

## 任务场景

| `--task` | 场景与任务 | 当前成功判定 |
|---|---|---|
| `CanSortDual` | 红、蓝罐与对应颜色的框；先右臂放置红罐，再左臂放置蓝罐 | 两个罐子分别位于对应颜色的框内 |
| `LaptopCleanup` | 笔记本与鼠标；将鼠标放在键盘上并合上屏幕 | 鼠标位于键盘表面且屏幕已合上 |
| `LiftTray` | 双臂抓住托盘把手并抬起 | 托盘底部高于桌面超过 5 cm |
| `Handover` | 起始框、目标框与罐子；双臂按需交接并搬运 | 罐子位于目标框内；不单独检查交接动作 |

任务名不区分大小写。切换任务只需修改 `--task`。

CanSortDual 的任务描述还要求优先夹取罐身中段，并在整个过程中保持每只夹爪两个 pad 的连线水平。这些是 Agent 的任务要求，当前判定器不会额外检查执行顺序、抓取部位或全程姿态。

## 机器人资产与控制约定

仓库内提供机器人资产副本：

```text
assets/robots/xarm7_g2_gripper/
├── xarm7_with_gripper.urdf
├── meshes/
├── collision/
└── visual/
```

**当前仿真仍加载 `--native-root` 下的同名机器人资产目录**；仓库副本尚未接入运行时加载路径。修改副本不会改变仿真中的机器人。

- 双臂名称为 `left`、`right`；控制点为 `link_tcp`，相对夹爪基座沿局部 +Z 偏移 0.172 m，坐标轴方向相同。
- `move` 接收世界坐标系的 `[x, y, z, roll, pitch, yaw]`，单位为米和弧度；状态四元数顺序为 `wxyz`。
- 对称开合时，两个 pad 的连线沿 TCP 局部 **Y 轴**，局部 +Z 指向夹指。TCP 不是随开合变化的 pad 中点。
- 夹爪开合值 `0` 为闭合、`1` 为张开，不代表米制指间距。
- 原生 IK 将 TCP 目标转换为关节目标，再由 PD 控制推进物理仿真；IK 可解不代表路径无碰撞。
- 提供 `front`、`top` 两路 640×480 图像和相机标定；`--depth` 开启深度观测。

## 准备运行环境

主环境运行 uni-robot-agent 和 Agent；独立仿真环境需要 Python、SAPIEN 3、Pinocchio 支持、SciPy、`cross_eef_sim` 依赖，以及版本匹配且包含本接入的 uni-robot-agent。SAPIEN 渲染需要 GPU/Vulkan，即使不打开窗口也一样。

注册已经准备好的仿真解释器：

```bash
uni-robot-agent setup --integration crosseef \
  --runtime-python /path/to/sapien-venv/bin/python \
  --native-root /path/to/crosseef-merged \
  --cache-dir "$PWD/.runtime-cache"
```

该步骤检查并记录已有环境，不自动安装原生依赖或下载场景资产。后续启动使用相同的缓存目录。主环境不必安装 SAPIEN。

## 分别启动仿真与 Agent

以下命令在工作目录执行，先激活主 Python 环境。配置好启动 Agent 的终端中的 `UNI_ROBOT_AGENT_API_KEY`，并把模型参数占位符替换为实际值。

**终端 1：启动一个新的仿真回合。**

```bash
uni-robot-agent deploy env \
  --integration crosseef \
  --cache-dir "$PWD/.runtime-cache" \
  --task CanSortDual --seed 0 --depth \
  --port 18790
```

**终端 2：连接 Agent，并开启监控。**

```bash
uni-robot-agent run \
  --integration crosseef \
  --env-url http://127.0.0.1:18790 \
  --agent-python "$PWD/.venv/bin/python" \
  --model YOUR_MODEL_ID \
  --provider-profile YOUR_PROVIDER_PROFILE \
  --provider-url YOUR_PROVIDER_URL \
  --action-profile direct --no-sam3 \
  --output-dir ./runs --monitor
```

使用支持图像输入的模型接口。若主环境不在 `.venv`，将 `--agent-python` 改为实际解释器路径。启用 SAM3 时，先部署其服务，再将 `--no-sam3` 替换为 `--sam3-url http://127.0.0.1:18762`；准备方法见 [服务部署](deployment.md)。

## 一条命令管理整个运行

也可以让 `run` 同时启动并管理仿真和监控：

```bash
uni-robot-agent run \
  --integration crosseef --deploy local \
  --cache-dir "$PWD/.runtime-cache" \
  --task CanSortDual --seed 0 --depth \
  --env-port 18790 \
  --agent-python "$PWD/.venv/bin/python" \
  --model YOUR_MODEL_ID \
  --provider-profile YOUR_PROVIDER_PROFILE \
  --provider-url YOUR_PROVIDER_URL \
  --action-profile direct --no-sam3 \
  --output-dir ./runs --monitor
```

这种方式不传 `--env-url`。注意：`run` 设置仿真端口用 **`--env-port`**，`deploy env` 用 **`--port`**。不要同时运行上述两套启动方式并占用同一端口。

## 监控、重置与退出

- 监控默认地址为 `http://127.0.0.1:8765/`，可用 `--monitor-port` 修改。18790 是环境 API 端口，不是可视化页面。
- 监控展示相机快照和工具记录；仿真只在执行动作时推进。`Holding previous frame` 表示沿用上一张相机图像，不表示环境 reset。
- 每次部署创建一个新回合并 reset。回合结束后需要重新部署；重启 Agent 或刷新网页不会 reset 已有环境。
- 分开启动时，Agent 的 Ctrl+C 不会停止通过 `--env-url` 连接的独立仿真。应在 `deploy env` 所在终端停止该服务。
- 使用 `run --deploy local` 时，运行流程负责清理它启动的仿真。端口占用时先确认并停止旧服务，不要把“端口仍在监听”当作新回合已就绪。
- 修改任务描述或机器人说明后，重新启动环境和 Agent 才会生效。

已有运行可单独回放：

```bash
uni-robot-agent monitor --run-dir /path/to/run-directory
```

## 代码入口与支持范围

| 文件 | 职责 |
|---|---|
| [tasks.py](../uni_robot_agent/integrations/crosseef/tasks.py) | 四个任务映射及 Agent 任务描述 |
| [server.py](../uni_robot_agent/integrations/crosseef/server.py) | 创建 SAPIEN 场景并启动环境服务 |
| [adapter.py](../uni_robot_agent/integrations/crosseef/adapter.py) | 双臂控制、原生 IK、相机观测和状态反馈 |
| [机器人 skill](../uni_robot_agent/resources/skills/crosseef/SKILL.md) | xArm7/G2 坐标、开合与操作反馈说明 |

当前支持 Direct 和 Clean 工具配置，尚未接入 Hybrid/ACT 策略。已验证四个场景的加载、RGB/深度观测、基础位姿控制及夹爪反馈；这不等于四个任务已由 Agent 自主完成。

`call_ok` 表示调用正常返回，`action_complete` 表示动作是否完成，二者都不等于抓取成功或任务成功。需要结合实际位姿、物体随动和最终场景判断结果。
