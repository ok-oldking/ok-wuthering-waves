# OK-WW macOS 前台模式——能力与任务兼容矩阵

## 当前综合矩阵（2026-09-06；取代下方旧矩阵）

本层重新按 source/unit、source/hardware、packaged/hardware 汇总。下方 2026-09-04
表格只保留为历史，不再用于当前支持声明。provider evidence 与 task status 仍是独立轴。

当前 packaged MVP 产品基线为 Apple Silicon、macOS 15+，见 [ADR 0003](decisions/0003-macos-packaged-minimum-version.md) 与 [安装说明](../macos-installation.md)。框架 13+ API 设计与 host gate 保留，不构成当前包支持 13/14 的承诺。此为用户授权的 contributor 分支决定，upstream 尚未接受。

当前冻结的运行时代码基线为 ok-script `91a897071c6013930a9e23452e7b61fd112af310` 与 OK-WW `c03138895323413a98eca4ca59e9434bcba1682f`；构建 provenance 记录两个仓库均 `dirty=false`。对应 Windows/macOS exact-SHA CI 已全部完成并通过。最终内部包安装于 `/Applications/OK-WW.app`，CDHash `6584ba8b8964462ede0aa932113a1c9c8ecfcdd8`，arm64、285 个 native 文件、15.0 最低版本、deep/strict ad-hoc 签名及静态 verifier 均已通过。用户随后确认该最终包手工实测运行正常；这是当前 exact-SHA package 的包级人工 smoke 证据，不自动替代未逐项记录的权限撤销、所有任务端到端、Developer ID/公证或 clean-user Gatekeeper 证据。

精确构建输入以包内 `Contents/Resources/build-provenance.json` 为准，签名后 CDHash 和全部 native minos 以产物旁的 `build-manifest.json` 为准。外部 manifest 不是签名证书；外部 probe 的实际加载 hash 必须逐次记录，不能只靠 CDHash 归因。旧测试没有 probe hash 的，明确保留为未记录。

| 能力/ID | source/unit | source/hardware | packaged/hardware | 当前下一门槛 |
|---|---|---|---|---|
| 安装、导入、声明 CAP-01～09 | exact-SHA unit-tested | 原生 GUI 已运行 | exact-SHA 独立包由用户手工 smoke 正常 | 最终 upstream 接受后的不可变 ok-script 依赖 |
| 主窗口绑定/前台 CAP-10～15/50 | unit-tested | 官方游戏绑定、W 失焦已有详细历史证据 | 最终 exact-SHA 包整体手工运行正常；未按单项重新拆录 | 如 reviewer 要求，再补窄范围逐项记录 |
| 权限 CAP-16/17/73/74 | unit-tested | 两权限授权输入/捕获有历史证据 | same-build 重启保持有正面证据；cross-ad-hoc-rebuild 已观察不保持；最终包整体 smoke 正常 | 权限撤销未逐项确认；稳定签名跨构建留公开发行阶段 |
| 内部 .app CAP-18/72 | unit-tested | 不适用 | exact-SHA arm64 `/Applications` 包静态验证通过，用户手工运行正常 | upstream/release identity 协调；非公开发行证据 |
| persistent capture/BGR/content-only CAP-20～23/27 | unit-tested | 1920×1080/1000 帧；1280×800 原生 16:10 有详细历史证据 | 最终 exact-SHA 包整体手工运行正常 | 保留历史详细帧证据，不由总体 smoke 补猜逐项数值 |
| lifecycle/geometry CAP-24～26/28 | unit-tested | move/resize/scale、旧 generation 拒绝有详细证据 | 最终 exact-SHA 包整体手工运行正常 | reviewer 如要求再做特定窗口重建复现 |
| heartbeat 新鲜帧门槛 | unit-tested | 未单独真机制造 stall | 未单独制造 stall | 仍以 2 秒 heartbeat fail-closed 契约和自动化为证据，不从正常 smoke 推断故障注入通过 |
| key/button/absolute/scroll CAP-30～34/40/42 | unit-tested | tap/hold、WASD、三鼠标键、组合和滚轮已有实际输入证据 | 最终 exact-SHA 包整体手工运行正常 | 未逐 task 拆分的功能继续按 task status 声明 |
| guard/release/shutdown CAP-35～39/75 | unit-tested | W 失焦释放、失焦拒绝输入、stop/capture-close 有详细历史证据 | 最终 exact-SHA 包整体手工运行正常 | 未单独记录的新故障注入场景不补猜 |
| 相对自由镜头 CAP-41/63 | not-implemented | 未验证 | 未验证 | 独立 MAC_FULL_CAMERA gate；不阻塞基础 MVP |
| 热键/任务平台化 CAP-51～54 | unit-tested | 自定义 Y 指南已有证据 | 最终包整体 smoke 正常 | 其他用户自定义键位仍按配置确认 |
| 打开截图目录 CAP-55 | unit-tested | 未单独真机复验 | 未单独复验 | 两正式 task 已使用框架 open_path，不直接 OS API |
| CPU OCR/model CAP-56/57 | unit-tested | 已识别实景 | exact-SHA package 静态/构建自检基础已通过，用户整体 smoke 正常 | 不由总体 smoke 补猜具体 OCR 性能指标 |
| UI 声明 CAP-58/64 | unit-tested | 部分 GUI 观察 | 最终 exact-SHA 包整体手工运行正常 | task 状态仍按逐项证据维护 |
| CI/公开发行 CAP-70/71/76 | exact-SHA 本地回归通过 | 不适用 | Developer ID、公证、staple、Gatekeeper clean-user 未验证 | exact-SHA CI 已全绿；公开发行门槛仍后置 |
| 系统最低版本 | packaged MVP/verifier 为 15.0；框架 host gate 13+ | 当前主机不证明 13/14 | exact-SHA 包主程序及 285 native 已按 15.0 hard gate 验证 | macOS 13/14 不在当前 packaged MVP 范围 |

### 当前任务结论

- 用户已确认最终 exact-SHA package 手工实测运行正常；由于本次确认没有按每个 task 单独列出步骤/结果，任务 registry 不据此批量升级。
- AutoPick：source 地面拾取端到端与 packaged 历史前后画面已有证据；当前代码声明仍为 `experimental`，除非在 PR 沟通中决定用既有逐项证据正式升级，否则保持保守声明。
- AutoLogin：已登录状态识别；不是从退出状态完整登录的证据。
- AutoCombat：基本战斗、攻击、切人和停止释放已有 source/部分 packaged 证据；
  不是所有角色循环或完整正式任务稳定闭环。
- Tacet/NightmareNest/Daily：仍 `experimental`。导航单元分支已覆盖，旧 guide-entry 不能替代
  正式 BaseWWTask/helper/参数/provider/executor/capability 全路径；完整 Daily 暂不作首个入口。
- Merge/Enhance/Change/AutoDialog/FastTravel/FarmEcho/Forgery/Simulation/MultiAccountDaily/Garden：
  均 `experimental`，未执行的消费、传送、对话等不能标为通过。
- MouseResetTask：`unsupported`。未登记任务 fail closed。relative mouse 不是 basic/locked 阻塞项。

### 证据定位与版本边界

详细历史见 `macos-internal-acceptance.md` 的各时间戳与 CDHash；其中早期 CURRENT INTERNAL BUILD 标题仅指该节当时状态。当前最终 exact-SHA 包为 ok-script `91a897071c6013930a9e23452e7b61fd112af310`、OK-WW `c03138895323413a98eca4ca59e9434bcba1682f`、CDHash `6584ba8b8964462ede0aa932113a1c9c8ecfcdd8`，构建 provenance 为 clean source，用户已确认整体手工实测正常。更早 16:9 guide-entry、16:10 AutoPick 等详细证据继续保留各自时间线/CDHash；没有记录的 SHA、dirty fingerprint、probe hash 或逐项故障注入结果不补猜。本矩阵仍不等于 Developer ID/notarization/公开发行就绪声明。

---

## 历史矩阵（2026-09-04，已被上方综合矩阵取代）


记录日期：2026-09-04

适用分支：`feature/macos-foreground-mvp`

状态：阶段 A/B/C 的本地与远端无游戏 gate 已通过；阶段 D 的 persistent `SCStream`、actual `1920×1080` content-only frame、1000 帧、frame ownership、move/resize lifecycle 与 geometry contract 已在 `ok-script` 提交 `ee3c63d82a36a5b1867b54483f3a2cfda4f40f84` 通过本地自动化和 source-identity 硬件验证。Stage D 远端 runner 与 packaged `.app` 仍待验收；当前没有任务达到 `validated`。

## 1. 两个独立状态轴

### 1.1 provider capability evidence

仅使用：

1. `not-implemented`：没有可执行实现，或实现尚未满足最低单元契约；
2. `unit-tested`：无游戏环境中的确定性接口/状态/导入测试通过；
3. `hardware-validated`：在官方《鸣潮》Mac 客户端和真实硬件上通过；
4. `packaged-app-validated`：在稳定 bundle identifier 的内部 `.app` 身份下通过。

单元测试不能替代真实窗口、TCC 或游戏输入证据。相关架构、依赖、系统或 packaged identity 变化会重新打开 gate。

### 1.2 task support status

- `validated`：该任务在相应能力等级下真机端到端通过；
- `experimental`：可以在底层 capability 满足后进行真机验收，但不得对用户描述为稳定支持；
- `unsupported`：不可在当前 Mac MVP 执行。

任务状态不等于 provider evidence。当前没有任务达到 `validated`。

## 2. 精确设备能力

`ok-script` 的 `DeviceCapabilities` 包含：

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

所有字段默认 `False`。任务在 enable 前和真正执行前检查要求；未实现后端或空方法不会自动形成能力。

`relative_mouse` 专指自由镜头相对/delta 输入，不等于任务层把百分比坐标换算为绝对坐标的 `move_relative` helper。

## 3. 任务能力等级

| 等级 | 定义 | relative mouse 是否必需 |
|---|---|---|
| `MAC_BASIC` | 菜单、登录、领取、合成、背包、强化、固定页面 OCR/模板、绝对点击 | 否 |
| `MAC_LOCKED_GAMEPLAY` | 持续 W/A/S/D、中键锁敌/居中、左右键保持、键鼠组合和视觉方向选择 | 否 |
| `MAC_FULL_CAMERA` | 任意 relative X/Y、连续 delta、精确路线转向和自由镜头寻路 | 是 |

relative mouse 缺失只阻止 `MAC_FULL_CAMERA` 和明确声明该字段的任务，不阻止已通过的 basic/locked task。

## 4. 框架安装与导入

| ID | 能力 | Owner | 当前证据 | 已有证据 | 下一门槛 |
|---|---|---|---|---|---|
| CAP-01 | arm64 macOS 正常 dependency resolution，不选择 Windows-only distribution | `ok-script` | `unit-tested` | sibling editable install 和 `pip check` 在参考 Mac 环境成功；metadata marker tests 通过 | Windows/macOS CI 重跑及最终 immutable dependency |
| CAP-02 | 确定性 PEP 517/editable build | `ok-script` | `unit-tested` | 普通 build/editable 不再依赖未声明 import 或默认 PyPI 版本查询；package metadata tests 通过 | clean CI build 和最终 release version 流程 |
| CAP-03 | 从安装环境 `import ok` | `ok-script` | `unit-tested` | 从临时工作目录导入测试通过 | macOS CI |
| CAP-04 | `DeviceManager` / executor / shared capture/interaction 导入不加载 Win32 | `ok-script` | `unit-tested` | `tests/test_platform_imports.py` 与完整 framework suite 通过 | macOS CI |
| CAP-05 | Qt app/start/debug/notification optional modules 在 Darwin 可导入 | `ok-script` | `unit-tested` | headless/offscreen import contracts 通过 | native WindowServer UI smoke 与 packaged app |
| CAP-06 | 所有登记 OK-WW entry/task/scene/custom tab 在 Darwin 可导入 | both | `unit-tested` | `tests/test_macos_imports.py` 通过，无 forbidden module | macOS CI |
| CAP-07 | Windows provider 行为在平台拆分后保持 | `ok-script` | `unit-tested` | Stage C `ok-script` Windows run `33865913439` 通过；新增 HWND adapter 另有 fake contract tests | Stage D 提交后的 Windows runner 重跑 |
| CAP-08 | `DeviceCapabilities` 默认 fail-closed、matching 和 task preflight | `ok-script` | `unit-tested` | `tests/test_device_capabilities.py` 通过；enable/execute 前检查 | 在真实 Mac provider 接入后重跑 |
| CAP-09 | 所有登记 OK-WW task 有明确 Mac declaration | OK-WW | `unit-tested` | `tests/test_macos_capabilities.py` 检查 17/17 覆盖 | 真实 capability 与 task end-to-end |

## 5. Desktop target、窗口与权限

| ID | 能力 | 当前证据 | 已有证据 | 下一门槛 |
|---|---|---|---|---|
| CAP-10 | 平台中立 `DesktopWindowTarget` contract | `unit-tested` | immutable snapshot、明确 coordinate-space、丢失清空与 generation contract tests | Stage D frame/geometry integration |
| CAP-11 | 现有 HWND 行为通过 Windows adapter | `unit-tested` | composition fake `HwndWindow` adapter tests；未改 Windows capture/input 主路径 | Stage C 提交后的 Windows unit/CI regression |
| CAP-12 | 枚举官方 Mac app/window candidates | `hardware-validated` | 官方客户端实测为 `鸣潮` / `com.kurogame.mingchao`，PID/window ID 与 outer geometry 可枚举并绑定 | packaged `.app` identity 与 window recreation |
| CAP-13 | PID/bundle/window binding、manual selection 与 refresh/rebind | `unit-tested` | fake adapter 覆盖稳定 hint、歧义手选、PID/window replacement、bind 前二次枚举/liveness recheck、刷新期/异常 fail closed | 官方客户端 process/window recreation hardware test |
| CAP-14 | 观察系统 frontmost 状态 | `unit-tested` | fake adapter 覆盖实时 frontmost 观察；不使用枚举时的旧快照代替观察 | Command-Tab hardware observation |
| CAP-15 | request activation 后确认 observed activation | `unit-tested` | contract tests 证明 request accepted 不等于 observed frontmost | real-game hardware validation |
| CAP-16 | Screen Recording permission status/request/revoke | `unit-tested` | public API mapping 与 required/requested/granted/revoked/error 状态机 fake tests；并发请求串行化且 requested 后禁止重复请求 | source identity hardware + stable `.app` TCC |
| CAP-17 | Accessibility permission status/request/revoke | `unit-tested` | public API mapping 与 required/requested/granted/revoked/error 状态机 fake tests；并发请求串行化且 requested 后禁止重复请求 | source identity hardware + stable `.app` TCC |
| CAP-18 | 稳定 bundle identifier 的早期内部 `.app` identity checkpoint | `not-implemented` | 尚未生成或安装稳定 identity 的内部 `.app` | 阶段 C 后从 `/Applications` 验证 permission persistence |

## 6. Capture 与 geometry

| ID | 能力 | 当前证据 | 已有证据 | 下一门槛 |
|---|---|---|---|---|
| CAP-20 | selected-window persistent `SCStream` | `hardware-validated` | 官方客户端窗口模式 persistent stream 完成 1000 unique frames，约 29.36 FPS，无 stall | resize/display/window recreation hardware test |
| CAP-21 | BGR `uint8` `(height,width,3)` frame | `hardware-validated` | synthetic conversion tests 加官方客户端 actual `1920×1080×3` BGR frame 与 color 视觉检查；逻辑客户区 `960×540`、Retina scale 2.0 | 离线 recognition suite |
| CAP-22 | content-only frame，无 cursor/title/border/shadow | `hardware-validated` | AX/AppKit 识别 `960×568` 标准窗口中的顶部 28-point chrome，`sourceRect` 输出 actual `1920×1080`；视觉检查无 cursor/title/border/shadow | packaged identity；全屏/无边框不在窗口模式验收内并 fail closed |
| CAP-23 | bounded latest-frame publication 与 ownership | `hardware-validated` | 最终 1000 unique frames 中 received/published 1001、storage size 1、incomplete/stale/conversion error 0；另有 ownership/overwrite tests | 更长时段 leak observation 与 packaged app |
| CAP-24 | stream/window recreation 与 bounded rebind | `hardware-validated` | 临时标准 AppKit 窗口 move/resize 两次触发旧帧失效与 stream rebuild，target generation `1→2→3`；另有 target loss、permission revoke、unexpected stop、stop timeout fail-closed tests | 官方客户端 display/window/PID recreation hardware test |
| CAP-25 | immutable geometry generation 与 stale-frame rejection | `hardware-validated` | `SCStreamFrameInfoScreenRect` 驱动 move/resize geometry invalidation；临时窗口验证新 generation 恢复到正确位置/尺寸，另有 callback race tests | macOS 13.0 move fallback 与官方客户端 rebind |
| CAP-26 | frame pixel → global logical/CGEvent coordinate | `unit-tested` | scale 1.0/2.0/1.5、offset、crop、positive Mac logical geometry tests | actual game four-corner coordinate hardware validation |
| CAP-27 | 1920×1080 1000+ continuous frames | `hardware-validated` | 官方客户端窗口模式 actual `1920×1080×3` 完成 1000 unique frames，34.295 s、约 29.24 FPS，单槽且无 stall/error；逻辑客户区为 `960×540`、Retina scale 2.0 | packaged `.app` 与更长时段 leak observation |
| CAP-28 | 同时诊断 outer frame、actual frame、content、scale 和 posted coordinate | `unit-tested` | diagnostics 提供 FPS、frame age、overwrite/drop、target/capture generation、geometry、invalidation 与 rebuild；fake Quartz sink 已验证 frame pixel → global point | actual game posted-coordinate trace |

## 7. Foreground input 与安全

| ID | 能力 | 当前证据 | 下一门槛 |
|---|---|---|---|
| CAP-30 | Quartz key tap | `unit-tested` | public Quartz event sink + fake sink tap/down-time/release tests | official game key tap hardware |
| CAP-31 | Quartz key down/up/hold | `unit-tested` | duplicate-down、matching-up、held-state 与 watchdog release tests | W/A/S/D hardware |
| CAP-32 | left/right/middle down/up/click | `unit-tested` | absolute move、三键 down/up/click、cursor-query failure release tests | official game hardware |
| CAP-33 | absolute mouse coordinate mapping | `unit-tested` | frame-local physical pixel → global logical point fake sink tests | actual game four-corner hardware |
| CAP-34 | scroll | `unit-tested` | guarded Quartz scroll fake sink tests | task hardware |
| CAP-35 | `HeldInputState` keys/buttons/owner/invalidation | `unit-tested` | shared `RLock`、owner/generation、snapshot、clear 与 duplicate state tests | concurrent real-input observation |
| CAP-36 | idempotent best-effort `release_all()` | `unit-tested` | partial release failure 继续释放、总是清 state、重复调用 tests | vanished-target 与 hardware release observation |
| CAP-37 | `ForegroundGuard` immediately before ordinary event/batch | `unit-tested` | target/PID、双权限、frontmost、capture state 与双 generation gate tests | Command-Tab hardware |
| CAP-38 | invalidation 后无 ordinary event，只允许 matching release | `unit-tested` | ordinary event failure closes gate；watchdog/ExitEvent 同步 release；后续 ordinary event 被拒绝 | hardware leak test |
| CAP-39 | task/capture/permission/device/app shutdown release ordering | `unit-tested` | capture invalidation callback、executor pause/stop、ExitEvent binding、DeviceManager close/start lifecycle lock tests | packaged app |
| CAP-40 | platform-neutral CursorService seam | `unit-tested` | Windows/unavailable seam 保持；Mac 使用绑定同一 foreground gate 的 Quartz cursor service | hardware cursor query/move |
| CAP-41 | relative/delta mouse X/Y | `not-implemented` | 阶段 F 第三优先级 hardware；只阻止 full-camera claims |
| CAP-42 | W/A/S/D + left/skill/middle/right-hold combinations | `not-implemented` | 阶段 F official-game matrix；通过后可开放 locked tasks |

## 8. OK-WW integration 与 recognition

| ID | 能力 | 当前证据 | 下一门槛 |
|---|---|---|---|
| CAP-50 | 真实 Mac game matching config | `hardware-validated` | 官方客户端实测 `com.kurogame.mingchao` / `鸣潮` 并写入独立 `macos` hints | 地区/语言变体与 packaged app 验证 |
| CAP-51 | Mac logical key set / game hotkeys | `unit-tested` | public HIToolbox `kVK_*` map 覆盖现有 OK-WW task hotkeys 并通过 map tests | official-client key validation |
| CAP-52 | `CombatCheck` 不直接调用 Win32，使用 framework cursor seam | `unit-tested` | import/unit tests 通过；Mac Quartz cursor service 已绑定 foreground gate | hardware |
| CAP-53 | `MouseResetTask` Mac P0 显式 unsupported | `unit-tested` | capability declaration/preflight test | UI 文案和 packaged behavior |
| CAP-54 | task 不依赖具体 `PostMessageInteraction` 类型 | `unit-tested` | existing task regression/import tests | Windows CI |
| CAP-55 | cross-platform screenshot-folder open/reveal | `not-implemented` | platform service + task tests |
| CAP-56 | CPU OCR/inference arm64，NPU disabled/ignored | `not-implemented` | model load/correctness/performance tests |
| CAP-57 | existing template/OCR on normalized Mac frame | `not-implemented` | offline real-frame suite |
| CAP-58 | UI 显示 task status / missing capabilities，并阻止新 enable | `unit-tested` | framework `TaskCard` status-code badge tests 通过；Windows compatible task 不显示额外 badge | 阶段 G 补 level/本地化说明并做真实 provider UI 验收 |

## 9. Task compatibility

下表是当前代码审计后的**候选验收范围**，不是用户支持声明。

| Task | Level | Required capability 摘要 | 当前状态 | 下一证据 |
|---|---|---|---|---|
| `MergeEchoTask` | `MAC_BASIC` | key tap、absolute mouse、left、foreground-only | `experimental` | normalized frame + end-to-end |
| `EnhanceEchoTask` | `MAC_BASIC` | key tap、absolute mouse、left、foreground-only | `experimental` | end-to-end |
| `ChangeEchoTask` | `MAC_BASIC` | key tap、absolute mouse、left、foreground-only | `experimental` | end-to-end |
| `AutoLoginTask` | `MAC_BASIC` | absolute mouse、left、foreground-only | `experimental` | login/notice hardware |
| `AutoPickTask` | `MAC_BASIC` | key tap、scroll、foreground-only | `experimental` | F-key/候选滚动 trigger hardware |
| `AutoDialogTask` | `MAC_BASIC` | absolute mouse、left、foreground-only | `experimental` | dialog hardware |
| `FastTravelTask` | `MAC_BASIC` | absolute mouse、left、foreground-only | `experimental` | fast-travel hardware |
| `AutoCombatTask` | `MAC_LOCKED_GAMEPLAY` | key tap/hold、absolute、left/middle、button hold、foreground-only | `experimental` | locked input matrix + representative combat |
| `FarmEchoTask` | `MAC_LOCKED_GAMEPLAY` | locked baseline + right + scroll | `experimental` | movement/combat/pickup end-to-end |
| `NightmareNestTask` | `MAC_LOCKED_GAMEPLAY` | locked baseline + scroll | `experimental` | end-to-end |
| `TacetTask` | `MAC_LOCKED_GAMEPLAY` | locked baseline + scroll | `experimental` | end-to-end |
| `ForgeryTask` | `MAC_LOCKED_GAMEPLAY` | locked baseline + scroll | `experimental` | end-to-end |
| `SimulationTask` | `MAC_LOCKED_GAMEPLAY` | locked baseline + scroll | `experimental` | end-to-end |
| `DailyTask` | `MAC_LOCKED_GAMEPLAY` | 编排子任务，按最宽依赖 | `experimental` | constituent tasks + end-to-end |
| `MultiAccountDailyTask` | `MAC_LOCKED_GAMEPLAY` | 编排 DailyTask，按最宽依赖 | `experimental` | account flow + end-to-end |
| `GardenTask` | `MAC_LOCKED_GAMEPLAY` | key tap/hold、absolute、left、foreground-only | `experimental` | end-to-end |
| `MouseResetTask` | — | Windows workaround | `unsupported` | 只有真机证明确有必要才重新设计 |

当前没有登记任务要求 `MAC_FULL_CAMERA` 或 `relative_mouse=True`。未来任务如调用自由镜头 delta，必须显式升级 requirement，并在 CAP-41 硬件通过前被拒绝。

## 10. 端到端与发布声明

| ID | 能力 | 当前证据 | 下一门槛 |
|---|---|---|---|
| CAP-60 | 一个 `MAC_BASIC` task end-to-end | `not-implemented` | 阶段 G real game |
| CAP-61 | Auto Pick 或其他 key-tap trigger end-to-end | `not-implemented` | CAP-30/37 后 hardware |
| CAP-62 | 一个 `MAC_LOCKED_GAMEPLAY` representative flow | `not-implemented` | CAP-31/32/36/37/42 hardware |
| CAP-63 | `MAC_FULL_CAMERA` route flow | `not-implemented` | CAP-41 hardware + route end-to-end |
| CAP-64 | 当前全部 task 兼容矩阵与 UI 一致 | `not-implemented` | 阶段 G automated + hardware evidence |

CAP-41 未通过时不阻止 CAP-60，也不阻止已经通过的 CAP-62；但 CAP-63 与 full-camera/complete-route claims 保持关闭。

## 11. CI、packaging 与公开发布

| ID | 能力 | 当前证据 | 下一门槛 |
|---|---|---|---|
| CAP-70 | macOS Python 3.12 no-game branch CI | `unit-tested` | Stage C `ok-script` run `33865913507` 与 OK-WW guardrail run `33865949644` 通过 | Stage D 提交后的远端绿色 |
| CAP-71 | Windows branch regression CI | `unit-tested` | Stage C `ok-script` run `33865913439`、OK-WW legacy run `33865949610` 与 guardrail run `33865949644` 通过 | Stage D 提交后的两仓库 Windows runner 绿色 |
| CAP-72 | stable bundle-ID arm64 internal `.app` launch | `not-implemented` | 阶段 C/H internal package |
| CAP-73 | packaged Screen Recording permission/persistence/revoke | `not-implemented` | `/Applications` identity validation |
| CAP-74 | packaged Accessibility/input/focus safety | `not-implemented` | stable identity hardware |
| CAP-75 | packaged shutdown releases input/capture | `not-implemented` | lifecycle hardware |
| CAP-76 | Developer ID + Hardened Runtime + timestamp + notarization + staple | `not-implemented` | public-release gate；凭据不入库 |

## 12. 当前声明边界

截至本记录：

- 可声明平台安全安装/导入、capability/task declaration、Stage C target/permission contract、Stage D capture/lifecycle/geometry，以及 Stage E Quartz foreground input/fail-closed contract 已通过本地自动化；
- 已在 source identity 下发现并捕获官方客户端窗口，完成窗口模式 1920×1080 content-only BGR 与 1000 unique frames；
- Quartz input 生产实现已存在并达到 `unit-tested`，但安全 smoke 只创建事件对象、没有调用 `CGEventPost`，不得声明真实游戏输入有效；
- macOS 13.0 同尺寸窗口移动 fallback 尚未闭合，因此在该基线问题解决前不得开始真实输入验收；
- packaged `.app`、Accessibility 实际授权/撤销、稳定 bundle identity 与 shutdown release 尚未验收；
- 不可声明中键、持续按键、locked gameplay 或 relative mouse 在游戏中有效；
- 所有候选任务仍为 `experimental`，`MouseResetTask` 为 `unsupported`；
- 不支持后台；
- Stage C Windows 行为已有远端 runner 证据；Stage D/E 均只有本地回归，未推送、未触发远端 CI；
- README、UI、PR 和 release note 必须采用上述较低状态。
