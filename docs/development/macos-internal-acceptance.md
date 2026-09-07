# macOS 内部包验收（2026-09-05，进行中）

## 当前产品基线与证据边界（2026-09-06）

用户已授权 contributor 集成分支按 [ADR 0003](decisions/0003-macos-packaged-minimum-version.md) 将当前 packaged MVP 收窄为 Apple Silicon、macOS 15+；13/14 不在本次包支持范围。框架公开 API 设计与通用 host gate 保留 13+。这不代表 upstream 接受，也不表示本轮新提交已完成 packaged 或真实游戏验收。安装说明见 [macOS 内部版安装与使用](../macos-installation.md)。

已有 manifest 对 285 个 native 文件的 minos 分布为 11.0×109、13.0×99、14.0×13、15.0×64；主程序/Python/PySide6 wrapper 15.0 决定整包下限，不能用 Qt 原生库或 OpenVINO 较低的 minos 推断整包支持 13/14。构建、plist 和 all-native 验证应保持 15.0 一致，禁止伪改标记。

下方按时间记录的“当前安装”“CURRENT INTERNAL BUILD”“最新源码”和“当前结论”均指各节当时的产物与工作树，历史原始证据继续保留。早期“产品 13+ 目标不变”已由 ADR 0003 取代。当前 exact-SHA Windows/macOS CI 已全部通过；最终 clean-source 内部包也已重建、安装，并由用户确认手工实测运行正常。仍须把这种总体 package smoke 与逐项权限撤销、故障注入、每个 task 端到端及公开签名/公证证据分开，不能用总体“正常”补填未逐项记录的 gate。

## 最终 exact-SHA 内部包人工复验（2026-09-06）

- 运行时代码：ok-script `91a897071c6013930a9e23452e7b61fd112af310`；OK-WW `c03138895323413a98eca4ca59e9434bcba1682f`。构建 provenance 记录两个仓库均 `dirty=false`。
- 安装包：`/Applications/OK-WW.app`；bundle ID `org.okww.foreground.internal`；CDHash `6584ba8b8964462ede0aa932113a1c9c8ecfcdd8`；Apple Silicon arm64；packaged MVP 最低 macOS 15.0。
- 静态构建门槛：285 个 native 文件、最低系统版本、deep/strict ad-hoc 签名、资源/图标/翻译和禁止文件/个人路径扫描均已通过；对应 manifest 与包内 provenance 一致。
- 自动化：ok-script exact HEAD 的 macOS/Windows CI 均 success；OK-WW exact HEAD 的 macOS/Windows guardrail 与主 Windows legacy workflow 均 success。详细 run ID 见规划目录 `macos-closeout-2026-09-06.md`。
- 用户随后确认该最终 package 已完成手工实测且运行正常。该确认作为**最终 exact-SHA 包级人工 smoke 通过**记录，用于关闭“最终 clean-source 包是否能正常运行”的总体门槛。
- 本次确认没有逐项给出权限 revoke/regrant、人工制造 capture stall、每个 experimental task 的独立端到端步骤或 Developer ID/notarization/Gatekeeper clean-user 结果，因此这些项目仍保持各自原有状态；任务 registry 不因总体 smoke 批量升级。
- ad-hoc 包不构成公开发行签名证据；当前下一阶段转为与维护者确认两个协调 PR 的提交方式、`ok-script` 最终不可变依赖身份及 reviewer 希望保留/补充的验收材料。

## 当前安装：任务自动连接包（2026-09-06 19:35）

- 已安装 `/Applications/OK-WW.app`，CDHash `0789ffb7203f39ebba9c1111ff752853d291651e`。
  arm64、图标、285 原生依赖、deep/strict 签名通过，bundle ID 和 ad-hoc 方式不变。
- 旧包通过关闭窗口正常退出，确认进程退出后备份至
  `build/macos-rollback-autoconnect.DW8FJu/installed-original.app`。用户数据未修改。
- 包含连接成功立即更新任务卡、Mac 一次性任务点击可自动连接；unsupported 和执行前
  能力/前台/新鲜帧门禁保持。框架自动化 694 passed、12 skipped、4 subtests passed。
- 安装路径无输入自检退出码 0：Qt cocoa、OpenCV、OpenVINO CPU/NPU 关闭、OCR、
  Echo 640 通过，input_posts=0。自动连接与倒计时新版真机待用户验证，未启动游戏任务。
- Windows deferred / 未验证；16:10 暂缓；权限撤销取消；Developer ID/公证/staple/
  Gatekeeper clean-user 未验证，不宣称完整内部包或公开发布通过。

## 当前安装：OK-WW 命名与 UI 整理包（2026-09-06 18:55）

- 已安装 `/Applications/OK-WW.app`，CDHash `a80b45cec81f7ab8b365b4a4076ba3fb7789841f`。
  bundle ID 与 ad-hoc 签名方式不变，macOS 最低 15.0；旧包正常退出后移至
  `build/macos-rollback-ui.OGgFE4/installed-original.app`，原用户数据目录保持不变。
- PNG 自动转换缺少 imageio，因此采用系统 sips/iconutil 生成 ICNS，无新增依赖；
  图标资源、arm64、285 原生依赖、deep/strict 签名和安装路径无输入自检通过。
- GUI 实际打开，标题/菜单显示 OK-WW 与 0.1.0 内部版；窗口图标、汉化权限面板及 Fluent
  控件实际观察正常，未运行游戏任务。技术 API 名仍保留，其他页面的细节统一可后续继续。
- 本次重建后两权限显示未授权或不可用，需要用户重新授权；没有自动更改权限。
  新倒计时真机仍待授权后验证，自动化只证明实际秒数和不重复 show/activate 的路由。
- Windows deferred / 未验证，16:10 暂缓，撤权取消，Developer ID/公证/staple/
  Gatekeeper clean-user 未验证。内部 UI 整理不代表最终上游或公开发行就绪。

## UI 与命名整理（最新源码）

- 应用显示名统一为 OK-WW，运行时版本为 0.1.0 内部版，不再显示 dev；bundle ID
  仍为 org.okww.foreground.internal，ad-hoc 签名方式不变，不升级公开发布声明。
- Nuitka 配置项目已有 PNG 为应用图标，构建阶段检查 CFBundleIconFile 指向实际资源。
- 倒计时分为等待游戏置前、每任务准备两个阶段；采用 controller 单调时钟真实剩余秒数，
  同一遮罩原地刷新，不在阶段转换或每秒更新时重复 show/activate。失焦与最终输入检查不变。
- Mac 权限面板采用与其他页面一致的 Fluent 字体、按钮与下拉框；权限/窗口文案汉化。
  准备时间沿用稳定英文配置键，五种现有语言目录新增翻译并编译，无重置用户设置。
- 自动化：框架 686 passed、12 skipped、4 subtests passed；游戏相关 147 passed；
  五种 gettext 目录检查与编译通过。真实新版 UI、TCC 和游戏任务证据须另行记录。

## 当前安装：截图连接合一包（2026-09-06 18:30）

- 产物已重建并安装至 `/Applications/OK-WW Foreground Internal.app`，CDHash
  `8ee597cee668e78fc85d1e69211d2d7bc17f23fe`。arm64、285 原生依赖、稳定 bundle ID、
  macOS 15.0 内部基线、ad-hoc 签名与 deep/strict 校验通过。
- 旧包通过 GUI 关闭退出，没有强杀；替换前确认无安装路径进程。旧包保存在
  `build/macos-rollback-connect.fcxgMy/installed-original.app`，配置与日志不变。
- 新版截图页隐藏执行器“开始”入口；“绑定并连接截图”一次完成绑定、provider 准备及
  新鲜截图就绪，不经过 30 秒前台交接或任务准备倒计时。截图就绪检查 8 秒为失败上限。
- 安装路径无输入自检退出码 0：Qt cocoa、OpenCV、OpenVINO CPU/NPU 关闭、OCR、
  Echo 640 通过，`input_posts=0`。框架自动化 684 passed、12 skipped、4 subtests passed。
- 此轮未运行游戏任务，新版连接真实行为及 TCC 待验。Windows deferred / 未验证；
  16:10 暂缓；权限撤销取消；公开签名、公证及 Gatekeeper clean-user 未验证。

## 当前安装：每任务准备时间包（2026-09-06 18:20）

- 用户确认退出且无 macos_main 进程后安装至 `/Applications/OK-WW Foreground Internal.app`。
  CDHash `ae5231c8bedcbf032c6dc67a1b3cae2e7f67ed7c`，bundle ID 保持不变。
- 旧包及外置 `macos_internal_probe.py` 已移至
  `build/macos-rollback-preparation.BLCYfP/`，分别为 `installed-original.app` 和原脚本名。
  短验收入口已移出加载目录，配置、截图、日志未删除。需回滚时先退出 App，再恢复对应备份。
- 安装后 deep/strict 签名校验通过；安装路径 `--self-check` 退出码 0：arm64、Qt cocoa、
  OpenCV 5、OpenVINO CPU（NPU 关闭）、空图 OCR、Echo 640 模型通过，`input_posts=0`。
  自检退出后无 macos_main 残留进程。未自动启动正式 GUI 或游戏任务。
- 新包 TCC、任务配置界面及准备时间真实行为待用户验证。ad-hoc 重建可能需要重新授权；
  不把旧包权限保持证据升级为本包证据。其他未验证边界不变。

## 新产物：每任务准备时间（2026-09-06，已构建，尚未安装）

- 本地 Nuitka/PySide 构建成功，产物 `build/macos-internal/macos_main.app`；
  provenance 与签名后 manifest 位于原有标准位置。编译前后源码指纹一致。
- 静态检查通过：arm64、285 个原生依赖、稳定 bundle ID
  `org.okww.foreground.internal`、内部最低 macOS 15.0、ad-hoc 签名。
- 包含每任务 `Preparation Seconds` 默认 8 秒（0–300）、置前后计时、切走取消、
  启动失败回滚、无主动激活、Mac schtasks 隔离和任务技术标签隐藏。
- 构建前自动化：框架 683 passed、12 skipped、4 subtests passed；游戏 Mac 相关 147 passed。
- 旧安装包仍在运行，因此尚未安装或执行新包自检/真机测试；外置短验收脚本仍待旧包退出后
  移出加载目录并备份。静态构建通过不升级 packaged 真机验收状态。
- Windows deferred / 未验证；16:10 暂缓；权限撤销取消；Developer ID/公证/staple/
  Gatekeeper clean-user 未验证。没有提交、打标签、push 或创建 PR。

## 最新源码状态：前台交接与调度器隔离（2026-09-06，未重建）

- 用户报告当前包几个常规任务正常；只作为用户真机反馈，不扩展为所有任务 validated。
  日志中三次 `decision=corroborated-bound-window` 后战斗继续，支持已安装包处理
  AppKit 单次否定的修复有效。
- 日志中的 game activation 启动失败来自主动激活路径。本轮改为开始/恢复后
  最多 30 秒等待用户切回游戏，可取消等待，不检测 Option、不要求固定释放鼠标方式。
  输入仍须通过绑定、新鲜帧、generation、guard 和最终 pre-post，失焦不自动夺回焦点。
- 启动失败回滚本次新启用/入队状态，保留原任务；Mac 不再调用 Windows schtasks。
- 日志仍有 FarmEcho 的 travel 等待超时、Revive Failed/CharDeadException、boss not found。
  这类 4C 路径保留 experimental，不能称全部任务闭环通过。日志未发现明确输入泄漏证据，
  但日志不是逐事件输入审计，不能由此证明所有场景零泄漏。
- 自动化：框架 663 passed、12 skipped、4 subtests passed；游戏 Mac 相关 147 passed。
  遵循本地虚拟环境技能，未新增依赖。此轮没有 source 或 packaged 真机操作。
- 下方 CURRENT 包未包含本轮启动/调度器修改；本轮未重建、安装或更换正在运行的包。
  待用户退出后可重建安装，再由用户验证启动交接和常规任务。
- Windows deferred / 未验证；16:10 暂缓；权限撤销用户取消／未执行；
  Developer ID、公证、staple、Gatekeeper clean-user 未验证。
  可准备内部发布整理，不宣称完整内部包、上游 MVP PR 或公开发行已就绪。

## CURRENT INTERNAL BUILD（2026-09-06，AppKit 交叉核验修复包）

- 已安装至 `/Applications/OK-WW Foreground Internal.app`；CDHash
  `f813aa953ff10ac08a8e20cceaf4abb492d5751b`，bundle ID `org.okww.foreground.internal`。
- 旧包正常退出后备份到 `build/macos-rollback-corroboration.UT6teg/installed-original.app`，
  未删除配置、日志、截图，未修改外部短测脚本或任务配置。
- 安装后 deep/strict 签名校验通过；从安装路径运行 `--self-check`，退出码 0：
  arm64、Qt cocoa、OpenCV 5.0.0、OpenVINO 2025.4.1 CPU、空图 OCR 和 Echo 640 模型通过，
  `input_posts=0`；随后无残留 macos_main 进程。
- 新包两项 TCC、正式 GUI/绑定及残像聚落战斗待用户验证；没有启动任何游戏任务。
  旧包权限/任务证据不可直接升级为本 CDHash 下的新证据。
- 内部最低 macOS 15.0；Windows deferred / 未验证，16:10 用户暂缓，撤权用户取消，
  Developer ID、公证、staple、Gatekeeper clean-user 未验证。未宣称完整内部包验收通过。

## PREVIOUS INTERNAL BUILD（2026-09-06，网页审查修复包及历史证据）

| 字段 | 当前值 |
|---|---|
| 安装位置 | /Applications/OK-WW Foreground Internal.app |
| bundle ID | org.okww.foreground.internal |
| 已安装 CDHash | 81770241435720d55de7fec2b30a86f3d66f90ea |
| source SHA / dirty fingerprint | 两仓基线与完整 dirty 指纹见下方本次构建证据及包内 build-provenance.json |
| minimum macOS | main/native 均不超过 15.0，LSMinimumSystemVersion=15.0；当时产品 13/14 blocked，现由 ADR 0003 收窄范围 |
| TCC | 同包授权后正常退出、重启，GUI 两权限仍 granted；cross-ad-hoc-rebuild 已观察不保持；撤销用户取消／未执行 |
| resolution | 本包 1920×1080（16:9）真实截图通过；16:10 本包未复验 |
| capture / OCR | 本包无输入自检、主窗口真实截图及紫珊瑚实景 OCR 前置检查通过 |
| input / task | packaged AutoPick 单轮组合调用通过（用户确认正常且报告吻合）；持续 Trigger 调度及其他正式任务未升级 validated |
| superseded by newer source? | 是：ok-script 新增 AppKit 否定的原绑定交叉核验，当前安装包尚未包含；外部 probe 版本另见下方 |
| known blockers | 新包定向真机、正式导航/恢复与代表任务；Windows deferred / 未验证；Developer ID/公证/staple/Gatekeeper clean-user 未验证 |

本轮源码新增：发布帧 sequence、captured_monotonic、age、geometry 的输入门槛；
2 秒 heartbeat 超时走生产 guard→release→pause，恢复需本次 resume 之后的新帧。
静态相同像素的持续发布不视为 stall。读取帧接口不再返回超龄 packet。
两处截图目录打开改用通用 open_path。NightmareNest 成功/明确不可达/未知 loading
现有单元分支保持；未做真实传送、消费或挑战。

构建新增：包内签名前 provenance、签名后外部 manifest（含 CDHash/all-native minos）、
源码编译前后指纹一致性、构建互斥锁、原子 manifest 写入；外部 probe 记录加载时源码 hash。
verifier 通过只代表 15+ 内部静态门槛，不证明原定产品 13+ 或 TCC/任务验收；原定系统范围现由 ADR 0003 取代。

### 拾取短测准备与倒计时（2026-09-06，单轮拾取通过）

- 用户准备紫珊瑚拾取场景；此前受切换 App 时游戏捕获鼠标/最小化干扰，后续用户报告测试正常。
- 外部 `scripts/macos_internal_probe.py` 新增 `autopick-once`：两帧 OCR 确认唯一高置信度紫珊瑚，
  通过 `run_task_by_class(AutoPickTask)` 调用正式任务一轮（内部最多三次 F），10 秒任务保底清理。
  保持其他任务关闭，证据仅覆盖组合调用，不替代持续 Trigger 调度验收。
- 新增 `Delayed Start` 的 8 秒启动及取消按钮；使用 task handler 定时调度，不阻塞 Qt，
  不提前启用任务、不打开 guard。结束时只读确认目标前台，再走正式 `start_controller.start(self)`。
  非前台时不启动并保留 GUI 提示；准备阶段取消/退出/destroy/停止会取消预约；每实例只 dispatch 一次。
- 正式 GUI 的 `_mark_task_enabled()` 直接置启用状态，不调用 `enable()`；因此未使用无效的 enable override。
  此按钮是内部短测入口，不宣称已修改所有正式任务的通用开始按钮。
- 自动化定向测试：`python -m pytest tests/test_macos_internal_probe.py -q`：72 passed，使用本地指定 venv。
  GUI 已目视确认 `autopick-once`、8 秒启动与取消按钮显示。
- 真机报告 `macos-internal-probe-1788678710564594000.json` 与下方 runtime hash 相符：
  真实 BGR 内容帧 1920×1080、uint8；`pickup_prompt_before=true`，调用正式 `AutoPickTask`，
  `pickup_prompt_after=false`。结合用户“测试完毕，正常”，接受本场景单轮拾取，不扩大为完整任务支持。
  `status=observed-not-accepted` 是脚本留给人工核验的状态，未篡改原始报告。
  `ordinary_attempts=0` 未统计子任务内部按键次数，不能解读为本轮零输入。
- 清理报告：held keys/buttons 均为 0、guard 关闭、capture closed、cleanup_errors 空；
  核对 `pgrep -x macos_main` 无残留进程。本轮未独立对比崩溃报告，不能新增“无新增 native 崩溃”的结论。
- 热重载后曾出现任务页空白，尚未做代码层根因修复；后续更新外部 probe 应在 App 退出后执行，
  不把热重载成功加载类等同于 GUI 列表恢复。倒计时取消等阴性行为仍只有自动化证据。
- 外部已部署 probe SHA256：`35e0aa36eb1afe5a496304f7055a61f3cf82edbf587eb31cac2446511bb165fe`。
  未重建 App、未修改签名或构建 manifest；原构建 probe hash 保留在下方历史证据。
  私人场景截图仅留运行时目录；配置 `MacInternalProbe.Mode` 为 `autopick-once`，未改其他任务或键位。
- 回滚：关闭 App，恢复原外部 probe；或将 Mode 设为 `read-only`。不删除用户配置/截图/日志。
- Windows：deferred / 未验证；撤权：用户取消；Developer ID、公证、staple、Gatekeeper clean-user：未验证。
  不升级任务 validated，不称 Mac 内部包完整验收通过。

### 当前包指南短测结果（2026-09-06，guide-entry 通过）

- 用户完成测试；报告 `macos-internal-probe-1788683650285001000.json` 的 runtime probe hash
  与上述外部部署版本一致，真实内容帧为 1920×1080、uint8。
- `entry_confirmations=2`，两次点击尝试，生产 `wait_book_destination` 返回配队准备页，
  `team_start_challenge_found=true`、`status=team-ready`；脚本到此结束，不调用开启挑战、传送或领奖。
- `finish_reason=task-finally`；held keys/buttons 均为 0、guard 关闭、capture closed、
  cleanup_errors 空，退出后 `pgrep -x macos_main` 无残留进程。
- 证据仅覆盖当前 16:9 包的分类 helper、OCR 中心点击及准备页识别；最终点击由 probe 的
  `BaseTask.click` 默认 move=True 路径完成，不替代正式任务 move=False 或“前往”地图分支验收。
  不宣称 DailyTask/TacetTask 完整闭环、窗口恢复或 16:10 已通过；本次未独立核对新增崩溃报告。
- Windows deferred / 未验证；权限撤销用户取消；Developer ID、公证、staple、Gatekeeper clean-user 未验证。

### 残像聚落误暂停修复进度（2026-09-06，尚未换包）

- 用户提供的诊断报告记载两次 AppKit 否定后暂停；无音区完整完成为用户报告，
  不扩大为每日任务全部闭环通过。残像聚落稳定完成仍未通过。
- 框架仅在原绑定有效、POSIX/CGWindow 均为肯定、原窗口 geometry 不变且前台 PID 匹配时，
  交叉确认 AppKit 否定；任何不完整证据仍停止释放，无自动 rearm。
  详情见配套框架 `docs/development/macos-liveness-corroboration.md`。
- 自动化：框架 647 passed / 12 skipped / 4 subtests；游戏 Mac 定向 147 passed。
  新修复 source/packaged 真机均未验证；当前 App 没有被替换或重新签名，不能用于验收新修复。
- 16:10 用户暂缓；Windows deferred / 未验证；撤权用户取消；公开签名、公证和 clean-user 未验证。

### AppKit 交叉核验修复包构建（2026-09-06，待安装）

- 使用现有构建脚本与 `build/macos-native-deps` 重建成功；编译前后两仓来源指纹一致。
- 产物：`build/macos-internal/macos_main.app`；来源记录与 manifest 位于现有标准路径。
- bundle ID `org.okww.foreground.internal`，arm64，285 个 native 文件；静态依赖、素材、
  隐私文件扫描、provenance 与签名校验通过，内部最低 macOS 15.0。
- 新 CDHash：`f813aa953ff10ac08a8e20cceaf4abb492d5751b`，仅 ad-hoc 内部签名。
- 旧 `/Applications` App 仍在运行，尚未替换，也未运行新包自检或战斗。
  用户要求自行测试残像聚落；本轮不新增战斗 probe，不启动或操控游戏任务。
- 等旧包正常退出后再备份安装；新包 TCC 状态与真机行为待验证，不沿用旧 CDHash 的验收结论。

### 本次构建及安装证据

- ok-script commit `3310d103e70233e675e7bf7bf2e9203003b15a97`，dirty=true；
  diff SHA256 `137b926de01b82554fa86863c8ba53a85e1ff58995f3b8acdffb70e35269b3b1`；
  worktree SHA256 `c950184f6f2f2c6337a0fe4a6d4c1cea6537f35ef7b51b20dd632255d5e0e0a5`。
- OK-WW commit `89280123e5f7c446d1b823b9642a8bf8eae66adc`，dirty=true；
  diff SHA256 `aad793b2aac46c11245bb13f2d0b4f35b208a5ceac0ee2bf3c08aac0fb011ea2`；
  worktree SHA256 `987038993ffdb4dac580ea144cb76f84510266cf19c3a8dd0db506358d755024`。
- Python 3.12.14、PySide/Qt 6.11.2、OpenVINO 2025.4.1 CPU；NPU 关闭。
- 源码与已安装外部 probe SHA256 均为
  `2aa894f6f6bec281d92def9798b07236da0eb66095210d11d11307aee9541143`；
  probe 只增加加载时 hash 记录，未自动执行。旧外部脚本已备份。
- 自动化：框架 634 passed、12 skipped、4 subtests passed；游戏相关 144 passed、3 subtests passed。
- 本地构建与安装后 verifier 均通过：arm64、285 native、all-native minos、签名、素材/翻译、
  禁止文件及个人绝对路径扫描、provenance schema；未修改 Mach-O deployment flag。
- `/Applications` 的 `--self-check` 返回 passed、input_posts=0、进程正常退出。
  随后正式 GUI 启动、关闭、重启成功；进程退出已核对，未发现新增匹配的 Python/native 崩溃报告。
  这不是已有 stream/held state 的真机退出验收。
- 构建完成当时停在权限准备页；后续用户授权并绑定，详情见下方只读复验。
- 产物：`build/macos-internal/macos_main.app`；机器记录：`build/macos-internal/build-manifest.json`。
  回滚：退出新包，恢复 `build/macos-rollback-review.0jjRrE/installed-original.app`；
  外部 probe 可恢复同目录 `probe-original.py`；保留用户配置/日志/截图不删除。
- 报告建议的“全部 dirty worktree 拆分提交”本轮未执行：历史未完成改动范围大，未把它们一并提交，
  本轮以构建指纹标识交付；未 push、未创建 PR/tag、未运行远端 CI。

### 用户授权绑定后的只读复验（同一 CDHash）

- GUI 实际显示 Screen Recording 与 Accessibility 均 granted；选择官方鸣潮主窗口，
  外框逻辑尺寸 960×568（不是内容像素尺寸）。
- 通过正式 GUI 的“截图”按钮取得 1920×1080 游戏画面，目视未见标题栏、边框、阴影或光标。
  截图仅存用户运行时目录，不放入仓库或构建产物；本次未运行外部 probe。
- 当前画面为“确认离开／重新挑战”弹窗，不是安全拾取场景。未点击游戏弹窗、未启动任何任务，
  待用户自行回到开放世界后再做短时识别和正式 AutoPick。
- 启动日志此前已取得 1920×1080 帧，随后报告 MAC_GAME_NOT_FOREGROUND 并暂停；
  不将切回 App 的预期保护行为归因于旧 MAC_TARGET_EXITED 缺陷。
- 本次只补 packaged 捕获与授权状态证据；不升级任务 validated，不声称 liveness/stall 真机验收通过。


## 2026-09-06：修正单次 AppKit 否定误报退出（最新状态）

本节取代此前“一次进程 API False 即确认退出”的结论。单次 AppKit False/异常只进入
`MAC_TARGET_UNAVAILABLE`，清除公开可用 snapshot；首次失效立即返回安全门释放 held state，
不等待辅助枚举。后续至多每 0.5 秒观察一次 AppKit、POSIX `kill(pid, 0)` 与 CGWindow PID。
仅连续三次三项均明确否定才锁定 `MAC_TARGET_EXITED`；EPERM 视为存活，未知/矛盾不确认退出。
日志记录三项信号及计数，不记录窗口标题或个人画面。未采用可能陈旧的 SCK 帧作为存活证据。
显式恢复仍要求可信唯一窗口、新 target/capture generation、geometry 和新鲜帧，不自动续战。

自动化：框架全量 624 passed、12 skipped、4 subtests passed；游戏相关 132 passed、
3 subtests passed。新增覆盖 AppKit 瞬时否定、独立证据冲突、ESRCH/EPERM/未知错误、采样间隔、
正信号清零、首/末检查释放 held state 和旧 generation 拒绝。`git diff --check` 通过。
本修正尚未重新打包或安装；已安装旧包不含此修复。source identity 与 packaged identity 的
本轮战斗复测均未执行，历史真机证据不升级。Windows：deferred / 未验证。
权限撤销：用户取消／未执行；Developer ID、公证、Gatekeeper clean-user：未验证。
回滚仅移除此轮存活确认代码和对应测试，保留原有未提交修改；不得整仓 reset。


## 当前结论

首次启动修复已有自动化及 source identity 的只读真机证据。
OpenVINO/TBB 打包阻塞已通过匹配版本官方源码重建解决。
独立 `.app` 已安装到 `/Applications`，包内无输入自检及正式 GUI 启动通过。
用户已手动授予两项 TCC 权限，同一安装产物正常退出并重启后均保持 granted；
真实捕获及只读 OCR 已通过，AutoPick 有前后画面证据；代表性完整任务仍有阻塞。
权限撤销由用户取消／未执行，packaged hold/失焦后置，**尚未达到「Mac 内部包验收通过」条件**。
该具体内部产物最低 macOS 15.0；本节当时仍以 macOS 13 为产品目标且 13/14 未满足，该历史目标现由 ADR 0003 的当前 packaged MVP 15+ 范围取代。
无 push、无 PR、未修改默认分支。已有未提交改动保留。

## 首次启动修复

- Fresh DeviceManager 在创建 provider 前发现并绑定正式主窗口；
  OK-WW 以最小逻辑尺寸 320×200 排除已观察到的约 52×20 小浮窗。
  多个合格窗口仍拒绝盲选，需手动选择。
- executor 显式 start/resume 在能力检查后调用生产 `on_run()`；
  polling 不自动重开 guard。Quartz 初始化受锁保护且已打开时幂等，
  不重置已有 held ownership。stop 后不能重新启动已退出生命周期。
- MouseResetTask 在 Mac 上默认关闭且仍为 unsupported；旧的 enabled 偏好也不会启用它，
  不修改原持久化偏好，Windows 默认不变。
- GUI 提供权限状态、用户请求按钮与显式窗口选择；绑定不启动任务或输入。

## 自动化证据

使用 OK-WW 本地 Python 3.12 arm64 venv，没有安装或引入 onnxruntime。
Mac OCR 保持 OpenVINO CPU、`use_npu=False`。

| 范围 | 结果 |
| --- | --- |
| framework 首次启动、权限面板、start controller 定向测试 | 18 passed |
| framework 当前 Mac 全量 tests | 559 passed、12 skipped、4 subtests passed |
| OK-WW Mac 相关 10 个测试文件（含离线依赖准备与内部 probe） | 55 passed |
| 两源码仓库 `git diff --check` | 通过 |
| Windows 回归 | deferred / 未验证；未运行远端 CI |

首次默认启用 TriggerTask 回归包含生产 executor 调度进入 `run()`；
窗口发现、失败关闭与 held-state 测试使用假的系统边界，不直接开 guard、
不跳过生产 on_run 或执行前能力检查。模拟测试不算真机证据。
12 skipped 包含 Win32-only、需要 native window server 及缺少 optional httpx2 的项目。

## Source identity 真机证据

修复后 fresh AutoLogin 只读短测（10 秒上限）：

- 初始 `enabled=true`、`fresh_provider=true`；没有手工绑定 ID 或 disable/enable。
- 经正式 StartController 绑定官方主窗口并进入任务。
- 2 次完成识别，`logged_in=true`，ordinary attempts/posts 均为 0，进程 exit 0。
- finally 停止 executor、关闭 capture 并退出；此证据不替代 packaged identity。

此前 source identity 已验证 AutoPick 地面拾取、无目标零输入、AutoLogin 已登录、
AutoCombat 基本战斗和停止释放，以及基础按键/鼠标和代表性失焦释放。
本轮不重复穷举输入组合，不由此声称全部任务或角色循环通过。

## Packaged identity 真机验收

身份与构建设计见 ADR 0002；bundle ID 为 `org.okww.foreground.internal`。
当前构建输出为 `build/macos-internal/`，构建日志/报告仅本地，不提交。

### 初次构建阻塞及已尝试方案（历史）

Nuitka 4.1.1 完成 1115 个 C 文件编译与链接，在复制/重定位 OpenVINO 原生库时失败。
Apple Xcode 与 Command Line Tools 的 `install_name_tool` 均报告：
`link edit information does not fill the __LINKEDIT segment`。

| OpenVINO wheel | 独立副本预检 |
| --- | --- |
| 开发 venv 原有 2026.3.1 | libhwloc.dylib 重定位失败 |
| 隔离候选 2026.2.1 | libhwloc.dylib 重定位失败 |
| 隔离候选 2025.4.1 | libhwloc 等通过，但 libtbbbind_2_5.3.dylib 重定位失败 |

2026.3.1 原 libhwloc 与 Nuitka 复制品 SHA256 一致，确认不是复制损坏。
`__LINKEDIT`/文件末尾比 `LC_CODE_SIGNATURE` 末尾多 16 字节零 padding。
Apple `codesign` 去签名/重新 ad-hoc 签名同样拒绝该副本。
未手工修改第三方 Mach-O header、未移除运行时所需库、未绕过重定位或签名检查。

隔离的 2025.4.1 使用现有模型完成 CPU OCR 空图推理及 Echo 640×640 模型编译，
exit 0，但这不抵消其打包预检失败，因此没有采用为内部发行依赖。
候选 wheel 从 PyPI 下载并对照 SHA256：

- 2026.2.1：`7afed0219cd29fa73f54b7351ffab8e7c7fefb64290dd5264d7c447617ee09ff`
- 2025.4.1：`8d082e73af653a40b97efaa8219adf62c60f32060b9929ebcb60d7f14e79e4f1`

所有候选仅安装在 ignored build 子目录；开发 venv 的 OpenVINO 2026.3.1 未替换。
构建脚本现于编译前对原生库临时副本执行重定位与 ad-hoc 签名/验证，失败即停止。
残缺产物已隔离为 `build/macos-internal/macos_main.app.incomplete`，未启动、未安装。
未进行 packaged TCC 授权/撤销测试，没有为试错启动残缺包或制造退出崩溃报告。
下一步需解决 OpenVINO/TBB 原生依赖的可重定位构建，再恢复下列验收。

### 本轮继续：可重现依赖修复与独立包证据

- 使用 SHA256 固定的 OpenVINO 2025.4.1 wheel、oneTBB 2021.13.0 commit
  `1c4c93fc5398c4a1acb3492c02db4699f3048dea` 与 hwloc 2.9.3 编译头。
- `prepare_macos_native_deps.py` 已从全新目录完整执行成功，不修改开发 venv。
  四个 TBB 库 exports 与原库分别同为 99/28/4/3，无缺失或新增。
- 禁止 CMake build RPATH，以 `-ffile-prefix-map` 去除编译路径；
  Apple 工具重定位新库的包内依赖并本地签名，全部 dylib/so 预检通过。
- 正式隔离依赖目录 `build/macos-native-deps`；来源与新库 hash 收据为
  `openvino/okww_native_build.json`，同 OpenVINO/oneTBB 许可证一起随包保留。
- Nuitka standalone 构建成功。安装位置：`/Applications/OK-WW Foreground Internal.app`。
  主程序 arm64；285 个原生文件均具有 arm64 slice；`codesign --verify --deep --strict` 通过。
  静态扫描未发现当前开发用户路径、虚拟环境、日志、个人截图目录、崩溃报告或 pyc。
- 通过 LaunchServices 从 `/Applications` 启动 `--self-check`，实际运行 identity
  为 `org.okww.foreground.internal`；Qt cocoa、OpenCV 5.0.0、OpenVINO 2025.4.1 CPU、
  PyObjC 四框架、模板索引、图标、中文 gettext、OCR 空图、Echo 640×640 模型均通过。
  TBB interface 12130、bind/proxy 动态加载通过；该路径不创建 capture 或发送输入。
- 随后从同一安装路径打开正式 GUI。权限面板分别显示
  `screen-recording: permission-required`、`accessibility: permission-required`，
  并显示系统设置指引；未自动授权、未绑定或启动游戏任务。
- 用户手动授权后，两项状态均为 `granted`。正常退出后确认安装路径下进程结束，
  再启动同一 `/Applications` 产物，两项状态仍为 `granted`，并能重新枚举鸣潮主窗口。
  此次没有重建或更换签名，因此仅证明同一产物重启保持，不证明 rebuild persistence。
- 无 capture/held input 的空闲退出日志包含 `Executor destroy` 与 `quit app`；
  此次检查未发现以 `macos_main` 或 `OK-WW` 命名的新崩溃报告。
  不把空闲退出提升为活跃截图流/持有输入时的退出清理通过。
- computer-use 可读取 GUI 状态，但窗口选择操作未生效，坐标操作返回
  `noWindowsAvailable`；应用进程仍在运行。暂请求用户手动选择主窗口并绑定，
  不将工具交互故障归因于捕获或输入后端，不点击 Start 启用其他默认任务。
- 用户手动绑定后，包内“截图”成功保存真实 1280×800 内容图；目视无标题栏、
  边框、阴影或光标。生产 diagnostics 同时记录 outer 640×428 logical、
  content 640×400 logical、display_scale=2，未伪造或拉伸尺寸。
- 用户准备普通地面植物后，仅保留 AutoPick，其他五个 trigger 均关闭。
  正式 StartController 从 fresh provider 自动选择主窗、创建 SCStream 并进入 executor；
  前后观察角色位置未变、拾取提示消失，符合拾取完成的表现。
  未采集逐事件 post 计数，不能把此证据写成完整事件审计或全部拾取场景通过。
  外部 20 秒保底仅向已核对路径的精确 app PID 发送 SIGINT；实际 executor 运行约 4 秒，
  日志确认 production SIGINT handler 正常退出。此 SIGINT 不发送游戏输入。
  退出后进程不存在，未发现匹配应用名称的新增崩溃报告。
- 新增 `scripts/macos_internal_probe.py`，经现有 `ok_tasks` loader 加载于同一已签名安装包；
  bundle 未修改，签名验证仍通过。它是 opt-in experimental 验收扩展，不是新支持的游戏任务。
  默认 read-only，仅输出帧形状、dtype、OCR 数量；另有最多 4 秒的 W hold-focus 模式。
  保留能力门控、禁止其他 enabled task 共存、生产 on_run 与 Quartz 不变，
  finally 和 10 秒保底调用 stop/release_all/capture.close/正常退出，不 force-kill。
  报告只证明观测到的状态，进程退出与崩溃文件仍须在进程外核对。
- probe 已加载，但只读任务的两次 GUI 启动均被
  `MAC_GAME_NOT_FOREGROUND: game activation request was rejected` 拒绝，未进入 run。
  这是失败关闭证据，不是 OCR 或 hold 通过。暂请用户手动点击正常启动按钮，
  不替换 provider、不直接开 guard、不以 source Python 代替 packaged 执行。
- 后续用户成功启动只读 probe（22:53:01）：`status=completed`，
  `ordinary_attempts=0`，`frame_shape=[800,1280,3]`，`frame_dtype=uint8`，
  `ocr_count=27`。`finish_reason=task-finally`，held keys/buttons 均为 0，
  `guard_open_after=false`，`capture_state_after=closed`，`cleanup_errors=[]`。
  日志显示约 0.4 秒完成后 stop、Executor destroy、quit app；10 秒是保底上限，
  不是固定运行时长。GUI 关闭是 probe 主动正常退出，不是已有证据支持的闪退。
  当轮进程外检查未发现对应新增崩溃报告；不扩大为持有输入退出或权限撤销通过。
- 用户确认重启绑定游戏已成功；明确取消权限撤销测试，并要求先验证任务，失焦测试后置。

### 任务超时调查：离线证据与下一步

- 23:00:21 TacetTask 与 23:04:28 NightmareNestTask 都在等待
  `team_start_challenge` 时超时；失败帧仍是指南素材列表，不是配队准备页。
  两次 DailyTask 均由用户主动启动；人工移动/切窗造成的失焦、target unavailable
  记为受干扰，不据此修改队列、guard、自动置前或窗口生命周期。
- 使用现有 venv、生产 `FeatureSet` 算法及安装包内模板，对两张私有失败帧做离线复算，
  无捕获、无游戏输入、无模型依赖安装。默认 variance 为 0.002，阈值为 0.8：

  | 失败帧 | `team_close` 最佳分数 | `team_start_challenge` 最佳分数 |
  | --- | --- | --- |
  | TacetTask 指南页 | 0.9515 | 0.0162 |
  | NightmareNestTask 指南页 | 0.9483 | 0.3155 |

  `team_close` 模板框为 `(1187,20,44,42)`，确实把指南页右上关闭图标识别为阳性。
  `team_start_challenge` 框为 `(1169,713,49,58)`；后者低分符合当前页面无挑战按钮，
  不能据此降低阈值或延长等待。此为 source 算法＋packaged 素材＋既有真机帧的
  **离线缺陷复现**，不是新一轮 packaged 无人干预端到端通过。
- 生产 `anchored_point` 在 1280×800 下将 `wuyin=.73` 映射为 `(307,606)`，
  `canxiang=.83` 映射为 `(307,678)`；这已经是内容坐标，没有额外标题栏偏移。
  失败帧中无音清剿在约 y=520、残象聚落在约 y=600、梦魇祓除在约 y=680。
  当前固定分类坐标与页面行位置不符，需受控导航复验确认。
- 尚未修改挑战流程 runtime、重建安装包或发送新游戏输入。
  下一步仅在“指南→素材获取”安全页面短测分类选择和页面识别，
  不点击开启挑战、不运行完整 DailyTask、不传送、不战斗、不领奖或消耗体力。
  用户指南键 Y 按手工配置使用，自动读取客户端绑定本轮不做。
  私有帧及日志留在本机用户数据目录，不复制进仓库。
- 2026-09-06：用户已准备“素材获取”页，computer-use 只读确认了当前页面。
  内部 probe 增加 opt-in `guide-category` 模式：OCR 严格确认中文参考页后，
  仅调用安装包原有 `open_boss_book('wuyin')` 一次；不调用前往/挑战/传送流程。
  后续重新取帧；模板结果仅诊断，`observed-not-accepted` 不代表分类选择成功，
  仍需目视核对选中行。沿用 10 秒保底与 finally 清理，不改变默认 read-only。
  定向 `tests/test_macos_internal_probe.py`：18 passed（含新增 6 项）；未重跑全量。
  扩展经既有 loader 安装，未修改 bundle，`codesign --verify --deep --strict` 通过。
  旧进程经正式 SIGINT handler 退出并确认消失，再启动 GUI；两项权限显示 granted。
  CUA 侧栏点击仍报 `noWindowsAvailable`，AX Raise 未解决；正式 app 无 task CLI。
  因此尚未运行 guide-category、尚无本轮新游戏输入，等待用户操作 GUI 启动。

### 2026-09-06 受控复现与局部修复

- 用户启动 `guide-category`，00:09:16–00:09:18 完成短测。
  原安装包正式 `open_boss_book('wuyin')` 日志记录一次 `(307,606)` 点击，
  `ordinary_attempts=1`；computer-use 随后目视确认高亮“残象聚落”，
  而非“无音清剿”。无需再以人工干扰解释此次分类错位。
- 真实帧 `[800,1280,3]`、`uint8`；OCR 分类文字起始 y 分别为
  wuyin=498、canxiang=578（不是点击点）。点击后仍在素材页；
  `team_close_found=true`、confidence=0.9499、`team_start_challenge_found=false`。
  这确认指南关闭图标不能单独证明配队页；没有点击前往/挑战、传送、战斗或消费。
- `finish_reason=task-finally`，held keys/buttons=0、guard closed、capture closed、
  cleanup_errors 为空；日志包含 stop、Executor destroy、quit app。
  进程外查询确认安装包进程已退出；当前用户 DiagnosticReports 中未发现匹配
  Python/macOS 主程序或 OK-WW 名称的对应新增崩溃报告。
  此次为无持续 hold 的单击导航清理证据，不替代被后置的 hold/失焦或已取消的撤权验收。
- 源码局部修复：仅 macOS provider、opt-in anchored 且画面比参考比例更高时，
  未滚动的素材分类列表按整体顶部对齐；1280×800 下 wuyin 从 y=606 改为 526，
  canxiang 从 y=678 改为 598。坐标仍是原生帧像素，不改变捕获图像或分辨率。
  16:9、Windows 分支及尚无重新标定证据的 mengyan 滚动路径保持原行为。
- `wait_book_destination()` 统一两处判断：Mac 等待独特的 `team_start_challenge`
  正证据，而非共享关闭图标；传送候选和 10 秒等待保持，Windows 仍使用原候选。
  不降低阈值、不修改 guard/权限/热键，不自动点击等待到的挑战按钮。
- 自动化：最小三文件集 40 passed、3 subtests passed；扩大到
  `tests/test_macos*.py` 与 `tests/TestNightmareNestTask.py` 为
  **83 passed、3 subtests passed**。补齐既有 `__new__` 测试的 provider fixture，
  并新增 Mac 分支用例；未为测试安装 onnxruntime。`git diff --check` 通过。
- **修复尚未重打包或安装**。当前 `/Applications` 仍为上述缺陷复现的原产物，
  不能把 source 单测写成修复版 packaged 验收。下一步重建后只复验安全分类导航
  与挑战准备页识别；完整 DailyTask、梦魇滚动路径和资源消费流程仍未验证。
  重建会改变 ad-hoc cdhash，不能保证 TCC 保持；保留原包作回滚，不改 TCC 数据库。

### 2026-09-06 修复版重建与安装

- 使用原有 venv、Nuitka 4.1.1 与隔离 `build/macos-native-deps` 重建成功；
  1163 个 C 文件中 1161 个缓存命中、2 个重新编译，未安装新依赖或修改开发 OCR 环境。
  构建仍为 arm64、macOS 15+；不因此声称支持 macOS 13/14。
- 原安装包已保存在 ignored
  `build/macos-rollback-20260906-before-guide-fix/installed-original.app`，
  同目录另有事前校验的 `OK-WW Foreground Internal.app` 副本。
  新包通过 staging 校验后安装到 `/Applications/OK-WW Foreground Internal.app`；
  未改用户配置、日志、截图目录，未删除旧包，未 push、提交或打发布标签。
- 构建产物及安装路径均通过 `verify_macos_internal.py`：
  identity=`org.okww.foreground.internal`，主程序 arm64-only，285 个原生文件
  全部具有 arm64；deep/strict 签名、资源目录、当前用户路径及禁止文件扫描通过。
- 通过 LaunchServices 从 `/Applications` 执行 `--self-check`，00:35:33 报告 passed：
  Qt cocoa、OpenCV 5.0.0、OpenVINO 2025.4.1 CPU、PyObjC、assets、i18n、
  空图 OCR、640×640 Echo 模型通过，input_posts=0，use_npu=False。
  这不创建游戏 capture，也不证明新签名的 TCC 权限或导航任务已通过。
- designated requirement 的 cdhash 已从 `2a5096f92e82700dcc7cac2178e34c0140024f9d`
  变为 `d1ae728ebcaa7ec973db2c9bc44e4697b9097227`，bundle ID 不变。
  本轮重建后的权限保持仍需读正常 GUI 状态确认，不能沿用旧包结论。
- 自动化再确认：游戏 Mac 相关集 83 passed、3 subtests passed；框架
  native layout、first start、Quartz foreground、capture shutdown 四文件集通过（96 项）。
  独立只读核验未发现阻塞缺陷，但 probe 只验证分类方法，
  不能替代真实挑战准备页的 `wait_book_destination()` 验收。
- 正式 GUI 启动后被 macOS “Time Limit / You've reached your limit” 系统界面遮挡。
  未点击 Ignore Limit、未更改屏幕使用时间或 TCC，未发送新游戏输入。
  需用户处理系统使用限制后再检查权限与执行分类短测；
  **修复版 packaged 导航、挑战准备页识别及完整任务均仍未验证**。
- 用户处理 Time Limit 后，正式 GUI 已恢复。经“刷新权限与窗口”复查，
  Screen Recording 与 Accessibility 均显示 `permission-required`，无窗口可绑定。
  **本次 ad-hoc 重建后的权限未保持**；不能声称仅凭稳定 bundle ID 即可跨重建继承权限。
  未运行任务或发送输入，未自动操作系统权限；等待用户为 `/Applications` 新产物重新授权。
- 后续用户重新授权并重启，GUI 最终显示 Screen Recording/Accessibility 均为 granted，
  正式窗口可绑定。此次重新授权成功不改变“跨重建未保持旧授权”的结论。
  01:25 启动检查捕获到 1280×904 内容帧（outer 640×480 logical，content 640×452，scale=2），
  不满足当前 16:9/16:10 比例门槛，因此仍在有上限的启动等待，未进入分类 probe。
  随后只读观察游戏处于图像设置页，设置显示 1920×1080，窗口状态在变化；
  该设置文本不替代新鲜 capture geometry 证据，也不据此归因为后端缺陷。
  已向精确核对的内部包主进程发送 SIGINT 正常停止等待，并确认进程消失；
  待场景/尺寸稳定后继续，不放宽比例门槛、不拉伸裁切、不自动调整用户分辨率。
- 用户说明已切换到外接显示器，当前使用 1920×1080；按既有支持范围继续，
  不要求改回内屏 1280×800。此前 1280×904 与窗口变化记为换屏阶段的观测，
  不据此认定捕获后端缺陷。已停止的是当时核对的主进程，用户后来重开 GUI。
- 独立 probe 扩展明确接受 1280×800 和 1920×1080 两个验收尺寸，
  左侧 OCR ROI/页码前置判断按原生帧宽缩放，图像本身不重采样、不裁成另一比例。
  非目标尺寸与错误 dtype 仍拒绝，点击前后尺寸变化会停止。
  probe 与分类回归测试合计 36 passed；本次只更新用户数据目录中的扩展，
  不改 bundle 签名，deep/strict 验证通过。1920×1080 任务证据将与
  尚待完成的修复版 16:10 真机复验分别记录。
- 用户进一步确认本轮产品范围为内屏 16:10 与外接屏 16:9，其他比例后续适配。
  probe 已由临时两个固定验收尺寸改为与应用一致的两种比例＋最低 1280×720 检查，
  覆盖 1280/1600/1920/2560 宽的代表尺寸；不读取或改动显示器设置、不重采样截图。
  定向 probe/分类/比例测试 46 passed；两类真机证据继续分别记录。

### 修复版外接屏 16:9 分类导航（2026-09-06 01:39）

- 用户运行同一修复安装包的 `guide-category`。真实内容帧为
  `[1080,1920,3]`、`uint8`，不以设置页标称值替代 capture 证据。
  `ordinary_attempts=1`，生产 `open_boss_book('wuyin')` 的实际点击为 `(460,788)`。
  computer-use 随后只读目视确认左侧“无音清剿”高亮、右侧为无音区列表。
  **该 1920×1080 分类导航步骤通过**，不代表完整 TacetTask/DailyTask 通过。
- probe 原始状态仍为 `observed-not-accepted`：它只输出观测，不自行决定选中行；
  上述结论来自报告、生产日志及后续目视核对的合并证据，未修改原始报告。
  OCR 左侧标签 y 为 wuyin=751、canxiang=872；素材页前置/后置检查通过。
- `team_close_found=true`、confidence=0.9891，`team_start_challenge_found=false`；
  当前仍是素材页，这不算等待挑战按钮失败，也没有调用 `wait_book_destination()`。
  共享关闭图标仍会匹配，修复避免的是用它单独判配队页，不是改变其模板。
- `finish_reason=task-finally`；held keys/buttons=0、guard closed、capture closed、
  cleanup_errors 为空。01:39:20 日志显示 Executor destroy、quit app；
  进程外确认安装包进程已消失，当前用户 DiagnosticReports 未发现匹配报告。
  没有传送、开启挑战、战斗、消费或领奖。
- 下一步只验证安全挑战准备页的入口/识别，进入准备页后即停，不能放任完整
  DailyTask 执行资源操作。修复版内屏 16:10 分类真机复验仍待完成，
  hold/失焦仍后置，撤销权限仍为用户取消／未执行。

当前 ad-hoc designated requirement 为 cdhash 绑定：bundle ID 稳定并不保证
重建后 TCC 保持。重启保持/重建保持必须实测，不修改 requirement 放宽身份约束。
当前 Python 与 PySide6/Qt 的既有二进制要求 macOS 15.0，单改编译 flag 不能支持 13。
恢复 macOS 13/14 兼容需要相应构建的 Python/Qt 依赖及完整回归，本轮不伪改 Mach-O 标记。

| 门槛 | 结果 |
| --- | --- |
| 独立 arm64、依赖及 Qt/OCR/assets/i18n | 包内无输入自检通过；当前包 macOS 15+ |
| 安装并从 `/Applications` 启动 | 自检及正式 GUI 启动通过 |
| 两项 TCC 授权与重启保持 | 用户授权与同一产物重启保持通过；重建保持未验证 |
| 两项 TCC 分别撤销并恢复 | 用户取消／未执行，不算通过 |
| 真实 1280×800 BGR 内容帧、无标题栏边框阴影光标 | 包内截图、生产 geometry 与 probe dtype/shape 实测通过 |
| 最短只读识别与代表任务 | 只读 OCR 通过；AutoPick 前后画面已有证据；DailyTask 挑战入口路径未通过 |
| 代表性 hold/失焦、无输入泄漏及无卡键 | 未执行，按用户要求后置 |
| stop、退出、capture 关闭、无新增退出崩溃 | 只读 probe 与 AutoPick 短测有证据；持有输入时退出未验证 |
| 重启与重新绑定 | fresh 正式启动与用户确认成功；本轮不重复 |
| 产物个人敏感信息检查 | 资源白名单与静态路径/禁止文件扫描通过 |

## 状态与限制

### 准备页只读检查准备（2026-09-06）

用户手动进入配队准备页，CUA 只读画面确认存在“开启挑战”，未点击该按钮。
独立 `macos_internal_probe.py` 的 `read-only` 模式新增同一真实帧上的
`team_close` / `team_start_challenge` 布尔与四位置信度报告，不存 OCR 全文或截图，
不增加输入调用、权限或运行模式。沿用 10 秒保底与 finally 清理。
probe / book navigation / resolution 定向测试 48 passed，包含阳性、阴性与无输入检查。
独立脚本已部署到现有 `ok_tasks`，源码与部署副本一致，安装包 deep/strict 签名检查通过，
未重建 bundle；正式 GUI 两项权限仍为 granted。
CUA 打开任务页后模式控件操作报 `noWindowsAvailable`，Raise 后仍失败；
当时尚未启动真实只读任务，随后由用户选择 `read-only` 并启动。

### 准备页只读识别结果（2026-09-06）

安装包加载独立 probe，最新报告 `macos-internal-probe-1788630825952412000.json`：
`mode=read-only`、`status=completed`，真实内容帧为 1920×1080、三通道 `uint8`，
OCR 检出 16 框；`team_start_challenge_found=true`、confidence=0.9995，
`team_close_found=false`。未修改模板或阈值。
`ordinary_attempts=0`；`finish_reason=task-finally`，held keys/buttons 均为 0，
guard 关闭、capture=closed、cleanup_errors=[]。精确安装路径进程检查无残留；
用户 DiagnosticReports 未发现名称匹配 macos_main、OK-WW、Python/python 的报告。
CUA 测后只读画面仍为配队准备页，未开启挑战、传送或消费资源。
结论：packaged identity 下 16:9 准备页模板识别与本轮只读退出清理通过。
与此前指南页挑战模板阴性结果共同支持新判据；未直接执行 `wait_book_destination()`，
用户手动进入页面不计为自动导航通过，不计为完整任务或修复版 16:10 真机通过。

### 自动进入准备页短测已准备，未实测（2026-09-06）

独立 probe 新增手动 `guide-entry` 模式，默认仍为 `read-only`。仅中文素材页验收：
先确认页面，再调用安装包的 `BaseWWTask.open_boss_book('wuyin')`；
右侧必须恰有一个置信度不低于 0.9 的“直接挑战”，两张新鲜帧的 OCR 框需稳定。
只点击第二帧 OCR 框中心，不按行号猜测，不使用无法区分“前往”的按钮模板兜底。
随后直接复用生产 `BaseWWTask.wait_book_destination()`；所需 provider 判定委派生产方法，
不改继承树、安全门或 capability check。准备页返回成功即记 `team-ready` 并退出，
未识别或返回传送页则停止，不调用开启挑战、传送、领奖或战斗逻辑。

全流程最多两个普通点击尝试；`run()` 开始后 15 秒 timer 与动作前 deadline 检查，
finally 仍执行 executor stop → release_all → capture close → report → app quit。
启动前权限/绑定等待仍由正式启动生命周期管理，不把 15 秒写成从点击 GUI 到完全退出的硬保证。
图像只通过 task `next_frame()` 获取；诊断值仅用于检查 running、帧龄不超过 1 秒、
target/capture generation 与完整 geometry 不变、新发布计数递增。
点击前再次检查识别时效与 epoch，最后仍经过 production Quartz/ForegroundGuard/pre-post。
同尺寸重绑、无新帧、错误页面、无目标/多目标、错字、低置信度、框移动、超时和停止均拒绝。

自动化证据：`tests/test_macos_internal_probe.py` 为 61 passed；
`tests/test_macos*.py tests/TestNightmareNestTask.py` 为 126 passed、3 subtests passed。
独立只读复核未发现阻塞性问题；未发送真实游戏输入。
已部署到安装应用使用的独立 `ok_tasks` 目录，源码与部署副本 `cmp` 一致，
安装包 deep/strict 签名检查及 `git diff --check` 通过；未重建 `.app`、未变更 TCC。
旧 probe 备份位于本地 ignored `build/macos-internal/probe-rollback.K4obeB/macos_internal_probe.py`；
回滚需先正常退出内部 app，再恢复此脚本；保留用户配置、日志和其他产物。
这次只准备脚本；即使后续通过，也仅证明 probe 的有界导航编排及正式分类/目的页 helper，
不能替代 `click_on_book_target()` 的索引/滚动路径、完整 DailyTask 或所有比例真机验收。
Windows 回归：deferred / 未验证；权限撤销：用户取消／未执行；公开发行门槛不变。

### 自动进入准备页实测通过（2026-09-06 02:16，外接屏 16:9）

用户启动安装包的 `guide-entry`，报告 `macos-internal-probe-1788632163685373000.json`
为 `status=team-ready`、真实 1920×1080 三通道 uint8、`entry_confirmations=2`，
`destination_helper=wait_book_destination`、`team_start_challenge_found=true`。
`ordinary_attempts=2` 与生产日志一致：02:16:01.148 分类 wuyin 点击 `(460,788)`，
02:16:02.755 唯一“直接挑战”入口点击 `(1720,730)`，02:16:03.686 报告完成。
未点击开启挑战或任何传送/领奖按钮；测后 CUA 只读画面仍为配队准备页。

`finish_reason=task-finally`；held keys/buttons 均 0，guard 关闭、capture=closed、
cleanup_errors=[]。日志有 executor destroy / quit app，精确安装路径进程检查无残留；
用户 DiagnosticReports 未发现名称匹配 macos_main、OK-WW、Python/python 的报告。
结论：packaged identity 下，这段“分类 → 唯一直接挑战入口 → 正式准备页识别 → 停止退出”
有界自动导航通过，不再只是手动进入后的静态识别证据。
仍不包含完整 DailyTask、`click_on_book_target()` 索引/滚动路径、修复版 16:10 实测，
也不替代 held/失焦、权限撤销或完整内部包验收。

任务注册状态保持现有声明：AutoPick/AutoLogin/AutoCombat 的 source 短测
是具体场景证据，不把全部任务提升为 validated；packaged 完整任务仍待验。
MouseResetTask：unsupported。relative mouse / 完整跑图 / 全角色循环未验证，
不是当前基础 MVP 阻塞项。16:10 遵循 ADR 0001，不拉伸或伪造 1080p。
用户自定义热键必须经配置确认，不把默认 F2 当成指南真实绑定。
正式 GUI 的 Windows 计划任务页当前会产生一次非致命 `schtasks` 不存在日志；
Mac 不提供该计划任务功能，本轮未使用；它不影响权限面板或启动，后续应隐藏该入口。

Developer ID、公证、staple、Gatekeeper clean-user：未验证。
内部 ad-hoc 签名不代表公开发行证据；即使内部包通过，也不代表最终上游 MVP PR 就绪。

### 正式任务点击坐标修复与内部包重建（2026-09-06）

正式 `BaseWWTask.click()` 默认 `move=False`，旧 Quartz 分支丢弃传入坐标，
在当前光标处按下；释放又查询光标，可能与按下位置不同。
这解释了正式任务记录目标坐标但仍停在指南页的失败。失焦停止及窗口丢失日志
另记为干扰，不全部归因于此缺陷。此前 `guide-entry` 继承 `BaseTask`、使用
默认 `move=True`，其成功证据不覆盖正式任务的 `move=False` 路径。

修复位于通用框架 `ok/device/interaction_methods/quartz.py`：完整 x/y 在
现有 guard 回调内转换，down/up 使用同一目标全局坐标；`move=False` 仅不发送
独立 mouse-move 事件，不再丢弃坐标，也不承诺系统光标绝对不动。
保持 production ForegroundGuard、geometry generation 和最终 pre-post check；
独立 hold、swipe、紧急 release_all 及 Windows 实现不变，未批量修改游戏任务。

自动化证据（不等同于真机输入）：

- 修复前 6 项目标坐标测试失败；修复后最初 Quartz/modifier 定向 78 passed。
- 后续补充释放失败用例，框架最终全量：577 passed、12 skipped、4 subtests passed。
  命令：从框架仓库使用游戏仓库 `.venv/bin/python -m pytest -o addopts='' -q`。
- 游戏 Mac 相关及 NightmareNestTask：128 passed、3 subtests passed；
  命令：`.venv/bin/python -m pytest tests/test_macos*.py tests/TestNightmareNestTask.py -q`。
- 新增正式 BaseWWTask Box 中心分派及 click_on_book_target 回归；框架覆盖三按钮、
  move 两值、光标变化、前台/代次失效、最终发布拒绝和释放清理。

内部包已重建并安装至 `/Applications/OK-WW Foreground Internal.app`。
稳定 bundle identifier 为 `org.okww.foreground.internal`，本轮 ad-hoc CDHash 为
`2137a8e79a456f020c85844936ef0939efbebd47`。构建与安装副本均通过包验证：
主程序 arm64-only、285 个 native 文件含 arm64、deep/strict 签名、素材与翻译、
禁止文件及个人路径检查。本内部包运行基线仍为 macOS 15+，不宣称已支持 13/14。

从 `/Applications` 经 LaunchServices 运行 `--self-check`，正常退出且 input_posts=0：
Qt cocoa、OpenCV 5.0.0、OpenVINO 2025.4.1 CPU、空图 OCR、640×640 echo 模型加载通过。
自检退出后无匹配进程；用户 DiagnosticReports 未发现对应名称的新报告。
随后正常 GUI 可启动，但 Screen Recording 与 Accessibility 均显示
`permission-required`：需用户重新授权；未绑定、未点开始、未发送游戏输入。
不能将稳定 bundle identifier 等同于本次重建后的 TCC 权限保持通过。

source identity 既有真机证据保持原范围；新包正式 move=False 点击、Tacet 首项
“前往→地图页”、第三项“直接挑战→准备页”及 NightmareNest/Daily 前置导航均待复验。
到目的页即停，不实际传送、开启挑战或消费资源。修复版 16:10 正式任务也未验证。
任务声明不升级；MouseResetTask 保持 unsupported，其他 experimental 项不因单测转为 validated。
packaged hold/失焦尚待验；权限撤销为用户取消／未执行。
Windows：deferred / 未验证；Developer ID、公证、staple、Gatekeeper clean-user：未验证。
因此本轮不能称“Mac 内部包验收通过”、上游 MVP PR 就绪或公开发行就绪。

旧安装包保留于游戏仓库 ignored
`build/macos-rollback-click.2iNPr5/installed-original.app`；需要回滚时先正常退出新包，
确认清理后恢复旧包到上述安装位置，保留用户配置、日志和截图。
构建、自检日志仅存本地 ignored `build/macos-internal/`，不提交个人证据。

### 第二轮正式任务报告与恢复修复（2026-09-06）

用户提供的第二轮日志分析及现场报告补充：正式 BaseWWTask `move=False` 已实际完成
指南分类、目标选择、地图传送按钮点击；重新绑定后 NightmareNest 基础战斗可运行。
这属于旧 packaged identity 的特定场景正面证据，不代表完整任务闭环或本次新构建通过。
用户切回 GUI 后的失焦停止记为干扰；窗口不可用不能仅凭日志断言一定发生 window ID 重建。
本次 Tacet 所选第一项区域未解锁，记录为场景限制，不据此认定地图分支有缺陷，
也未修改 TacetTask 配置或逻辑；后续在已解锁条目复验。

本轮修复：

- 框架 Quartz 显式 on_run 先等待持久 capture 的新鲜帧和一致 generation，
  再走原有前台观察和 guard 校验；TaskCard 恢复使用后台 controller，失败保留暂停。
- 窗口暂失后用户点恢复，会按原稳定身份/尺寸/歧义规则有界重找主窗口并重建流；
  不自动在后台续跑、不绕过 guard。完整无干预窗口丢失恢复仍不作通过承诺。
- NightmareNest 增加 Mac 专用传送等待：点击后重新请求帧，始终使用原有最长 120 秒
  世界/队伍等待，不再因为一秒后按钮仍可见就判不可达。明确超时且仍能识别地图
  传送入口才缓存并返回；未知加载页则抛出停止错误，不按 Esc 或重开指南。
  捕获异常不缓存为游戏目标不可达。Windows 原分支保持。

自动化：框架 597 passed、12 skipped、4 subtests passed；游戏 Mac 相关与
NightmareNestTask 132 passed、3 subtests passed。新鲜帧/代次/窗口恢复及
start/resume/queued-start/UI 路由/失败关闭，和传送延迟/超时/捕获异常均有回归。
框架实现细节见其 `docs/development/macos-start-resume-readiness.md`。
修复版正式任务、窗口恢复与传送等待真机尚未验证。

内部包已重建并安装至 `/Applications/OK-WW Foreground Internal.app`，ID 仍为
`org.okww.foreground.internal`，ad-hoc CDHash
`78d109f1919978dd356de685d4351dc184baf894`。构建及安装副本静态验证通过：
arm64 主程序、285 native 文件、deep/strict 签名、资源与禁止文件检查。
Applications 经 LaunchServices 的 `--self-check` 正常退出、input_posts=0；
Qt cocoa、OpenCV 5.0.0、OpenVINO 2025.4.1 CPU、空图 OCR 和 640×640 模型加载通过。
GUI 正常打开，两项 TCC 均 permission-required，等待用户重新授权；没有绑定或启动任务。
用户 DiagnosticReports 未发现 macos_main/OK-WW/Python/python 名称匹配报告；
这不是完整运行后退出验收。内部包基线仍 macOS 15+，无新增 13/14 兼容承诺。

本轮旧安装副本保留于 ignored
`build/macos-rollback-readiness.eSvDIy/installed-original.app`；回滚前先正常退出新包，
确认清理后恢复到安装位置，保留用户配置、日志、截图及独立任务目录。
构建、自检日志仅保存在 ignored `build/macos-internal/`，不提交个人材料。

任务声明不升级；MouseResetTask unsupported，其他任务按既有 experimental 声明。
Windows deferred / 未验证；权限撤销用户取消／未执行；packaged hold/失焦代表场景待验。
Developer ID、公证、staple、Gatekeeper clean-user 未验证；内部包完整验收未通过。

### 战斗中窗口瞬时缺失修复（2026-09-06）

用户现场报告：11:15:24 开启挑战、11:15:32 开始战斗，11:16:00 因
`MAC_TARGET_EXITED` 停止；未见普通失焦、用户停止或战斗完成。事后原 PID 和窗口仍存在，
并出现另一无标题窗口，原标题窗口位置改变。报告支持窗口生命周期／一次查询缺失假设，
不证明一定重建了渲染窗口，也不证明应自动选择新无标题窗口。

本轮框架修复区分 `MAC_TARGET_UNAVAILABLE`（窗口暂失／查询失败）与
`MAC_TARGET_EXITED`（原进程确认结束）。私有保留恢复身份，公开窗口/几何立即失效，
输入立即释放并暂停。显式恢复仅匹配同 PID/bundle/application name、合格尺寸/layer；
多可信主窗口人工选择，原进程结束须重新绑定；新代次和新鲜帧通过后才允许原 guard 开门。
没有后台自动续战、旧坐标输入或安全门放宽。游戏战斗／Tacet 逻辑及配置未修改。

主页面 Start 同样保留既有 target 并按同进程规则恢复，不隐式创建新绑定；
窗口仍缺失、进程结束或多候选时提示重试／人工绑定。

自动化：框架 613 passed、12 skipped、4 subtests passed；游戏 Mac 相关
132 passed、3 subtests passed；两仓 diff 检查通过。包含 16 项瞬时窗口缺失回归，
同 ID/换 ID 后组合 target/capture/Quartz 的显式恢复也经无硬件测试通过。
source/旧包现场报告与本次自动化分开；本次修复包真机尚未验证。
最终包已安装至 `/Applications/OK-WW Foreground Internal.app`，稳定 ID
`org.okww.foreground.internal`，ad-hoc CDHash
`2ebce129051af084a98df6604912719d952cf046`。构建及安装副本通过 arm64/285 native、
签名、素材/翻译与禁止文件检查。Applications 启动零输入自检 exit=0、input_posts=0：
Qt cocoa、OpenCV、OpenVINO CPU、空图 OCR 和 640×640 模型通过；退出后无对应进程残留，
用户 DiagnosticReports 未发现对应名称的新增报告。随后 GUI 可启动，但两项权限 required，
等待用户授权，未启动游戏任务。内部包仍 macOS 15+，未宣称 13/14 兼容。
旧包保留在 ignored `build/macos-rollback-transient.eWzDku/installed-original.app`；
正常退出后可恢复，用户配置、日志、截图和独立任务目录均保留。
本次构建/自检日志只留 ignored build 目录，不提交个人材料。
Windows deferred / 未验证；权限撤销用户取消／未执行；任务状态不升级，
MouseResetTask unsupported；Developer ID、公证、staple、Gatekeeper clean-user 未验证。
不能称完整内部包通过或上游 PR／公开发行就绪。

## 回滚

退出内部 app，确认退出清理后移走精确的内部 app 产物；不碰其他应用。
用户 Library/Application Support/OK-WW Foreground 数据保留，可供恢复，
不自动删除。源码改动尚未发布；不要用 reset/checkout/clean 丢弃用户原工作。
