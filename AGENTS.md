# 声骸评分开发与发布清单

对声骸评分代码、OCR、模板或配置完成修改后，交付前依次检查：

- [ ] 从 XW-UID 主仓库及其独立资源仓库核对角色 ID、`calc*.json`、提交号；模板数据用 `scripts/update_xwuid_echo_templates.py` 更新，不手改权重。
- [ ] 运行 `.venv/Scripts/python.exe -m unittest discover -s tests -p 'Test*.py'`，检查模板搜索、自动匹配、评分和界面回归。
- [ ] 用 `scripts/build_echo_score_okscript.py --folder --version <新版本>` 生成 `dist/echo-score` 与 `.okscript`，核对 `manifest.json`。
- [ ] 把 `dist/echo-score` 的内容同步到本仓库 `echo-score/`、`D:/ok-ww/data/apps/ok-ww/working/ok_import/echo-score/` 和 `E:/okww-xwuid-echo-score/echo-score/`，验证逐文件一致；不要覆盖用户的其他目录。
- [ ] 在 `E:/okww-xwuid-echo-score` 重新生成含顶层 `echo-score/` 的 `echo-score.zip`，核对 ZIP 文件列表与目录内容一致，排除 `__pycache__`。
- [ ] 视变更更新分发仓库 README；检查两个仓库 `git status`、diff 和测试，再分别 commit & push。除非用户另有要求，不要漏掉分发仓库。

资源仓库地址：`https://cnb.cool/loping151/XutheringWavesUID-Resources.git`。本仓库的 XW-UID 模板快照与分发包需要保持同步。
