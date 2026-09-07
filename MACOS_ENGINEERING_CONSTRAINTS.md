# OK-WW macOS 前台模式移植——工程约束

状态：**macOS 前台模式 MVP 的规范性产品与工程合同**

2026-09-05 规范修订：已接受的 `docs/development/decisions/0001-native-macos-aspect-ratio.md` 对下文“仅16:9/首验1920×1080”作窄例外，允许 Mac 原生16:10按真实内容帧验收。16:9仍为既有参考/回归目标；不允许拉伸整帧、伪裁切或自动放行任意比例。其余安全及发布门槛不变。

目标基线：Apple Silicon arm64、macOS 15+（当前 packaged MVP）、Python 3.12 arm64、官方《鸣潮》Mac 客户端、前台模式、1920×1080 首个硬件验收、CPU OCR/推理

2026-09-06 规范修订：用户授权 contributor 集成分支按 OK-WW ADR `docs/development/decisions/0003-macos-packaged-minimum-version.md` 将当前 packaged MVP 最低版本收窄为 macOS 15.0；不代表 upstream 已接受。此前产品 13+ 目标被本决策取代，macOS 13/14 不在当前 packaged MVP 支持范围。框架公开 API 设计与通用 host gate 仍为 macOS 13+，不据此承诺 consumer 二进制兼容。历史记录保留其日期与产物身份，不能替代当前提交和新包验收。

本文规定首个原生 macOS 版本的硬性边界。文中的“必须”“不得”“仅允许”和“发布门槛”均为强制要求，不得通过兼容垫片、隐藏回退、空实现、降低安全检查或夸大证据绕过。

## 0. 规范层级与变更控制

- 本文件是 OK-WW macOS 前台 MVP 的最高仓库内规范。
- `docs/development/macos-foreground-port-plan.md` 只描述实施顺序和证据，不得削弱本文件。
- `AGENTS.md`、嵌套说明和适用 skills 同时生效；更具体规则可收紧实现，但不得放宽“仅前台、仅公开 API、失败关闭、Windows 不回归”。
- 发现冲突时，必须在修改运行时代码前解决；安全、仓库职责和兼容性优先于实现便利。
- 有意偏离前台语义、公开 API、仓库职责、持久截图、坐标模型、能力门控、输入安全或 Windows 回归边界时，必须先在 `docs/development/decisions/` 提交 ADR。
- 代码注释、聊天、临时 issue 或 PR 讨论不能代替 ADR。

## 1. 长期分支与交付模型

### 1.1 开发分支

- `ok-script` 与 `ok-wuthering-waves` 都使用 `feature/macos-foreground-mvp` 长期集成分支。
- 分支从已记录的 `upstream/master` SHA 创建。
- `origin` 指向 contributor fork；`upstream` 指向 `ok-oldking` canonical repository。
- 开发提交保持逻辑清晰、可审查、可回滚、可二分，尽量在提交边界可构建。
- 不得为每一阶段创建准备合并的基础设施 PR、占位 PR 或未完成能力 PR。
- 不得把不完整 Mac 支持合入默认分支来解锁后续工作。
- 定期同步 upstream，并按已提交的同步/回滚流程处理冲突。

### 1.2 跨仓库连接

开发期使用 sibling editable install：

```bash
./.venv/bin/python -m pip install -e "../ok-script[ocr,qt,dev]"
./.venv/bin/python -m pip install -e ".[dev]"
```

不得通过 submodule、subtree、复制包、vendoring、可变分支 URL 或临时发布包连接两个仓库。

最终交付是两个协调的完整 MVP PR：

1. `ok-script` PR：可复用平台能力；
2. `ok-wuthering-waves` PR：游戏集成，并使用维护者接受的不可变框架版本或提交。

最终 OK-WW PR 不得依赖：

- mutable branch URL；
- 未提交文件或私有补丁；
- 临时 wheel；
- 开发者绝对路径；
- 未记录的环境 monkey patch。

### 1.3 仓库与证据卫生

不得提交：

- token、私钥、Developer ID、公证凭据或签名证书；
- TCC 数据库或权限绕过材料；
- 个人账户截图、未脱敏日志或私密硬件证据；
- `.venv`、`.app`、`.dmg`、`.pkg`、`.xcarchive`、`DerivedData`、构建缓存；
- 本机绝对路径。

参考外部项目或历史 PR 时必须记录来源、作者归属和许可证兼容性；不得整段照搬未经审查的实验实现。

## 2. 产品目标与非目标

最终产品行为：

```text
用户启动官方《鸣潮》Mac 客户端
        ↓
OK-WW 发现并绑定真实游戏窗口
        ↓
持久 ScreenCaptureKit SCStream 连续取帧
        ↓
标准化为 BGR uint8 NumPy/OpenCV 图像
        ↓
复用现有 OCR、模板、颜色、YOLO 和任务逻辑
        ↓
仅在绑定游戏实际为系统前台应用时发送 Quartz 输入
        ↓
失焦、任务停止、窗口消失、权限失效或截图致命失败
        ↓
立即阻断普通输入、release_all() 并暂停/停止
```

首个正式目标：

- Apple Silicon arm64；
- macOS 15+（当前 packaged MVP）；
- Python 3.12 arm64；
- 官方《鸣潮》Mac 客户端；
- 前台模式；
- 16:9；
- 1920×1080 首个硬件验收；
- CPU OCR/推理；
- 现有 PySide6/Qt GUI；
- 不引入 MaaFramework 运行时依赖。

明确不支持：

- Intel Mac 和 macOS 14 或更早系统上的当前 packaged MVP；
- 后台、最小化、被其他应用覆盖时继续自动化；
- BetterDisplay、虚拟显示器、私有 `CGVirtualDisplay`；
- `CGEvent.postToPid` 后台控制；
- 进程/dylib 注入、swizzling、Metal hook 或反作弊绕过；
- Android 模拟器、云游戏或远程串流替代原生客户端；
- 任意宽高比；
- Mac App Store 首发分发。

## 3. 公开 API 政策

仅允许使用公开 Apple API：

- ScreenCaptureKit；
- AppKit；
- Core Graphics / Quartz；
- ApplicationServices Accessibility API；
- Foundation / CoreFoundation。

禁止：

- 私有 WindowServer SPI；
- 私有 `CGVirtualDisplay*`；
- injection、hook、method swizzling；
- 直接修改游戏进程代码、数据或运行状态；
- 无焦点、隐藏或后台控制的未公开接口；
- 自动修改 TCC 或通过 root 绕过权限。

## 4. 仓库职责

### 4.1 `ok-script` 必须实现

- 平台安全 dependency marker 和 lazy import；
- 平台中立 `DesktopWindowTarget`；
- Windows `HwndWindow` 兼容 adapter；
- macOS 窗口发现、手动选择、PID/window 重绑；
- `ScreenCaptureKitCaptureMethod` 持久 `SCStream`；
- `QuartzForegroundInteraction`；
- `ForegroundGuard`；
- `HeldInputState` 与 `release_all()`；
- `CursorService`；
- Screen Recording / Accessibility 权限服务；
- `DeviceCapabilities`；
- 通用帧/内容区/显示器/输入坐标转换；
- 平台契约测试、生命周期和可观测错误状态。

### 4.2 `ok-wuthering-waves` 必须实现

- 经真实安装观察的《鸣潮》Mac app/window 匹配提示；
- Mac CPU 推理配置与 NPU 关闭/安全忽略；
- task/combat/scene 不直接调用 OS API；
- 任务精确 capability requirement；
- `MAC_BASIC` / `MAC_LOCKED_GAMEPLAY` / `MAC_FULL_CAMERA` 分级；
- `validated` / `experimental` / `unsupported` 状态；
- Mac 任务兼容矩阵；
- 必要且有证据的 `assets/macos` 覆盖；
- 用户权限、安装、焦点、安全和限制文档；
- 真机任务验收记录。

### 4.3 禁止私建后端或兼容垫片

- 不得新增 `src.compat.win32api` 一类保持 Win32 外形、在 Darwin 内调用 Quartz 的 shim。
- task、combat、scene 不得直接导入 AppKit、Quartz、ScreenCaptureKit 或 Win32。
- 不得把 `ok-script` 后端复制进 OK-WW。
- Windows-only 非核心功能可以在 Mac P0 明确禁用，但状态必须可观察、可测试；不得空实现、吞异常或伪造成功。

## 5. 平台依赖与导入

`pyproject.toml` 是依赖事实来源。

- Windows-only 包必须使用环境 marker 或 Windows extra。
- macOS 只声明实际使用的最小 PyObjC framework wrapper。
- 生成锁文件通过工具重建，不得手改版本集合。
- 单一锁无法跨平台复现时，可增加独立 macOS arm64 lock。
- Windows 生成的 `requirements.txt` 不是 Mac 安装清单。

共享模块顶层不得无条件导入：

- `win32api`、`win32con`、`win32gui`、`win32process`、`winreg`；
- `ctypes.windll` / `ctypes.WinDLL` 实现；
- AppKit、Quartz、ScreenCaptureKit、ApplicationServices 或 PyObjC 实现。

必须先选择平台/provider，再加载具体实现。不得散布宽泛 `try/except ImportError` 掩盖错误边界。

macOS import smoke 必须覆盖 `import ok`、`DeviceManager`、executor、应用入口、全部登记 task、scene、custom tab 和 combat module，且不加载 Win32-only backend。

## 6. 设备能力与任务分级

### 6.1 `DeviceCapabilities`

框架至少区分：

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

要求：

- 新 provider 默认全部 `False`；
- 只有真实实现和安全语义存在时才可声明 `True`；
- inherited empty method、日志 stub 或吞异常不形成能力；
- 任务在 enable 前和真正执行前再次检查要求；
- 缺失能力时在任务逻辑开始前 fail closed，不能运行到中途才发现方法为空；
- `foreground_only=True` 表示每个普通事件或短原子批次前都验证 frontmost；
- `relative_mouse` 专指自由镜头相对/delta，不等于把百分比坐标换算成绝对点击/移动。

### 6.2 任务等级

#### `MAC_BASIC`

用于菜单、登录、领取、背包、强化、合成、固定页面点击及 OCR/模板流程。典型能力为 key tap、绝对点击、左键和前台安全；每个任务仍按真实使用精确声明。

#### `MAC_LOCKED_GAMEPLAY`

用于：

- 持续 W/A/S/D；
- 中键锁敌或视角居中；
- 左右键保持；
- 键鼠组合；
- 根据视觉目标选择 W/A/S/D；
- 不要求任意自由镜头旋转。

#### `MAC_FULL_CAMERA`

用于：

- 任意 relative X/Y；
- 连续 delta；
- 精确路线转向；
- 需要自由镜头的自动寻路。

### 6.3 任务状态与证据状态

任务状态：

- `validated`：对应真机端到端通过；
- `experimental`：能力满足时允许真机验收，但不得描述为稳定支持；
- `unsupported`：不可执行。

底层能力证据另行使用：

1. `not-implemented`；
2. `unit-tested`；
3. `hardware-validated`；
4. `packaged-app-validated`。

这两个轴不得混用。单元测试通过不能把任务标为 `validated`。

### 6.4 relative mouse 不是统一 MVP 阻断项

不得再使用“relative mouse 失败则整个 Mac MVP 不得发布”的绝对规则。

- relative mouse 未通过时，允许发布已通过的 `MAC_BASIC` MVP；
- 允许据实开放已硬件通过的 `MAC_LOCKED_GAMEPLAY` 任务；
- 要求 `relative_mouse=True` 的任务必须在执行前被拒绝；
- 不得声明 `MAC_FULL_CAMERA`、完整路线、完整跑图、完整战斗或 Windows 功能对等。

当前注册任务审计未发现自由镜头 delta 调用；`center_camera()` 是中键中心点击。必须先验证实际依赖，而不是为通用 RelativeMove 推迟基础任务。

## 7. 桌面窗口目标与识别

不得把 `HwndWindow` 扩充成仍以 HWND 字段为中心的伪跨平台对象。

平台中立 target 至少表达：

- PID 与进程存活；
- bundle/application identifier；
- platform window ID；
- 应用名与窗口标题；
- outer frame、content geometry、capture geometry；
- display scale；
- binding/geometry generation；
- frontmost 状态；
- activation request 与观察到的 activation；
- PID/window 重建后的 refresh/rebind。

窗口匹配必须组合：

- 经真实客户端观察的 bundle identifier；
- PID；
- `SCWindow.owningApplication`；
- 标题作为辅助；
- 尺寸和层级过滤；
- 用户手动选择兜底。

不得在观察官方客户端前硬编码猜测 bundle identifier，也不得只靠标题。持久化稳定提示，不持久化旧 PID/window ID。

## 8. 权限与稳定应用身份

必须显式处理：

- Screen Recording / screen capture；
- Accessibility synthetic control。

使用支持的 preflight/request API。缺失或撤销权限时：

- 显示明确状态和设置路径；
- 阻止对应 capture/input capability；
- 不在紧密循环重复请求；
- 不修改 TCC、不请求 root 绕过。

Terminal/Python 权限仅是开发证据。

不得等所有任务完成后才验证打包权限。在 window/permission boundary 建立后，应尽早生成具有稳定 bundle identifier 的内部 `.app`，验证：

- 从 `/Applications` 启动；
- Screen Recording；
- Accessibility；
- 重启后权限持久化；
- 重新打包/升级后的权限行为；
- 撤销权限后的明确错误状态；
- 不从 DMG 内直接运行作为标准路径。

`codesign --sign -` 或其他 ad-hoc 签名不能作为公开发布验收。

## 9. ScreenCaptureKit 持久截图

### 9.1 生产路径

连续自动化必须使用：

```text
SCShareableContent（仅发现或重绑时）
  → selected SCWindow
  → SCContentFilter(desktopIndependentWindow:)
  → SCStreamConfiguration
  → persistent SCStream
  → CMSampleBuffer callback
  → bounded latest-frame publication
  → task thread 按需读取最新帧
```

禁止：

- 每帧重新枚举 `SCShareableContent`；
- 每帧重建 filter/config；
- 每帧调用 `SCScreenshotManager`；
- 全显示器截图后猜坐标裁切作为 production fallback；
- callback 中运行 OCR、模板、YOLO、task 或 Qt 更新。

一次性截图仅允许显式“截图测试”或低频诊断，不得进入 task executor。

### 9.2 输出与存储

每个成功帧必须：

- `numpy.ndarray`；
- `dtype == uint8`；
- `shape == (height, width, 3)`；
- BGR；
- 仅游戏内容区；
- 不含光标、标题栏、阴影、边框或其他桌面内容。

要求：

- `showsCursor = false`；
- 只保留最新完整帧；
- 存储有固定上限；
- 允许覆盖旧帧；
- 慢消费者不能造成队列增长；
- consumer 读取期间底层缓冲不得异步覆盖；
- 每帧绑定不可变 geometry/capture generation。

### 9.3 重绑和失败

必须检测、恢复或进入明确终止状态：

- 游戏退出；
- PID/window ID 变化；
- 窗口重建或全屏切换；
- 尺寸或 display scale 变化；
- Screen Recording 撤销；
- `SCStream` 失败。

重试必须有退避和终止条件。重绑开始后立即使旧帧和旧坐标失效；新 generation 完成前不得继续输入。

### 9.4 诊断指标

至少记录：

- capture FPS；
- latest frame age；
- overwrite/drop count；
- PID/window ID；
- geometry generation；
- stream rebuild/rebind count。

1920×1080 目标配置 30 FPS；稳定低于 20 FPS 时必须分析原因。

## 10. 几何与坐标模型

必须明确区分：

1. macOS 全局逻辑点；
2. `SCWindow.frame` 外框；
3. ScreenCaptureKit 实际帧像素；
4. 游戏内容区；
5. Qt logical coordinate；
6. Retina/display scale；
7. 游戏内部渲染分辨率。

不得直接使用 `SCWindow.frame.width/height` 声称游戏内容像素尺寸或任务分辨率。

- 视觉管线以实际捕获帧尺寸为事实来源；
- 若系统帧含装饰区域，必须可靠裁剪客户区；
- task/识别统一使用帧内物理像素；
- 平台后端负责“帧像素 → 全局逻辑点/CGEvent 坐标”；
- 一次输入使用与当前帧相同 generation 的 geometry snapshot；
- 窗口移动、resize、display 切换、scale 变化或重绑后，旧几何立即失效；
- 不得假设 scale 固定为 2.0。

调试输出必须能同时展示：`SCWindow` 外框、实际帧、内容区、display scale、点击帧坐标、最终 CGEvent 全局坐标和 generation。

## 11. Quartz 前台输入

生产后端使用公开 Quartz/Core Graphics CGEvent，至少支持：

- `send_key`、`send_key_down`、`send_key_up`；
- 左/右/中键 down、up、click；
- mouse button hold；
- 绝对 movement/click；
- scroll；
- `release_all()`；
- 作为单独能力的 relative/delta movement。

macOS keycode 转换集中在后端。task 保持逻辑键名：

```text
w a s d
e q r f t
space shift tab
f2 b 1 2 3
esc enter ...
```

任务文件不得出现 Mac keycode；公共 key map 不得顶层导入 `win32con`；不得把 Windows VK 直接当作 `CGKeyCode`。

## 12. 激活与前台 fail-closed 语义

任务开始时可以：

```text
请求激活游戏
→ 等待
→ 确认游戏实际成为系统 frontmost
→ 开始执行
```

输入后端不得在每次输入前无条件调用激活接口，不得高频抢回用户焦点。

每个普通事件或短原子批次前必须：

1. 验证 target 存在；
2. 验证绑定 PID 存活；
3. 验证目标 app 是系统 frontmost；
4. 验证 input gate 与 geometry generation；
5. 条件全部成立才发布 CGEvent。

失焦或失效时：

1. 不发送待执行普通事件；
2. 立即阻断后续普通输入；
3. 调用 `release_all()`；
4. 暂停或停止当前自动化；
5. 显示明确原因；
6. 要求用户显式恢复或重启，不自动循环抢焦点。

禁止：

- 失焦后继续向全局事件流发送普通输入；
- 无声把输入发给当前其他前台 app；
- 暗中回退到 `CGEvent.postToPid`；
- 激活 API 返回成功后不观察 frontmost 就继续输入。

## 13. `HeldInputState` 与 `release_all()`

必须显式跟踪：

- synthetic held keys；
- synthetic held mouse buttons；
- 当前 owner/batch；
- focus-lost/shutdown/target-lost 状态；
- current geometry generation。

普通输入、focus invalidation、task stop 和 release 必须经过同一线程安全边界。

`release_all()` 必须：

- 幂等、可重复；
- 窗口或进程消失后仍安全；
- 尽最大努力发布所有对应 key-up/mouse-up；
- 单个 release 失败时继续其余 release；
- 无论 posting 是否成功都清空内部 held state；
- 失效后只允许为已记录状态发布 up，不得生成 down、click、movement、scroll 或 text。

必须在以下路径调用：

- 焦点丢失；
- 任务取消；
- executor stop；
- 设备切换；
- 游戏退出；
- fatal capture；
- 权限撤销；
- OK-WW 退出。

长按代码可行时使用 `try/finally`。关闭顺序固定为：阻断新输入 → `release_all()` → 停止 stream/workers → 销毁 Qt/Python 对象。

## 14. 真实输入验证顺序

### 第一优先级：基础输入

- key tap；
- key down/up；
- W/A/S/D 持续移动；
- E/Q/R/F/Space/Shift/Tab；
- 左/右/中键；
- mouse button hold/release；
- 绝对点击；
- scroll。

### 第二优先级：OK-WW 实际组合

- W + 左键；
- W + 技能键；
- W + 中键；
- 中键锁敌或居中；
- 右键保持；
- 方向变化时释放旧方向；
- stop 后所有 held state 清空。

### 第三优先级：自由相对镜头

- relative X/Y；
- 连续 delta；
- 与移动/攻击并发；
- 光标漂移和恢复；
- 游戏锁定鼠标状态。

不得为了先做通用 relative mouse 而推迟基础任务和实际组合验证。

## 15. 任务兼容与执行门控

- `config.py` 登记的每个任务必须有显式 macOS compatibility declaration。
- 未声明任务默认 `unsupported`，不得粗暴按 OS 开启全部。
- capability requirement 必须反映真实调用与子任务编排；组合任务按最宽依赖门控。
- capability 缺失时，UI 应禁用/隐藏或在任务开始前给出明确原因；不得运行到中途才发现空方法。
- `relative_mouse=False` 时，`MAC_BASIC` 和不要求自由镜头的 `MAC_LOCKED_GAMEPLAY` 任务仍可运行。
- 明确要求自由镜头的任务必须声明 `relative_mouse=True` 并在未通过时被阻止。
- 当前 `MouseResetTask` 是 Windows workaround，Mac P0 明确 `unsupported`，除非真机证明确有必要并通过新设计验收。

## 16. 视觉、分辨率与推理

- 保持现有 16:9 task 坐标模型。
- 首个硬件验收为 1920×1080。
- 后续目标：1280×720、1600×900、2560×1440。
- 先修内容区、分辨率、BGR 和 geometry，再运行现有 template/OCR/color/YOLO。
- 只有同分辨率下可重复的 Mac 视觉差异，且通用调整会损害 Windows 时，才增加 `assets/macos`。
- 不得预复制完整 assets tree。
- 初始使用 CPU；`use_npu` 在 macOS 关闭或安全忽略。
- 必须验证 OCR/model wheel 和 native library 的 arm64 兼容性；正确性优先于优化。

## 17. UI、可选功能与进程行为

Mac P0 可以明确禁用：

- Win32 GDI overlay；
- Windows thumbnail；
- Windows global hotkey；
- volume/HDR/Night Light；
- Windows launcher/updater；
- Windows QQ/WeChat desktop automation。

装饰性功能不得阻塞核心自动化。继续复用可跨平台 Qt GUI，不无必要重写。

Windows named mutex、admin/elevation、Explorer helper 不得在 Darwin 执行。Mac MVP 不要求 root。

## 18. 自动化测试与 CI

至少新增/保持：

### 平台导入

- Darwin 不加载任何 `win32*`；
- Windows 不要求 PyObjC；
- 应用入口与全部登记 task/scene/custom tab 可导入。

### capability 与任务兼容

- all-false 默认；
- missing/supports；
- enable/执行前检查；
- 所有登记任务有声明；
- 不满足时不可执行；
- `relative_mouse=False` 不阻断 basic/locked requirement；
- full-camera requirement 被阻止；
- `MouseResetTask` Mac 明确 unsupported。

### 截图与几何

- BGRA→BGR；
- row stride/padding；
- frame ownership；
- latest-frame overwrite；
- bounded storage；
- resize/rebind；
- scale 1.0/2.0/非整数假设；
- 标题栏/内容区裁剪；
- frame pixel→logical/global；
- stale generation rejection。

### 输入状态

- key down/up；
- mouse down/up；
- repeated down；
- release 单点失败；
- `release_all()` 幂等；
- focus loss 拒绝普通输入；
- target exit；
- permission/fatal capture；
- shutdown order。

CI 不安装游戏。macOS Python 3.12 job 做依赖、import 和无游戏测试；现有 Windows job必须保持通过。

## 19. 真机验收门槛

记录：

- Mac 型号/芯片；
- macOS 版本；
- 游戏版本；
- OK-WW/ok-script commit；
- 窗口模式；
- 分辨率；
- display scale；
- 是否外接显示器；
- source 或 packaged identity。

### 19.1 基础 MVP

必须通过：

- 找到/选择正确窗口；
- PID、bundle ID、window ID、外框/内容区/scale 可观测；
- 1920×1080 内容帧；
- 不含标题栏、边框、阴影、光标；
- OCR/模板基础识别；
- key tap；
- key hold/release；
- 左/中/右键；
- 绝对点击；
- focus loss 不泄漏输入；
- 一个 `MAC_BASIC` 任务端到端；
- Windows 测试通过。

### 19.2 `MAC_LOCKED_GAMEPLAY` 声明

仅在以下通过后开放对应任务：

- W/A/S/D 持续输入；
- 方向切换释放；
- W + 左键；
- W + 技能键；
- 中键锁敌或居中；
- 右键保持；
- stop/失焦无卡键；
- 对应代表性任务端到端。

### 19.3 `MAC_FULL_CAMERA` 声明

仅在以下通过后开放：

- relative X/Y；
- continuous delta；
- 与移动/攻击并发；
- 光标状态恢复；
- 对应路线任务端到端。

## 20. 打包与公开分发

- 当前 packaged MVP 的最低系统版本为 macOS 15.0；主程序及全部随包 native library 的真实最低版本均不得高于该声明。缺失或无法解析最低版本的文件必须明确失败，不忽略检查。
- 同时审计 `LSMinimumSystemVersion`、主程序和所有依赖的 Mach-O arm64 slice；不得只修改 plist、deployment flag 或 Mach-O load command 来假装支持 13/14。未来恢复旧系统须按 ADR 0003 重新证明完整依赖与真机/打包兼容性。
- window/permission 边界完成后尽早建立稳定 bundle identifier 的内部 `.app`。
- 内部包验证 arm64 libraries、Qt plugin、OpenCV、OCR/inference、PyObjC、assets/i18n、TCC 和 shutdown。
- 最终 MVP PR 前必须完成 packaged-app permission validation。
- 公开分发另要求 Developer ID Application、Hardened Runtime、timestamp、notarization、staple 和干净用户环境 Gatekeeper 验证。
- 签名/公证凭据不得进入仓库。

## 21. MaaEnd / MaaFramework 参考边界

可以参考其公开实现确认以下路线具有现实可行性：

- 窗口枚举/选择；
- ScreenCaptureKit；
- Quartz key down/up/hold；
- 左/右/中键；
- 固定坐标点击；
- 部分实时视觉辅助。

不得照搬：

- 每次截图重新枚举并使用一次性 API；
- 直接用 `SCWindow.frame` 当内容像素；
- 每次输入前自动激活目标；
- ad-hoc/不稳定 app identity 作为 TCC 验收；
- 后台 controller 作为本分支增加后台支持的理由。

MVP 不引入 MaaFramework binary/dylib。未来引入必须独立 ADR。

## 22. 文档语言与能力声明

所有新增或修改的 macOS 工程约束、实施说明和验收记录默认使用中文。以下保留英文：API、类名、函数名、文件路径、配置键、日志状态码和命令。

文档、UI、README、PR、release note 必须明确：

1. 当前实际支持什么；
2. 哪些 task 已 `validated`；
3. 哪些 task 是 `experimental`；
4. 哪些 task `unsupported`；
5. relative mouse 状态；
6. 中键和持续按键状态；
7. 权限和安装要求；
8. 已知限制；
9. 不支持后台。

不得把未执行的真实游戏或 packaged-app 测试写成“已支持”。

## 23. 最终完成定义

最终 MVP PR 的最小产品范围可以是：

- 基础 MVP 全部通过；
- 至少一个 `MAC_BASIC` 任务端到端；
- focus/release 安全通过；
- Windows 回归通过；
- stable-identity `.app` 权限通过；
- 未通过的任务明确 experimental/unsupported；
- relative mouse 状态如实记录。

若 `MAC_LOCKED_GAMEPLAY` 通过，可增加对应任务声明；若 relative mouse 未通过，不阻断基础 MVP，但不得声称 `MAC_FULL_CAMERA`、完整路线或 Windows 功能对等。

## 24. 禁止的捷径

不得：

- 把 MaaEnd “MacOS-Background” 当作增加后台支持的理由；
- 加入 BetterDisplay、虚拟显示器或 `CGVirtualDisplay`；
- 使用 `CGEvent.postToPid`；
- 注入、Metal hook 或反作弊绕过；
- 用每帧 `SCScreenshotManager` 代替持久流；
- 用 `SCWindow.frame` 直接宣称内容分辨率；
- 每次输入自动抢回焦点；
- 失焦后继续发全局普通输入；
- 用 `pynput`/`pyautogui` 作为 production architecture；
- task 直接导入 AppKit、Quartz 或 Win32；
- 预先复制全部视觉资源；
- 因 relative mouse 未完成而阻断已通过的基础 MVP；
- relative mouse 未完成时宣称完整战斗/路线支持；
- 通过删除或降低安全检查让测试通过；
- 让旧帧/旧几何在 rebind 期间继续驱动输入。
