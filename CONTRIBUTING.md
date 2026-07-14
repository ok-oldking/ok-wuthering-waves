# 贡献指南 / Contributing Guide

感谢你愿意为 `ok-ww` 做贡献。本项目是基于图像识别的《鸣潮》自动化工具，使用 [ok-script](https://github.com/ok-oldking/ok-script) 开发，仅供个人学习与交流使用。提交贡献前，请先阅读 [README.md](README.md) 中的免责声明、开发者专区和社区信息。

Thank you for contributing to `ok-ww`. This project is an image-recognition-based automation tool for Wuthering Waves, developed with [ok-script](https://github.com/ok-oldking/ok-script), and is intended only for personal learning and communication. Before contributing, please read the disclaimer, developer section, and community information in [README.md](README.md).

## 提交 PR 前 / Before Opening a PR

请先确认你的修改范围：

Please check the scope of your change first:

- Bug 修复、文档修正、翻译修正、小型兼容性修复：可以直接提交 PR。
- 新功能、重构、架构调整、角色逻辑大改、任务行为大改、会显著改变现有功能体验的修改：请在提交 PR 前先联系作者或在社区中讨论，确认方向后再开始或提交。
- 不确定是否属于“大改”的修改：请先联系作者。

- Bug fixes, documentation fixes, translation fixes, and small compatibility fixes: you may open a PR directly.
- New features, refactors, architecture changes, major character logic changes, major task behavior changes, or changes that significantly alter existing behavior: please contact the author or discuss with the community before opening a PR.
- If you are unsure whether a change is major, please contact the author first.

## 联系方式 / Contact

- 开发者群 / Developer QQ group: `926858895`
- Discord: [https://discord.gg/vVyCatEBgA](https://discord.gg/vVyCatEBgA)

开发者群仅面向有开发能力、希望参与贡献的开发者。入群前请确保你已经能够从源码成功运行项目。

The developer group is for developers who can contribute to the project. Please make sure you can run the project from source before joining.

## 开发环境 / Development Environment

本项目仅支持 Python 3.12。建议使用仓库内的本地虚拟环境运行命令。

This project only supports Python 3.12. Prefer using the repository-local virtual environment when running commands.

```powershell
# 安装或更新依赖 / Install or update dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --upgrade

# 如需开发测试依赖 / For development test dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt --upgrade

# 运行 Release 版本 / Run release version
.\.venv\Scripts\python.exe main.py

# 运行 Debug 版本 / Run debug version
.\.venv\Scripts\python.exe main_debug.py
```

如果没有 `.venv`，可以使用 `python` 代替上面的解释器路径。

If `.venv` does not exist, use `python` instead of the interpreter path above.

## 测试 / Testing

提交 PR 前，请尽量运行相关测试，并在 PR 描述中说明测试结果。

Before opening a PR, please run the relevant tests when possible and include the results in the PR description.

```powershell
.\run_tests.ps1
```

也可以直接运行指定测试：

You can also run a specific test directly:

```powershell
.\.venv\Scripts\python.exe -m unittest tests\TestChar.py
```

## PR 要求 / PR Requirements

- 保持修改范围清晰，避免把无关格式化、重构和功能修改混在同一个 PR 中。
- 说明改动目的、主要实现方式、影响范围和测试结果。
- 修改用户可见行为时，请补充截图、录屏或清晰的复现说明。
- 修改配置、任务、角色逻辑或识别逻辑时，请说明适用场景和可能影响。
- 不要提交日志、缓存、临时文件、个人配置或无关生成文件。

- Keep the PR focused. Avoid mixing unrelated formatting, refactoring, and feature changes in one PR.
- Describe the purpose, implementation, impact, and test results.
- For user-visible behavior changes, include screenshots, recordings, or clear reproduction notes.
- For configuration, task, character logic, or recognition logic changes, describe the applicable scenarios and possible impact.
- Do not commit logs, caches, temporary files, personal settings, or unrelated generated files.

## 提交流程 / Submission Flow

1. Fork 本仓库并创建你的功能分支。
2. 完成修改并运行相关测试。
3. 确认是否需要先联系作者，尤其是新功能或大幅修改现有功能。
4. 提交 PR，并填写 PR 模板中的所有相关内容。
5. 根据维护者反馈调整修改。

1. Fork this repository and create your feature branch.
2. Make the changes and run relevant tests.
3. Confirm whether author contact is needed, especially for new features or major changes to existing behavior.
4. Open a PR and fill in all relevant sections of the PR template.
5. Update the PR based on maintainer feedback.
