# ADR 0003：当前 OK-WW packaged MVP 收窄为 macOS 15+

- 日期：2026-09-06。
- 状态：`accepted`，用户明确授权 contributor 的 `feature/macos-foreground-mvp` 分支采用；不代表 `ok-oldking` upstream 已接受，也不代表最终 MVP 或公开发行通过。
- 影响仓库：`ok-wuthering-waves` 的产品与构建合同；`ok-script` 仅同步 consumer 发行边界说明。
- 配套：框架 ADR `0002-consumer-packaged-minimum-version.md`；本仓库 ADR `0002-macos-internal-bundle.md` 的打包身份与依赖重建约定继续有效。

## 背景与证据

原产品合同以 macOS 13+ 为目标，但已有内部包的 Python 和 PySide6 wrapper 实际要求 macOS 15.0。仅看到 Qt 原生库或 OpenVINO 支持较低系统，不能推出整个 `.app` 支持该系统。继续宣称当前 packaged MVP 支持 13/14 会把设计目标与可执行二进制混为一谈。

已有 `build/macos-internal/build-manifest.json` 对 285 个随包 native 文件记录的最低版本分布为：

| arm64 Mach-O minos | 文件数 |
|---|---:|
| 11.0 | 109 |
| 13.0 | 99 |
| 14.0 | 13 |
| 15.0 | 64 |

主程序、包内 Python、PySide6 的 QtCore/QtGui 等 wrapper 为 15.0；Qt 原生 framework 大多为 13.0。OpenVINO 2025.4.1 主库、CPU 插件、Python bindings 与 hwloc 为 11.0；ADR 0002 固定源码重建的 oneTBB 为 13.0。本轮另对已安装包的 Python、QtCore.so、OpenVINO 主库与 oneTBB 直接解析 native minimum，结果分别为 15.0、15.0、11.0、13.0，与该限制一致。这是已有产物的静态证据，不是新提交重建或新系统运行验收。

## 决策与用户影响

当前 OK-WW packaged MVP 最低版本正式收窄为 **Apple Silicon、macOS 15.0**。macOS 13/14 与 Intel Mac 不在本次 packaged MVP 支持范围。当前用户安装文档、产品约束、构建 metadata、plist 及验证器必须一致；每个包仍须验证实际 native minos，若依赖要求更高系统则构建失败，不能自动抬高或隐瞒门槛。

`ok-script` 的公开 Apple API 设计与通用 host gate 继续保持 macOS 13+，不修改 provider 的通用最低版本判断，也不删除 13.x API 兼容路径或契约测试。这是框架设计边界，不是对任意 Python/Qt/consumer 依赖组合的二进制支持承诺。OK-WW 产品最低版本及打包策略由 consumer 管理；通用平台能力仍归框架。开发继续 sibling editable，最终依赖仍须是维护者接受的不可变版本或 commit。

## 考虑过的替代方案

1. 继续以 13+ 为当前产品承诺并推迟交付：保持原覆盖面，但与现有包的真实加载要求不符。将恢复 13/14 作为独立后续目标，而非本轮未完成的产品承诺。
2. 固定或源码重建支持 13/14 的 Python/PySide6/Qt 及完整依赖集合：技术上值得后续验证，但须重新验证 ABI、工具链、GUI、OCR、许可证和包身份，超出本轮收敛范围。不能只更换一个 wheel 或设置 `MACOSX_DEPLOYMENT_TARGET` 就声称完成。
3. 只降低 `LSMinimumSystemVersion`、修改 Mach-O load command 或跳过 native 审计：拒绝。标记修改不能消除已编译系统符号和运行时依赖，可能造成启动/加载失败。
4. 把框架 host gate 也提高到 15+：拒绝。当前限制来自 consumer 随包依赖，不是公开 API 架构需要，不能无证据收窄其他 consumer。

## 安全、权限与 Windows

本决策不增加 Apple API、依赖或权限，不引入私有 API、虚拟显示、`CGEvent.postToPid`、注入/hook、root 或 TCC 修改。ScreenCaptureKit 持久流、Quartz 前台校验、held-state 与 `release_all()`、新鲜帧/geometry generation、停止与退出失败关闭均保持。官方 Mac 客户端、仅前台边界不变。

bundle ID、签名方式、entitlement 与公证流程不因本决策改变；本轮不修改安装包签名、不公证、不执行游戏或 packaged 权限操作。历史 ad-hoc 包的 TCC 重启保持不证明跨重建保持，更不能证明新 SHA 的验收。不得提交凭据、TCC、个人日志、截图或本机路径。

Windows、ADB/browser、公共 task API、持久配置和 Windows 依赖/打包路径不因本决策改变。此为影响分析，不能替代实际 Windows 回归；本轮 exact-SHA Windows CI 结果须在运行完成后独立记录，不预填通过。

## 验证与恢复 13/14 的条件

本轮自动化检查应覆盖 build metadata 的 15.0 声明、plist 与主程序及全部 native arm64 minos 一致、未知或超基线 native 被拒绝，以及框架 host gate 仍接受 13+ 的契约。复用现有 `tests/test_macos_build_metadata.py`、`tests/test_macos_build_verifier.py`、`tests/test_macos_internal_build.py` 和框架平台测试；实际执行命令、结果与 SHA 另记当前验收记录。文档变更本身不提升能力或任务状态。

未来恢复 13/14 前须形成新 ADR，固定可复现且许可证兼容的完整 Python/Qt/OCR/native 依赖与工具链，证明每个实际随包 arm64 Mach-O 的真实最低版本满足目标；在目标版本的真实 Apple Silicon 上完成启动、Qt、CPU OCR/model、公开 API 可用性、窗口/捕获/输入/失焦释放与代表任务验证，并完成该稳定 `.app` 的权限和生命周期验收。相同源码 SHA 的 Windows/macOS CI 必须通过；新包必须记录两仓 SHA、构建指纹、CDHash 和所有外部 probe hash。只在新系统上通过的单测或旧包证据不满足该条件。

最终 MVP PR 仍须全部适用的 real-game 与 packaged-app gate 通过；公开发行另需 Developer ID、Hardened Runtime、timestamp、公证、staple 和 clean-user Gatekeeper 验证。macOS 15+ 是最低版本边界，不是这些 gate 已通过的声明。

## 迁移与回滚

本次无配置/schema 或用户数据迁移，已在 macOS 15+ 使用内部包的用户不必因文档决策更改设置。13/14 用户不能使用当前包；升级系统由用户自行决定，不能以源码运行绕过未验证的依赖限制。

回滚先停止 consumer 自动化并保留精确旧包、来源 manifest 与用户数据，再按明确产物恢复。撤销此 ADR 或 metadata 不能使现有 15.0 二进制获得 13/14 支持；在完整旧系统门槛未通过前，只能撤回发行/支持声明，不能重新写成 13+。框架 13+ host gate 无需随 consumer 回滚。既有安全修复不应随产品范围回滚被撤销，旧源码和旧包证据均按原身份保留。

## 外部来源与审批记录

本决策无新引入的第三方代码或依赖；既有 OpenVINO/oneTBB 来源、固定版本、ABI 与许可证材料沿用 ADR 0002。用户于 2026-09-06 明确批准将当前 packaged MVP 收窄为 macOS 15+ 并保留框架 13+ 设计；本 ADR 是 contributor 分支的持久记录，upstream 最终审查尚未发生。
