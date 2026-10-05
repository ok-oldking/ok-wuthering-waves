# 声骸评分维护与分发

## 仓库职责

| 位置 | 分支 / 用途 | 需要维护的内容 |
| --- | --- | --- |
| `E:/ok-wuthering-waves`，GitHub `IceHe/ok-wuthering-waves` | `slim`；源码开发仓库 | `src/`、更新与构建脚本、测试及生成的 `echo-score/` |
| `E:/okww-xwuid-echo-score`，GitHub `IceHe/okww-xwuid-echo-score` | `main`；供用户安装的分发仓库 | `echo-score/`、`echo-score.zip`、README 与 AGENTS.md |
| `D:/ok-ww/data/apps/ok-ww/working/ok_import/echo-score` | 本机已安装 OKWW 的导入目录 | 与分发仓库一致的导入文件 |

源码里的评分代码、OCR、界面、配置或模板变化后，必须重新生成导入产物并同步三处。
分发仓库的 `echo-score.zip` 必须包含顶层 `echo-score/`，与文件夹逐文件一致，且不包含
`__pycache__`。交付前必须分别提交并推送源码仓库 `fork/slim` 和分发仓库 `origin/main`。

## 更新 XW-UID 角色模板与评分权重

脚本：[scripts/update_xwuid_echo_templates.py](../scripts/update_xwuid_echo_templates.py)。
在 `E:/ok-wuthering-waves` 的 PowerShell 中运行：

```powershell
# 只拉取上游并查看模板差异，不修改本项目文件
.\.venv\Scripts\python.exe scripts\update_xwuid_echo_templates.py --check

# 更新模板、测试、生成并同步产物、打包、提交推送两个仓库
.\.venv\Scripts\python.exe scripts\update_xwuid_echo_templates.py --publish --commit-push
```

脚本从 [XW-UID 资源仓库](https://cnb.cool/loping151/XutheringWavesUID-Resources) 的
`main` 拉取每个角色的全部 `calc*.json` 和 `condition.json`，报告新增、更新、删除的模板及模态条件变化。
缓存默认位于 `E:/xwuid-score-resources`，首次运行自动克隆。它记录资源提交号，校验权重数据，
完整替换内置快照，从而同时支持新角色和已有角色的权重调整。

发布流程依次执行：运行测试、递增补丁版本、生成 `.okscript` 和导入目录、同步三处文件、
验证文件内容、生成并校验分发 ZIP、更新分发 README、提交并推送两个仓库。
评分数据无变化时跳过发布；资源中的图片等无关变更不会触发新评分版本。
这套脚本同步模板和权重；XW-UID 主仓库的评分算法变化仍需单独分析和实现。

常用选项：

- 不带选项：只更新源码中的模板快照。
- `--publish`：测试、同步和打包，但不提交推送，便于人工检查。
- `--force-package`：强制执行本地发布；附加 `--commit-push` 可一并提交推送。
- `--version 0.3.11`：指定比当前版本更高的版本号，否则自动递增补丁版本。
- `--distribution <目录>`、`--install-dir <目录>`：指定分发仓库和本机导入目录。
- `--no-fetch`：使用已完整检出的本地资源缓存。

自动提交模式要求源码仓库和分发仓库均无未提交改动；发现脏工作区会停止。
测试、构建或文件校验失败会停止后续流程。推送失败时提交保留在本地，按报错提示在对应仓库
重试 `git push`。无数据变化时脚本也会跳过推送，已有未推送的提交需另行推送。
更新后重启 OKWW，加载新的脚本与模板。

## 已验证的发布记录

2026-10-05 已核对的功能发布版本为 **0.3.10**，内置 **68** 套角色/多模态模板。
该次全量核对发现，现有评分权重与 XW-UID 资源提交
`0e2679afdc411a716687c47e6e4b0d7b129dc9d1` 完全一致，未发现新增权重。
61 项测试通过，三个导入目录及分发 ZIP 已同步并校验。

- 源码功能提交：[1989cb7a](https://github.com/IceHe/ok-wuthering-waves/commit/1989cb7aaaf178f5e6f8856f77f2c90cc32ff87b)，已推送到 `slim`。
- 分发产物提交：[5fcec3f](https://github.com/IceHe/okww-xwuid-echo-score/commit/5fcec3f041b69bc4badca9e2a3234bc3744ae8e4)，已推送到 `main`。

以上为该次功能发布记录；后续文档提交不改变其版本号和评分内容。
