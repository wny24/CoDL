# Cross-EEF / SAPIEN

`--integration crosseef` 将单独准备的 Cross-EEF 项目接入 CoDL，共用现有的 Direct/Clean 工具、环境服务、MCP 通信和监控界面。两条机械臂均固定使用 **xArm7 + G2 夹爪**（`xarm7_g2_gripper`），不使用原项目默认的 Ability 灵巧手。

| 对外任务名 | 原生环境类 | 原生成功条件 |
|---|---|---|
| `CanSortDual` | `BimanualCanSortDual` | 红、蓝罐子分别位于对应颜色的箱子内 |
| `LaptopCleanup` | `BimanualLaptopCleanup` | 鼠标位于键盘表面，且笔记本屏幕已合上 |
| `LiftTray` | `BimanualLiftTray` | 托盘底部高于桌面超过 5 cm |
| `Handover` | `BimanualTransport` | 目标物体位于目标箱内 |

任务名不区分大小写，部署时也接受原生环境类名。`Handover` 沿用原项目 DCD 实验中的命名，其成功条件**不会单独验证双臂之间是否发生交接**。修改这个条件就意味着采用了不同的评测协议。

## 一次性准备运行环境

使用 Linux 下的 Python 解释器，并准备好原生 `cross_eef_sim` 依赖、SAPIEN 3 及其 Pinocchio 支持、SciPy，以及版本匹配的 `uni-robot-agent-runtime` wheel。也可以采用源码可编辑安装，并补齐运行时依赖。任务代码和全部资产由原项目提供，部署过程不会修改原项目。CoDL 的主 Python 环境不需要安装 SAPIEN 或 PyTorch。

注册已经准备好的解释器：

```bash
uni-robot-agent setup --integration crosseef \
  --runtime-python /path/to/prepared-runtime/bin/python \
  --native-root /path/to/crosseef-merged \
  --cache-dir "$PWD/.runtime-cache"
```

这一步只检查模块能否导入并记录配置，不安装依赖，也不下载资产。源码安装必须包含本次新增的接入代码；较早发布的 wheel 不包含此功能。

如果原项目已有可用环境，可以另建一个本地 Python 环境，通过 `.pth` 文件指向原环境的 `site-packages`，复用已经安装的原生依赖，同时将 CoDL 框架依赖安装在新环境中。两者应使用相同的 Python 次版本，不要向原环境安装新依赖。这样可以避免重复安装大型仿真或机器学习包，但新环境会依赖原环境：需要保留原环境，并在其依赖更新后重新验证。需要可复现实验时，完全隔离的运行环境更合适。本次本地验证采用了上述复用方式。

即使不打开窗口，SAPIEN 仍需要访问主机 GPU 和 Vulkan。本接入会拒绝启用 `CROSS_EEF_SIM_NO_RENDER`，因为只有物理仿真的场景无法提供 Agent 所需的图像观测。接入过程不包含安装或更换驱动的步骤。

## 启动一个回合和 Agent

在 CoDL 工作目录中激活主环境后执行：

```bash
uni-robot-agent deploy env \
  --integration crosseef \
  --cache-dir "$PWD/.runtime-cache" \
  --task CanSortDual --seed 0 --depth \
  --port 18790
```

将 `CanSortDual` 替换为上表中的其他任务名即可切换任务。该命令会在前台运行，并打印环境服务 URL，请保持此终端运行。每次部署对应一个回合：结束后按 Ctrl+C 停止服务，再次执行命令可以重置环境或切换任务。如果要同时运行多个回合，需要使用不同端口。端口被占用并不表示任务已经重置。

在第二个终端中激活 CoDL 环境，并配置模型服务商的凭据。新开的终端不会继承另一个终端里用 `export` 设置的变量。以下命令适用于 zsh，输入的密钥不会回显，也不会作为命令保存在历史中：

```zsh
source .venv/bin/activate
read -rs 'UNI_ROBOT_AGENT_API_KEY?请输入 API Key：'
export UNI_ROBOT_AGENT_API_KEY
printf '\n'
```

然后连接 Agent：

```bash
uni-robot-agent run \
  --integration crosseef \
  --env-url http://127.0.0.1:18790 \
  --model YOUR_MODEL_ID \
  --provider-profile YOUR_PROVIDER_PROFILE \
  --provider-url YOUR_PROVIDER_URL \
  --action-profile direct --no-sam3 \
  --output-dir ./runs --monitor
```

请使用能够接收相机图像的模型及服务接口。打开 `run` 打印的 `Monitor:` 地址，通常为 `http://127.0.0.1:8765`。环境服务 URL 提供的是类型化 API，不是浏览器可视化页面。监控界面显示已发布的相机快照和动作记录，不是持续推进仿真的窗口；物理仿真只在执行动作时推进。`--tool-profile clean` 可以选择共用的四工具基线。本接入尚未实现 Hybrid/ACT 策略执行。

也可以使用 `run --deploy local --integration crosseef --task CanSortDual --cache-dir "$PWD/.runtime-cache" ...`，让 Agent 运行流程同时管理环境的启动和停止。采用这种方式时，不要传入 `--env-url`。

通过 [Python SDK](sdk.md) 观察或控制环境不需要调用模型 API。例如，部署一个新回合后执行：

```python
from uni_robot_agent import Session, SessionConfig

with Session(SessionConfig(
    integration="crosseef", env_url="http://127.0.0.1:18790",
    no_sam3=True, output_dir="runs",
)) as session:
    view = session.tools.call("capture_scene", {})
    assert view.success, view.error
    held = session.tools.call("hold", {"steps": 2})
    assert held.success, held.error
    # 结束当前回合，不代表任务已经成功完成。
    session.finish()
```

## 原生环境接口约定

- 机械臂对外名称为 `left` 和 `right`。位姿对应原生 `link_tcp`，位置使用世界坐标系、单位为米，姿态使用 `wxyz` 四元数。`link_tcp` 位于夹爪基座沿 +Z 方向 0.172 m 处。共用的模型工具仍接收常规 XYZ/RPY 参数，并将其转换为服务接口约定的格式。对外发布的机器人资料仅包含机器人自身的 URDF 运动学信息和基座位姿。
- 原生 Pinocchio IK 在各机械臂的根坐标系内求解七个机械臂关节。推进物理仿真前会验证两臂目标，检查正运动学（FK）残差和关节限位。不可达目标会被拒绝，且不会推进仿真。每个控制周期内，机械臂各关节的目标变化最多为 0.12 rad。这不是无碰撞路径规划器；原生 PD 控制和接触动力学保持不变。
- 夹爪值为 0 表示闭合，1 表示张开。原生控制器处理驱动关节方向反转和从动关节（mimic joints）。反馈的开合值来自主驱动关节的实际测量，归一化容差为 0.05。它不是以米为单位的线性指间距，也不能证明已经夹住物体。机械臂和夹爪可能需要多次工具调用才能稳定到位，应检查实际测量反馈。
- 每条被接受的底层动作指令执行一次原生 `env.step`，默认控制频率为 20 Hz、物理仿真频率为 480 Hz。服务默认允许 1,200 个控制步。达到原生成功条件或耗尽步数都会结束回合；`finish` 不能修改任务成功判定。本接入不对外提供原始动作数组、纯关节控制命令、关节预览或 Hybrid actor 能力。
- 前视和俯视相机分辨率均为 640×480，提供光学坐标系下的内外参，并可选输出以米为单位的深度（`--depth`，默认只输出 RGB）。`--cameras front` 可以只选择前视相机。环境重置及每次动作执行后进行渲染；获取观测时复用最近的图像，不推进物理仿真。场景物体位姿、奖励、任务判定器状态和原生特权观测均保留在服务内部。
- 回合记录包含任务、控制器和 URDF 源文件的哈希值，以及随机种子、机器人名称和 SAPIEN 版本。因此可以使用带有本地修改的研究项目，但这不等于锁定了每个网格资产或全部间接依赖的版本。

如需修改步数上限，可以在原生运行环境的解释器中直接启动服务：

```bash
python -m uni_robot_agent.integrations.crosseef.server \
  --native-root /path/to/crosseef-merged --task LiftTray \
  --run-id lift-probe --output-dir ./runs/lift-probe \
  --max-steps 600 --depth --port 18790
```

输出目录必须是尚不存在的新目录。

## 验证范围

在 RTX 4060 Laptop GPU 上，四个任务均以随机种子 0 加载了两条配备 G2 夹爪的 xArm7，成功渲染两路 RGB/深度图像、保持机械臂位姿，并执行了 TCP 向上移动 15 mm 的动作。经过 60 个控制周期后，位置误差约为 0.83 mm。不可达目标被拒绝且未推进状态；重复调用结束操作返回相同的原生判定结果。生成的图像也经过了人工视觉检查。

共用 HTTP 服务和 SDK 已验证观测、快照、保持位姿、双臂协同移动及 G2 开合测量反馈。过期状态对应的动作命令会被拒绝。此外，还验证了仅 RGB 模式、位姿控制与关节保持混合命令、步数耗尽终止，以及可重复调用的资源清理操作。监控页面能够提供运行记录和相机图像。

这些测试属于接入验证，原生结果为 `task_success=false`，不代表成功完成任务，也不构成基准测试成绩。验证过程中没有调用模型 API，也没有使用策略模型权重。

## 排查 Agent 启动失败

如果出现 `Missing environment variable: UNI_ROBOT_AGENT_CODEX_KEY`，请在**启动 Agent 的终端**设置 `UNI_ROBOT_AGENT_API_KEY`。前者是框架传给 Codex 子进程的内部变量，一般不需要手动设置。

如果回合在 `turns=0`、`steps=0` 时失败，不能据此认定仿真连接失败，应检查具体的 Agent 错误。较早的错误处理可能只显示 `Codex session ended without output`，掩盖了 SDK 返回的具体原因。

失败的 Agent 会结束当前环境回合。修复配置后，请先在环境终端按 Ctrl+C，再重新执行 `deploy env`，然后启动 Agent。

只查看已有回合的相机图像和记录不需要 API Key，可使用运行日志给出的回放命令：

```bash
uni-robot-agent monitor --run-dir /path/to/run-directory
```
