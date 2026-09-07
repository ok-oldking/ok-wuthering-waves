# OK-WW 原生 macOS 前台模式——长期工作分支实施方案

状态：**实施计划；不得削弱 `MACOS_ENGINEERING_CONSTRAINTS.md`**

2026-09-05：Stage D/F/H 的分辨率验收按已接受的 ADR `decisions/0001-native-macos-aspect-ratio.md` 增加原生16:10路径；1920×1080保留为16:9回归目标。代码适配、真实输入/视觉端到端和packaged app证据分别记录。

目标：Apple Silicon arm64、macOS 15+（当前 packaged MVP）、Python 3.12 arm64、官方《鸣潮》Mac 客户端、1920×1080 首个硬件验收、CPU OCR/推理

2026-09-06：用户授权 contributor 分支采用 OK-WW ADR `docs/development/decisions/0003-macos-packaged-minimum-version.md`，当前 packaged MVP 不再承诺 macOS 13/14。框架公开 API 设计与 host gate 仍为 13+。此为本分支的产品基线决定，不代表 upstream 接受；下方早期阶段状态和历史验收不证明当前 exact SHA 或新 package 通过。

分支：`ok-script` 与 `ok-wuthering-waves` 的 `feature/macos-foreground-mvp`

本文件描述同一长期分支内的执行顺序，不要求拆分阶段性 PR。所有能力在有对应证据前保持 `not-implemented`，所有任务在真机端到端通过前不得标为 `validated`。

## 1. 总体目标

```text
官方《鸣潮》Mac 客户端
        │
        ├── AppKit + ScreenCaptureKit metadata：窗口发现、选择、重绑
        ├── persistent SCStream：连续内容帧
        └── Quartz/Core Graphics：仅前台输入
                         │
                         ▼
                    ok-script
        target / capture / input / permission / capability
                         │
                         ▼
                  OK-WW 游戏集成
        OCR / template / color / YOLO / task compatibility
```

最终用户路径：

1. 用户从正常安装位置启动官方游戏和 OK-WW；
2. OK-WW 发现或让用户选择真实游戏窗口；
3. 用户授予 Screen Recording 和 Accessibility；
4. 持久 `SCStream` 发布最新 BGR 内容帧；
5. 任务按当前 provider capabilities 进行执行前门控；
6. 任务开始时可请求一次激活，并等待观察到游戏成为 frontmost；
7. 每个普通输入或短原子批次前重新验证 PID、frontmost、input gate 和 geometry generation；
8. 失焦、目标消失、权限失效、fatal capture、task stop 或 app exit 时立即阻断普通输入并 `release_all()`。

本计划不增加后台/最小化控制、BetterDisplay、虚拟显示器、私有 API、`CGEvent.postToPid`、进程注入、Metal hook、TCC 绕过或 MaaFramework 运行时依赖。

## 2. 当前分支基线

### 已完成

- Stage 0：工作区、fork、remotes、长期分支、参考 arm64 Python 3.12 环境、初始 install/import/test 证据；
- Stage 1：平台阻塞清单、任务/游戏阻塞清单、ADR、upstream sync 与 rollback 说明。

### 当前工作树正在完成

旧 Stage 2 的平台安全工作与本次方向调整合并为新的阶段 A/B：

- dependency marker；
- deterministic editable build；
- capture/interaction/Qt/notification lazy import；
- CursorService seam；
- `DeviceCapabilities`；
- task enable/execute preflight；
- OK-WW task compatibility declaration；
- 中文约束和验收文档；
- Darwin import 与 capability tests。

在提交、推送和 Windows/macOS CI 结果确认前，不将阶段 B 标为完成。

## 3. 仓库职责

### `ok-script`

负责：

- 平台安全依赖和 import/provider selection；
- `DeviceCapabilities` 和 generic task preflight；
- `DesktopWindowTarget` 与 Windows adapter；
- macOS window discovery/rebind；
- permission service；
- persistent `ScreenCaptureKitCaptureMethod`；
- geometry snapshot/generation；
- `QuartzForegroundInteraction`；
- Mac key map；
- `ForegroundGuard`；
- `HeldInputState` / `release_all()`；
- `CursorService`；
- 通用 diagnostics 和 tests。

### `ok-wuthering-waves`

负责：

- 真实客户端 app/window hints；
- Mac hotkey choices；
- CPU inference / NPU off；
- task capability requirements；
- task status 与兼容矩阵；
- evidence-driven visual overrides；
- user-facing permission/focus/install/limitations docs；
- real-game task evidence。

不得在 OK-WW 私建 Mac capture/input backend 或 `win32api` 外形 shim。

## 4. 能力与任务模型

### 4.1 provider capabilities

`ok-script.DeviceCapabilities` 至少包含：

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

全部默认 `False`。后端只有在实现和 fail-closed 语义真实存在时才能置 `True`。

### 4.2 task levels

- `MAC_BASIC`：菜单、登录、领取、合成、背包、强化、固定页面 OCR/模板和绝对点击；
- `MAC_LOCKED_GAMEPLAY`：持续 W/A/S/D、中键锁敌/居中、左右键保持和键鼠组合，不要求自由镜头；
- `MAC_FULL_CAMERA`：任意 relative X/Y、连续 delta、精确路线转向。

等级用于验收分组；每个任务仍声明精确 capability requirement。

### 4.3 task status 与 evidence

任务状态：`validated`、`experimental`、`unsupported`。

provider evidence：`not-implemented`、`unit-tested`、`hardware-validated`、`packaged-app-validated`。

二者独立。单元测试通过只可推进 provider contract，不会把 task 标为 `validated`。

### 4.4 当前方向

当前登记任务的静态审计没有发现自由镜头 delta 调用；`center_camera()` 是屏幕中心中键点击。实施优先级改为：

```text
基础键鼠
→ 持续按键/中键/按钮保持
→ OK-WW 实际组合
→ 对应任务端到端
→ 最后验证 relative mouse
```

relative mouse 不再阻断已经通过的 `MAC_BASIC` 或 `MAC_LOCKED_GAMEPLAY`；它只阻断明确要求 `MAC_FULL_CAMERA` 的任务和完整 camera/route parity 声明。

## 5. 阶段 A——现状审计与方向修订

### 工作

1. 搜索两个仓库中的：
   - `win32`、`windll`、`WinDLL`、`winreg`；
   - `Hwnd` / `HWND`；
   - `send_key_down` / `send_key_up`；
   - `middle_click`；
   - `mouse_down` / `mouse_up`；
   - `move_relative`、camera 和其他相对输入；
2. 区分 shared import blocker、Windows-only implementation 和 game task dependency；
3. 输出当前分支真实状态和差距清单；
4. 修订中文约束，取消 relative mouse 全局阻断；
5. 明确当前 17 个登记任务的 level、required capabilities 和 status；
6. 保持 foreground-only 边界。

### 产物

```text
# OK-WW
docs/development/macos-work-branch-direction-audit.md
MACOS_ENGINEERING_CONSTRAINTS.md
docs/development/macos-foreground-port-plan.md
docs/development/macos-capability-matrix.md
src/macos_capabilities.py

# ok-script
docs/development/macos-foreground-platform-constraints.md
docs/development/macos-stage2-direction-adjustment.md
```

### Gate

- 文档不再包含“relative mouse 失败则整个 MVP 不能发布”；
- 所有登记任务有显式 declaration；
- 未声明任务默认 fail closed；
- 没有把任何未真机测试任务标为 `validated`。

## 6. 阶段 B——平台安全 build/import 与 capability gate

### `ok-script` 工作

- 修正普通 PEP 517/editable build 的网络/未声明构建依赖；
- 对 Windows-only packages 添加 marker；
- 声明最小 Darwin PyObjC wrappers；
- 拆 common/Windows key map；
- capture/interaction exports lazy/platform-selected；
- `DeviceManager` 在 provider selection 后才加载 platform implementation；
- Qt start/debug、overlay、notification、process、analytics 等 shared import 不加载 Win32；
- `CursorService` 平台 seam；
- `DeviceCapabilities` 和全 False 默认；
- task enable 和 execution 前 capability preflight。

### OK-WW 工作

- `CombatCheck.py` 使用 framework CursorService；
- `MouseResetTask.py` 不直接导入 Win32，并在 Mac P0 明确 `unsupported`；
- `WWOneTimeTask.py` 不判断具体 `PostMessageInteraction` 类型；
- 所有 entry/task/scene/custom tab 可在 Darwin 导入；
- 注册任务映射到 macOS compatibility declaration。

### 无游戏 Gate

```bash
# 从 OK-WW venv
./.venv/bin/python -m pip install -e "../ok-script[ocr,qt,dev]"
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -m pip check

./.venv/bin/python -c "import ok"
./.venv/bin/python -c "from ok.device.DeviceManager import DeviceManager"
./.venv/bin/python -c "import src"

# ok-script
../ok-wuthering-waves/.venv/bin/python -m pytest -q

# OK-WW
./.venv/bin/python -m pytest -q tests/test_macos_imports.py tests/test_macos_capabilities.py
./.venv/bin/python -m unittest discover -s tests -p 'Test*.py'
```

验证 Darwin `sys.modules` 中没有 Win32-only backend。Windows CI 必须对 changed paths 保持绿色。

## 7. 阶段 C——`DesktopWindowTarget`、真实窗口与权限

### `ok-script` 实现

平台中立 contract 至少包含：

```text
process_id
window_id
bundle_identifier
application_name
title
outer_geometry
content_geometry
capture_geometry
display_scale
generation
exists()
is_foreground()
request_activation()
wait_for_observed_activation()
refresh()/rebind()
```

Windows adapter 包装现有 `HwndWindow`，尽量不改行为。

macOS discovery：

1. 低频获取 `SCShareableContent`；
2. 将 `SCWindow` 与 owning application/PID 关联；
3. 应用 bundle ID、标题、尺寸、层级等组合过滤；
4. 多候选时让用户明确选择；
5. 持久化稳定 hints，不持久化旧 PID/window ID；
6. 进程/窗口重建后重新绑定并提升 generation。

### OK-WW 实现

- 在真实官方客户端上记录 bundle identifier、应用名、窗口标题和窗口特征；
- 在 `config.py` 添加独立 `macos` block；
- 不复用 `windows` block，不猜唯一 bundle ID；
- 提供手动选择兜底。

### permission service

- Screen capture preflight/request；
- Accessibility trust/prompt；
- 明确 permission-required/revoked 状态；
- 无 tight retry；
- 不修改 TCC。

### 早期 packaged identity checkpoint

窗口/权限 seam 建立后，即建立稳定 bundle identifier 的内部 `.app` 骨架，尽早验证 TCC identity，而不是等全部 task 完成。

### Hardware Gate

- 发现正确 app/window；
- 展示 PID、bundle ID、window ID、outer/content geometry 和 scale；
- 手动选择有效；
- activation 必须观察到 frontmost；
- Command-Tab 状态变化；
- process exit、window replacement 和 PID 变化可检测；
- source identity 和 stable `.app` identity 的 permission 状态分别记录。

## 8. 阶段 D——持久 ScreenCaptureKit 流和几何

### 生产架构

```text
selected SCWindow
→ SCContentFilter(desktopIndependentWindow:)
→ one SCStreamConfiguration
→ persistent SCStream
→ CMSampleBuffer callback
→ newest complete frame only
→ owned BGR ndarray
```

### 实现要求

- `showsCursor = false`；
- callback 不运行 OCR/task/Qt；
- 不每帧调用 `SCShareableContent`；
- 不每帧重建 filter/config；
- 不使用每帧 `SCScreenshotManager`；
- storage 有界，只保留最新完整帧；
- 处理 BGRA、row stride、padding 和 lifetime；
- frame 是 BGR `uint8` `(h,w,3)`；
- 内容区不含标题栏、边框、阴影；
- frame 与 immutable geometry generation 绑定；
- rebind/resize/scale change 开始时立即失效旧帧。

### 几何模型

明确区分：

- macOS global logical point；
- `SCWindow.frame` outer frame；
- actual stream pixel frame；
- game content area；
- Qt logical coordinate；
- display scale；
- internal render resolution。

视觉尺寸以 actual frame 为事实来源。不得直接把 `SCWindow.frame.width/height` 当成内容像素。

### Unit tests

- BGRA→BGR；
- stride/padding；
- publication ownership；
- newest overwrite；
- bounded storage；
- resize/rebind generation；
- scale 1.0/2.0/非整数假设；
- offsets；
- title-bar/content crop；
- frame pixel→global logical point；
- stale generation rejection。

### Hardware Gate

- 1920×1080 内容帧；
- 无 cursor/title/border/shadow；
- color 正确；
- 1000+ frames 无 stall、明显 leak 或 queue growth；
- FPS、frame age、overwrite、generation、rebuild 可观测；
- resize/rebind 有明确恢复或终止状态。

## 9. 阶段 E——Quartz 基础输入与 fail-closed 安全

### Mac key map

任务继续使用逻辑键名；后端统一转换到 `CGKeyCode`。覆盖 OK-WW 实际使用的：

```text
w a s d
e q r f t
space shift tab
f2 b 1 2 3
esc enter alt ...
```

### 基础接口

```text
send_key
send_key_down / send_key_up
left/right/middle down/up/click
mouse button hold
absolute move/click
scroll
release_all
```

relative/delta 在同一 backend 中作为独立 capability，不阻塞基础接口完成。

### `ForegroundGuard`

任务开始可以 request activation once，然后等待 observed frontmost。每个事件/short batch 前：

```text
target exists / PID alive
→ target app is frontmost
→ input gate open
→ geometry generation current
→ post CGEvent
```

失焦时不得自动抢回焦点，不得 post-to-PID，不得向当前其他前台 app 发送普通输入。

### `HeldInputState`

跟踪 held keys、held buttons、owner/batch、invalidated/shutdown 和 generation。

`release_all()`：

- 幂等；
- target vanished 后安全；
- 单个 release 失败继续；
- 最终清空内部 state；
- invalidated path 只发布已记录 key-up/button-up。

### Lifecycle

focus loss、task cancel、executor stop、device switch、target exit、fatal capture、permission loss 和 app exit 都必须 release。

shutdown：block ordinary input → release → stop stream/workers → destroy objects。

### Unit Gate

- key/button state transitions；
- duplicate down policy；
- one release failure；
- idempotent release；
- focus race；
- no ordinary event after invalidation；
- target exit；
- capture/permission failure；
- shutdown order；
- task receives explicit reason。

## 10. 阶段 F——真实 OK-WW 输入验收

### 第一优先级

- key tap；
- key down/up；
- W/A/S/D hold；
- E/Q/R/F/Space/Shift/Tab；
- left/right/middle；
- mouse button hold；
- absolute click；
- scroll。

### 第二优先级

- W + left；
- W + skill key；
- W + middle；
- middle lock/center；
- right-button hold；
- change direction releases old key；
- task stop/focus loss clears all state。

### 安全人工测试

```text
hold W → Command-Tab 到文本编辑器
hold Shift/right/middle → 切换应用
持续输入时退出游戏
持续输入时关闭 OK-WW
运行时撤销 Accessibility
运行时撤销 Screen Recording
```

每个场景都必须：不向新 app 泄漏字符/点击；所有 held state 清空；task 明确暂停/停止；不得自动抢焦点恢复。

### 第三优先级：relative mouse

在 basic/locked inputs 之后验证：

- X/Y；
- continuous delta；
- movement/attack concurrency；
- cursor drift/recovery；
- game cursor lock state。

失败只限制 `MAC_FULL_CAMERA`，不推翻已通过的 basic/locked evidence。

## 11. 阶段 G——任务矩阵与端到端

### 开放原则

- 每个 task 按真实 required capabilities 和 hardware result 开放；
- unknown declaration fail closed；
- status 仅在端到端证据后从 `experimental` 变为 `validated`；
- 未通过保持 `experimental` 或 `unsupported`；
- UI 显示缺失 capability/限制，不运行到中途才失败。

### 首批目标

1. 一个 `MAC_BASIC` 菜单/领取/强化/合成任务端到端；
2. Auto Pick 等主要依赖 key tap、并可能需要 scroll 的简单 trigger；
3. 若 locked inputs 通过，一个代表性 `MAC_LOCKED_GAMEPLAY` 流程；
4. 之后扩展 domain/combat/movement；
5. 只有 relative hardware pass 后才开放 `MAC_FULL_CAMERA` 路线。

### 视觉验证

使用 normalized Mac frames 验证：

- login/entry；
- overworld HUD/team；
- skill/liberation/echo readiness；
- F interaction；
- guidebook/map/teleport；
- stamina/claim/confirm；
- backpack/echo enhancement；
- domain start/result；
- combat target/lock。

修复优先级：content geometry → normalization → threshold/color/gamma/OCR params。只有可重复平台差异且通用修复伤害 Windows 时，才增加 `assets/macos`。

## 12. 阶段 H——CI、内部打包和最终验收

### CI

- macOS arm64/Python 3.12 dependency/install/import/unit job；
- Windows regression job；
- provider/target/capture/geometry/input/capability/task-gate tests；
- CI 不要求游戏或弹权限提示。

### 内部 `.app`

当前最低 macOS 15.0。逐个解析主程序与全部 native arm64 slice 的真实 minos，并与 plist、构建 metadata 和用户安装说明一致；不忽略未知项，不伪改旧系统支持。Python/PySide6 wrapper 与 Qt 原生框架分别记录，不能用其中一部分较低的 minos 推断整个应用。

稳定 bundle identifier，安装到 `/Applications`，验证：

- arm64 native libraries；
- Qt platform plugin；
- OpenCV/OCR/inference/PyObjC；
- assets/i18n；
- Screen Recording / Accessibility；
- restart/rebuild permission persistence；
- revoke behavior；
- shutdown release/stream close。

### 最终 MVP Gate

基础 MVP 至少要求：

- correct window binding；
- 1920×1080 content frame；
- OCR/template basics；
- key tap/hold/release；
- left/right/middle + absolute click；
- focus loss no input leak；
- one `MAC_BASIC` task end-to-end；
- Windows tests green；
- stable-identity `.app` permission validation；
- accurate supported/experimental/unsupported matrix；
- docs and rollback complete。

`MAC_LOCKED_GAMEPLAY` 和 `MAC_FULL_CAMERA` 是附加声明门槛，不再反向阻断已通过的基础 MVP。

### 公开分发

公开产物另要求：Developer ID Application、Hardened Runtime、timestamp、notarization、staple 和 clean-user Gatekeeper test。ad-hoc signing 不算该证据。

## 13. 主要风险

### focus/release race

最高安全风险。普通 event、invalidation 和 release 必须共享线程安全 gate；任何安全回归立即降级并 fail closed。

### frame/content geometry

不要把 outer frame、logical points 和 stream pixels 混用。所有输入绑定 current generation。

### TCC identity

尽早建立 stable internal `.app`，避免在开发完成后才发现 Terminal permission 与 packaged identity 不一致。

### current Qt/macOS native tests

部分 `qframelesswindow` 测试在 headless/offscreen macOS 可能 segfault，应明确分离需要 native WindowServer 的 UI 测试，而不是降低 runtime safety。

### relative camera

是 `MAC_FULL_CAMERA` 的功能风险，不是基础 MVP 全局风险。先完成实际 held-key/middle/button combinations。

### Windows regression

平台拆分不能破坏 WGC、BitBlt、PostMessage、HWND、ADB/browser 或 persisted config；需要 Windows CI，而 Mac 本地测试不能代替。

## 14. 故障状态建议

```text
MAC_SCREEN_CAPTURE_PERMISSION_REQUIRED
MAC_ACCESSIBILITY_PERMISSION_REQUIRED
MAC_GAME_NOT_FOUND
MAC_GAME_WINDOW_NOT_FOUND
MAC_GAME_NOT_FOREGROUND
MAC_TARGET_EXITED
MAC_CAPTURE_STREAM_STOPPED
MAC_CAPTURE_REBIND_FAILED
MAC_UNSUPPORTED_GEOMETRY
MAC_INPUT_GATE_CLOSED
MAC_INPUT_POST_FAILED
MAC_TASK_CAPABILITY_MISSING
MAC_TASK_UNSUPPORTED
MAC_RELATIVE_MOUSE_UNSUPPORTED
```

terminal state 不得转化为 endless tight loop。

## 15. 阶段性汇报格式

```text
已完成
- ...

已验证
- 命令：
- 结果：

仍未验证
- 需要真实《鸣潮》客户端：
- 需要打包应用身份：

风险或阻断
- ...

下一步
- ...
```

无法在当前环境执行的硬件或 packaged-app 项目必须明确写“待真机验收”，不得写成“已支持”。
