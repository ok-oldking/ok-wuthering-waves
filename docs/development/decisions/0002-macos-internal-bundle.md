# ADR 0002：macOS 内部独立应用身份

日期：2026-09-05。状态：实施中；不代表内部包验收或公开发行通过。

2026-09-06 补充：[ADR 0003](0003-macos-packaged-minimum-version.md) 将当前 packaged MVP 的产品最低系统版本正式收窄为 macOS 15+。下文 oneTBB 的 13.0 是该依赖的源码构建目标，不是完整 `.app` 最低版本；包内 Python/PySide6 wrapper 仍要求 15.0。该补充不修改本 ADR 的签名或权限约定。

## 决策与范围

使用 PySide6 官方部署工具所采用的 Nuitka standalone app-bundle 路径，
入口 `macos_main.py` 复用正式 `OK(config).start()` GUI，不依赖外部 Python。
使用 PySide6 6.11.2 对应的 Nuitka 4.1.1 构建，目标 arm64。
内部专用 bundle identifier 固定为 `org.okww.foreground.internal`，
显示名称 `OK-WW Foreground Internal`。不冒用上游公开发行身份。

构建脚本位于 `scripts/build_macos_internal.py`；本地输出 `build/macos-internal/`。
构建前必须在原生库临时副本上通过 Apple 重定位及本地签名预检；
预检失败就停止，不手工修补损坏的预编译第三方 Mach-O header，
不排除所需动态库。允许从固定的官方源码重建 ABI 匹配的库，
再由 Apple `install_name_tool` 正常重定位自建库并执行本地签名验证。
内部安装后从 `/Applications` 启动，不从 DMG 运行。
资源仅纳入代码、assets、icons、i18n 和必要依赖，不收集开发环境配置或日志。
运行时数据放在用户 Library/Application Support/OK-WW Foreground 下的
configs、logs、screenshots 子目录，禁止写入应用包。

## 替代方案

- 现有 PyAppify 打包/升级入口面向 Windows，不作为 Mac 内部部署入口。
- 外部 Python 的薄启动器不能证明独立分发及 packaged TCC 身份，拒绝采用。
- PyInstaller 暂不采用；优先验证现有 PySide/Nuitka 依赖收集路径。
- Developer ID、公证和 staple 留到公开发行阶段，本轮不读取签名凭据。

## 权限与安全

内部构建仅使用本地 ad-hoc 签名，不宣称公开发行可信性。
稳定 bundle ID 不等于 TCC 持久化已通过，必须实测安装位置、签名、重启与重建。
用户手动授权和撤销 Screen Recording 与 Accessibility；不读取或修改 TCC 数据库。
Qt 中显示权限状态、操作指引和主窗口选择；绑定不自动启动任务或发送输入。
输入仍经过生产 Quartz、foreground guard 和最终 pre-post check。
原生 16:10 遵循 ADR 0001，不增加后台控制或修改现有安全门。

## 原生依赖构建决策（本轮继续授权）

已验证 2026.3.1、2026.2.1、2025.4.1 wheel 各有原生库无法被当前 Apple
工具重定位。内部包固定以 OpenVINO 2025.4.1 为基础，仅在隔离 build staging
中替换其 oneTBB 四个库，开发 venv 不变，不发布修改后的 wheel。
不继续随机切换版本、不跳过动态库、不对损坏二进制做 header 修补。

oneTBB 源码取官方 v2021.13.0，commit
`1c4c93fc5398c4a1acb3492c02db4699f3048dea`，与该 wheel 的
`TBB_INTERFACE_VERSION=12130`、binary version 12 一致。
hwloc 2.9.3 发行源码仅 configure 生成编译头，运行时沿用 wheel 中通过
重定位检查的 hwloc 库。构建目标 arm64、macOS 13.0、Release。
内部构建工具版本由 pyproject.toml 的 macos-internal-build extra 声明；
归档必须通过固定 SHA256，准备脚本不自动下载、不覆盖已有输出。

四个自建库与原库 exports 分别为 99/28/4/3，静态比较没有缺失或新增；
compatibility version 分别为 12/2/2/3，current minor 13 与原库一致。
TBB bind 的 hwloc 符号均可由现有 hwloc 提供。
`/usr/local/lib/libhwloc.15.dylib` 与 malloc proxy 的依赖通过 Apple 工具
改为包内 loader-relative 路径，随后重新 ad-hoc 签名；无运行时外部库依赖。

采用门槛：全部原生库的 Apple 重定位/签名预检；完整动态加载；
CPU OCR 和 Echo 模型测试；最终 bundle 无开发机路径依赖并完成 packaged 验收。
准备脚本输出包含版本、来源归档 hash 和自建库 hash 的脱敏 provenance receipt，
随包保留依赖许可证。源码树、wheel、构建缓存与个人数据不入库、不随 app 分发。
回滚为移走隔离产物并回到未通过打包的原依赖；不改开发环境或 Windows依赖。
这些本地构建证据不构成其他 Mac 硬件、Windows 或公开发行的验证。

## 回归、验收与回滚

先运行首次 TriggerTask 启动、窗口选择、权限、释放和 GUI 面板定向测试；
再运行当前 Mac 可执行的相关测试。Windows 回归：deferred / 未验证。
必须实测独立 arm64、Qt、OpenCV、OpenVINO CPU OCR、PyObjC、素材和翻译加载；
两项权限授权、重启保持及分别撤销；真实窗口帧、只读识别、代表任务、失焦释放；
退出关闭截图流、不新增 native/Python 崩溃，并重启重新绑定。
未执行项一律保留未验证，不以源码身份结果替代 packaged 结果。

公开发行仍须完成 Windows 回归、Developer ID、notarization、staple 和
Gatekeeper clean-user 验证。内部包无自动升级，无数据迁移；不改用户游戏键位。
回滚为退出并移走精确的内部 `.app`，保留独立用户数据目录以便恢复；
如恢复旧包，重新检查系统显示的权限。不要删除其他安装或共享数据。
