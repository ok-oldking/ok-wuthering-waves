# 声骸评分开发与发布清单

对声骸评分代码、OCR、模板或配置完成修改后，交付前依次检查：

- [ ] 用 `scripts/update_xwuid_echo_templates.py --check` 全量核对 XW-UID 资源仓库的角色、多模态 `calc*.json`、条件与提交号，不手改权重。主仓库的评分算法变化需单独审查。
- [ ] 运行 `.venv/Scripts/python.exe -m unittest discover -s tests -p 'Test*.py'`，检查模板搜索、自动匹配、评分和界面回归。
- [ ] 用 `scripts/build_echo_score_okscript.py --folder --version <新版本>` 生成 `dist/echo-score` 与 `.okscript`，核对 `manifest.json`。
- [ ] 把 `dist/echo-score` 的内容同步到本仓库 `echo-score/`、`D:/ok-ww/data/apps/ok-ww/working/ok_import/echo-score/` 和 `E:/okww-xwuid-echo-score/echo-score/`，验证逐文件一致；不要覆盖用户的其他目录。
- [ ] 在 `E:/okww-xwuid-echo-score` 重新生成含顶层 `echo-score/` 的 `echo-score.zip`，核对 ZIP 文件列表与目录内容一致，排除 `__pycache__`。
- [ ] 视变更更新分发仓库 README；检查两个仓库 `git status`、diff 和测试，再分别 commit & push。除非用户另有要求，不要漏掉分发仓库。

资源仓库地址：`https://cnb.cool/loping151/XutheringWavesUID-Resources.git`。本仓库的 XW-UID 模板快照与分发包需要保持同步。

只更新评分模板时，可在两个仓库均干净的状态运行
`.venv/Scripts/python.exe scripts/update_xwuid_echo_templates.py --publish --commit-push`，
自动完成上面的测试、版本递增、三目录同步、ZIP 校验、分发文档更新与两个仓库的提交推送。
无变化时跳过发布。修改更新脚本本身时，先检查脚本与产物的 diff，再明确提交相应文件。

## 分发仓库的强制同步要求

以下要求同时来自 `E:/okww-xwuid-echo-score/AGENTS.md`，在本 OKWW fork 中进行声骸评分开发时也必须执行：

- 评分实现、OCR、界面、配置或 XW-UID 模板有变更，就重新构建 `dist/echo-score`，同步到本仓库 `echo-score/`、D 盘 OKWW 导入目录以及 `E:/okww-xwuid-echo-score/echo-score/`，校验文件内容一致。
- 在分发仓库重新生成 `echo-score.zip`，保留顶层 `echo-score/`，排除缓存文件，并核对 ZIP 与导入文件夹内容一致。
- 更新相应文档，确认主项目测试通过、版本号一致、两个仓库 diff 合理，然后分别 commit & push：本仓库推送到 `fork/slim`（`IceHe/ok-wuthering-waves`），分发仓库推送到 `origin/main`（`IceHe/okww-xwuid-echo-score`）。
- 不要只修改源码或 D 盘安装目录；未完成分发仓库同步、打包与推送时，应明确报告未完成的步骤，不能声称发布完成。
- 仅有文档改动时提交并推送对应文档即可，无需递增评分包版本或重打没有变化的产物。

更新脚本及两个仓库的维护说明见 `docs/echo-score-maintenance.md`。
