# macOS 前台模式工作分支方向调整审计

记录日期：2026-09-04

状态：**当前长期分支的事实审计与后续实施基线**

适用分支：

- `ok-script: feature/macos-foreground-mvp`
- `ok-wuthering-waves: feature/macos-foreground-mvp`

本记录吸收类似原生 macOS 3D 游戏助手已经证明的可行路径，但不引入 MaaFramework 运行时依赖，也不沿用一次性截图、输入前反复抢焦点、几何混用或不稳定应用身份等做法。

## 1. 当前分支的真实状态

### 1.1 已完成且已有历史提交

- Stage 0：工作区、fork、remote、长期分支、参考环境与基线证据；
- Stage 1：平台阻塞点清单、ADR 流程、同步和回滚约束；
- 两个仓库都仍在长期集成分支上，没有阶段性 PR。

### 1.2 当前未提交工作树

`ok-script` 已存在但尚未提交的 Stage 2 修改，主要覆盖：

- Windows-only dependency marker；
- 确定性 editable build；
- capture/interaction lazy import；
- Darwin 上的 Qt、通知、overlay 和进程工具导入隔离；
- CursorService 边界；
- macOS import tests。

OK-WW 已存在但尚未提交的修改，主要覆盖：

- `CombatCheck.py` 和 `MouseResetTask.py` 移除直接 `win32api` 调用；
- `WWOneTimeTask.py` 移除具体 `PostMessageInteraction` 类型判断；
- Darwin 全任务导入测试。

因此，上一轮把 Stage 2 描述为“已经提交并推送”并不符合 Git 工作树事实。本轮以实际 `git status` 为准，在测试和文档完成前不提升阶段状态。

## 2. 与新方向的差距

### 2.1 relative mouse 被错误设为整个 MVP 的统一阻断项

旧文档在以下位置仍把相对镜头当作全部战斗、跑图甚至最终 MVP 的统一门槛：

- `AGENTS.md`；
- `MACOS_ENGINEERING_CONSTRAINTS.md` 第 11、20、21 节；
- `docs/development/macos-foreground-port-plan.md` Stage 5 和风险章节；
- `docs/development/macos-capability-matrix.md` CAP-33、CAP-49、CAP-50；
- `docs/development/macos-stage1-game-inventory.md`。

这与当前 OK-WW 实际输入模型不符，必须改为任务能力分级。

### 2.2 当前注册任务没有自由镜头 delta 调用

对 `config.py` 登记的 11 个 one-time task 和 6 个 trigger task 进行 AST 审计后确认：

- 当前注册任务没有调用自由相对镜头接口；
- `ExecutorOperation.move_relative(x, y)` 是把帧内百分比换算成**绝对坐标移动**，不等于 `relative_mouse`；
- `BaseWWTask.center_camera()` 当前实现为屏幕中心中键点击；
- 现有移动主要依赖 `send_key_down` / `send_key_up`、W/A/S/D、右键保持、中键和视觉目标位置；
- 现有战斗角色实现大量使用左键保持和独立 key down/up。

因此应先验证持续按键、中键、左右键保持及组合输入，再决定哪些未来路线需要自由镜头 delta。

### 2.3 尚无可运行的原生 Mac provider

下列能力目前仍未实现：

- `DesktopWindowTarget`；
- 官方游戏窗口枚举、手动选择和重绑；
- Screen Recording / Accessibility 权限服务；
- 持久 `SCStream`；
- 内容区裁剪和几何代次；
- Quartz 前台输入；
- `ForegroundGuard`；
- `HeldInputState` / `release_all()`；
- 稳定 bundle identifier 的内部 `.app`；
- 真实《鸣潮》窗口、截图、输入和任务验收。

不得把平台安全导入或数据模型完成描述为“Mac 自动化已支持”。

### 2.4 打包身份验证排得过晚

旧计划把内部 `.app` 和 TCC 验证集中在后期。新顺序要求在窗口/权限边界建立后尽早创建稳定 bundle identifier 的内部包，用于验证：

- Screen Recording；
- Accessibility；
- 从 `/Applications` 启动；
- 重新打包和重启后的权限持久化；
- 撤销权限后的明确失败状态。

公开发布仍单独要求 Developer ID、Hardened Runtime、timestamp、notarization 和 staple。ad-hoc 签名不能作为公开发布证据。

## 3. 更新后的能力模型

### 3.1 设备能力

`ok-script` 提供平台中立 `DeviceCapabilities`：

```text
keyboard_tap
keyboard_hold
absolute_mouse
mouse_left
mouse_right
mouse_middle
mouse_button_hold
scroll
relative_mouse
foreground_only
```

所有能力默认 `False`。新后端必须显式声明，避免继承空方法后被误判为可用。

`relative_mouse` 专指自由镜头的相对/delta 输入；它不等于任务层把百分比坐标换算成绝对坐标的 `move_relative` helper。

### 3.2 任务能力等级

| 等级 | 含义 | 典型依赖 |
|---|---|---|
| `MAC_BASIC` | 菜单、领取、登录、背包、强化、固定页面 OCR/模板流程 | key tap、绝对点击、左键、前台安全；按任务精确声明 |
| `MAC_LOCKED_GAMEPLAY` | 锁定式战斗、自动拾取后的部分移动、视觉引导移动 | 持续 W/A/S/D、中键、左右键保持、键鼠组合；不要求自由镜头 |
| `MAC_FULL_CAMERA` | 任意镜头路线和精确转向 | `MAC_LOCKED_GAMEPLAY` 加 `relative_mouse` |

等级用于风险和验收分组；每个任务仍声明精确的 `DeviceCapabilities`，不得只靠等级粗暴开启。

### 3.3 任务状态

任务状态和底层能力证据是两个轴：

任务状态：

- `validated`：对应真机端到端验收通过；
- `experimental`：允许在能力满足时进行真机验收，但不得对用户宣称稳定支持；
- `unsupported`：不得执行。

底层能力证据继续使用：

1. `not-implemented`；
2. `unit-tested`；
3. `hardware-validated`；
4. `packaged-app-validated`。

### 3.4 当前注册任务分级

当前所有拟移植任务都仍未真机验收，状态不得写为 `validated`。

| 任务 | 等级 | 当前状态 | 主要原因 |
|---|---|---|---|
| `MergeEchoTask` | `MAC_BASIC` | `experimental` | key tap、固定/识别框左键点击 |
| `EnhanceEchoTask` | `MAC_BASIC` | `experimental` | key tap、左键点击 |
| `ChangeEchoTask` | `MAC_BASIC` | `experimental` | key tap、左键点击 |
| `AutoLoginTask` | `MAC_BASIC` | `experimental` | 登录/公告识别与左键点击 |
| `AutoPickTask` | `MAC_BASIC` | `experimental` | F key tap；文本候选滚动需要 scroll；不依赖自由镜头 |
| `AutoDialogTask` | `MAC_BASIC` | `experimental` | 视觉识别后左键点击 |
| `FastTravelTask` | `MAC_BASIC` | `experimental` | 视觉识别后左键点击 |
| `AutoCombatTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | key hold、中键、左键保持、组合输入 |
| `FarmEchoTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | W/A/S/D、右键跑动、中键、战斗、滚轮 |
| `NightmareNestTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 移动、战斗和领取子流程 |
| `TacetTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 视觉引导移动、中键和战斗 |
| `ForgeryTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 副本移动与战斗 |
| `SimulationTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 副本移动与战斗 |
| `DailyTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 编排多个子任务，按最宽依赖门控 |
| `MultiAccountDailyTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 编排 DailyTask，按最宽依赖门控 |
| `GardenTask` | `MAC_LOCKED_GAMEPLAY` | `experimental` | 固定页面和持续按键流程 |
| `MouseResetTask` | 无 | `unsupported` | Windows 窗口/光标 workaround，Mac P0 明确禁用 |

当前没有注册任务声明 `MAC_FULL_CAMERA`。未来新增自由镜头路线时必须单独声明并在 `relative_mouse` 硬件通过前保持不可执行。

## 4. 调整后的实施顺序

同一长期分支内改为：

```text
A. 现状审计与中文文档修订
B. 平台安全安装、导入和 capability gate
C. DesktopWindowTarget、窗口发现、前台观察与权限
D. 持久 SCStream、内容区和几何代次
E. Quartz 基础输入、ForegroundGuard、HeldInputState、release_all
F. 真实 OK-WW 基础/组合输入验收，再测试 relative mouse
G. 按真实结果开放任务、完成端到端矩阵
H. CI、稳定 bundle ID 内部 .app、TCC 和最终验收
```

relative mouse 未通过时：

- 不阻断已经通过的 `MAC_BASIC` MVP；
- 不阻断已经通过的 `MAC_LOCKED_GAMEPLAY` 任务；
- 阻断 `MAC_FULL_CAMERA` 与任何依赖自由镜头的声明；
- 不得声称完整战斗、完整跑图或 Windows 功能对等。

## 5. 本轮需要修改的文件

### `ok-script`

```text
AGENTS.md
docs/development/macos-foreground-platform-constraints.md
docs/development/macos-stage2-direction-adjustment.md
ok/device/capabilities.py
ok/device/interaction_methods/base.py
ok/device/DeviceManager.py
ok/task/task.py
ok/core/start_controller.py
ok/task/TaskExecutor.py
ok/ui/qt/tasks/TaskCard.py
tests/test_device_capabilities.py
tests/test_platform_imports.py
pyproject.toml
setup.py
.github/workflows/
```

以及当前未提交 Stage 2 import boundary 涉及的 capture、interaction、Qt、notification 和 process 文件。

### `ok-wuthering-waves`

```text
AGENTS.md
MACOS_ENGINEERING_CONSTRAINTS.md
docs/development/macos-foreground-port-plan.md
docs/development/macos-capability-matrix.md
docs/development/macos-work-branch-direction-audit.md
src/macos_capabilities.py
src/task/BaseWWTask.py
src/task/MouseResetTask.py
tests/test_macos_capabilities.py
tests/test_macos_imports.py
```

以及当前未提交的 CursorService 消费和 concrete-backend 解耦修改。

## 6. 当前可声明与不可声明

当前最多可声明为 `unit-tested` 的范围，需要以本轮最终测试结果为准：

- macOS 依赖 marker 与 editable build；
- Darwin 平台安全导入；
- 全部登记任务模块导入；
- `DeviceCapabilities` 的匹配和 fail-closed 默认值；
- 任务在 enable/执行前进行 capability gate；
- `relative_mouse=False` 不阻断 basic/locked requirement；
- `MouseResetTask` 在 Mac provider 上明确不支持；
- task card 以稳定状态码显示 experimental/unsupported/missing capabilities，并阻止不兼容的新 enable。

仍为 `not-implemented` 或“待真机验收”：

- 真实窗口发现和 bundle ID；
- 权限；
- SCStream；
- BGR 内容帧；
- Quartz 输入；
- held-state/focus-loss 安全；
- 中键和持续按键在游戏中的实际效果；
- relative mouse；
- 任一任务端到端；
- packaged-app identity。

## 7. 无游戏环境验证命令

```bash
# ok-script（从 OK-WW .venv 运行）
../ok-wuthering-waves/.venv/bin/python -m pytest -q
../ok-wuthering-waves/.venv/bin/python -m pytest -q \
  tests/test_platform_imports.py tests/test_device_capabilities.py

# OK-WW
./.venv/bin/python -m pytest -q \
  tests/test_macos_imports.py tests/test_macos_capabilities.py
./.venv/bin/python -m unittest discover -s tests -p 'Test*.py'

# 安装与元数据
./.venv/bin/python -m pip install -e "../ok-script[ocr,qt,dev]"
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m pip check
```

Windows 回归必须由 Windows CI 执行；当前 Mac 本机结果不能替代该证据。
