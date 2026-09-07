# macOS Stage F 前台输入硬件 Smoke

本入口只用于 `feature/macos-foreground-mvp` 集成分支的受控硬件验收，不代表任何任务已达到 `validated`。保持官方《鸣潮》客户端为窗口模式；首个验收内容帧必须为 actual `1920×1080`。

## 1. 只读预检

```bash
./.venv/bin/python scripts/smoke_macos_foreground_input.py
```

默认模式只检查 Apple Silicon/macOS 13+、Screen Recording、Accessibility、官方窗口身份和 capture geometry。它不会构造 `QuartzForegroundInteraction`，不会调用 `CGEventPost`，也不会保存 capture frame。

只有输出同时包含以下事实，才可继续：

- 两项权限均为 `granted`；
- `selection_status` 为 `selected`；
- `frame_width=1920`、`frame_height=1080`；
- `display_scale=2.0`；
- `ready_for_one_f2_tap=true`；
- `event_post_attempted=false`。

## 2. 同尺寸窗口移动验收

```bash
./.venv/bin/python scripts/smoke_macos_foreground_input.py \
  --observe-window-move --move-delay 8 --timeout 12
```

看到 `MOVE_WINDOW_NOW` 后，在等待时间内水平移动游戏窗口一次并松手，不改变窗口尺寸。该模式仍不构造输入后端。通过条件：

- target generation 前进；
- `stream_rebuilds=1`；
- target outer geometry 与 capture outer geometry 最大差值不超过 `0.5` logical point；
- `move_observed=true`；
- `event_post_attempted=false`。

若出现多个匹配窗口，先用只读诊断取得当次主窗口 ID，再通过 `--window-id` 显式选择。runtime window ID 不得持久化。

## 3. 首次真实输入

只有在前两步通过、测试者明确确认本次动作后，才允许运行：

```bash
./.venv/bin/python scripts/smoke_macos_foreground_input.py \
  --execute-one-f2-tap --confirm I_CONFIRM_ONE_F2_TAP
```

这个模式仅执行一次 `F2` key tap。运行时会再次验证 host、权限、target、frontmost、capture state 和 geometry generation；若游戏不是前台，只允许请求一次 activation，并必须观察到官方游戏实际成为 frontmost 后才可继续。普通 event 在紧邻 `CGEventPost` 处再次检查 gate。

错误确认短语在 runtime 初始化前被拒绝。正常与异常路径均先关闭 input/release held state，再关闭 capture；任何 cleanup failure 返回非零。

## 4. 明确不在本 smoke 范围内

- W/A/S/D 或 mouse button hold；
- Command-Tab 失焦释放；
- click、scroll 或组合输入；
- relative mouse / `MAC_FULL_CAMERA`；
- task 端到端；
- packaged `.app` 权限身份；
- push、PR 或远端 CI。

一次 F2 成功只能作为 Stage F 第一条真实输入证据，不能升级任何 task 的 `validated` 状态。
