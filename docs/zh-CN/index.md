<div align="center">
  <h1 align="center">
    <img src="https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves/master/icons/icon.png" width="200" alt="ok-ww logo"/>
    <br/>
    ok-ww
  </h1> 
  
  <p>
    一个基于图像识别的鸣潮自动化程序，支持后台运行，基于 <a href="https://ok-script.com">ok-script</a> 开发。
    <br />
    An image-recognition-based automation tool for Wuthering Waves, with background mode support, developed with <a href="https://ok-script.com">ok-script</a>.
  </p>
  
  <p><i>通过 Windows 接口模拟用户进行操作，无内存读取、无文件修改</i></p>
</div>

<!-- Badges -->
<div class="badge-row">
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="平台" />
  <a href="https://github.com/ok-oldking/ok-wuthering-waves/releases"><img src="https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves" alt="GitHub release" /></a>
  <a href="https://github.com/ok-oldking/ok-wuthering-waves/releases"><img src="https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total" alt="总下载量" /></a>
  <a href="https://discord.gg/vVyCatEBgA"><img src="https://img.shields.io/discord/296598043787132928?color=5865f2&amp;label=%20Discord" alt="Discord" /></a>
</div>

<p align="center"><strong>官方网站：</strong> <a href="https://ok-script.com/ok-ww">https://ok-script.com/ok-ww</a></p>

### [English](../en/index.md) | 简体中文 | [繁體中文](../zh-TW/index.md) | [日本語](../ja/index.md)

**演示与教程:** [![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/h6P1KWjdnB4)

---

## ⚠️ 免责声明

本软件为外部辅助工具，旨在自动化《鸣潮》的部分游戏流程。它完全通过模拟常规用户界面与游戏交互，遵循相关法律法规。本项目旨在简化用户的重复性操作，不会破坏游戏平衡或提供不公平优势，也绝不会修改任何游戏文件或数据。

本软件开源、免费，仅供个人学习与交流使用，请勿用于任何商业或营利性目的。开发者团队拥有本项目的最终解释权。因使用本软件而产生的任何问题，均与本项目及开发者无关。

请注意，根据库洛官方的《鸣潮》公平运营声明：
> 严禁利用任何第三方工具破坏游戏体验。
> 我们将严厉打击使用外挂、加速器、作弊软件、宏脚本等违规工具的行为，这些行为包括但不限于自动挂机、技能加速、无敌模式、瞬移、修改游戏数据等操作。
> 一经查证，我们将视违规情况和次数，采取包括但不限于扣除违规收益、冻结或永久封禁游戏账号等措施。

**使用本软件即表示您已阅读、理解并同意以上声明，并自愿承担一切潜在风险。**

## 🚀 快速开始

1.  **下载安装包**：从下方的“下载渠道”中选择一个，下载最新的 `ok-ww-win32-China-setup.exe` 安装文件。
2.  **安装程序**：双击 `ok-ww-win32-China-setup.exe` 文件，并按照安装向导的提示完成安装。
3.  **运行程序**：安装完成后，从桌面快捷方式或开始菜单启动 `ok-ww` 即可。

## 📥 下载渠道

*   **[GitHub](https://github.com/ok-oldking/ok-wuthering-waves/releases)**: 官方发布页，全球访问速度快。（**请下载 `setup.exe` 安装包，而不是 `Source Code` 源码压缩包**）
*   **[Mirror酱](https://mirrorchyan.com/zh/projects?rid=okww&source=ok-ww-readme)**: 国内镜像，下载可能需要购买其平台的 CD-KEY。
*   **[百度网盘](https://pan.baidu.com/s/102Mh1djq2B1T-cIJhct9Gg?pwd=okww)**: 免费下载
*   **[夸克网盘](https://pan.quark.cn/s/24433f3febc1)**: 免费下载

## ✨ 主要功能
<img width="1774" height="1182" alt="QQ_1762960844719" src="https://github.com/user-attachments/assets/c5eb0145-0d45-44f9-85b3-184de0ef20bf" />

*   **高分辨率支持**: 流畅运行于 4K 及以下所有 16:9 分辨率（最低 1280x720）。部分功能兼容 21:9 等超宽屏。
*   **后台模式**: 支持游戏窗口最小化或被遮挡时在后台运行，不影响您使用电脑。
*   **智能识别**: 全角色自动识别，无需手动配置技能序列，一键启动。
*   **自动静音**: 在后台运行时，可自动将游戏静音。

## 🔧 疑难解答 (Troubleshooting)

如果遇到问题，请在提问前按以下步骤逐一排查：

1.  **杀毒软件**：将软件的安装目录添加到您的杀毒软件（包括 Windows Defender）的**信任区或白名单**中，以防文件被误删或拦截。
2.  **显示设置**：
    *   一般可以开启游戏内滤镜。
    *   可以开启 Windows HDR，但必须关闭 Auto HDR（自动 HDR）。
    *   建议关闭显卡滤镜，例如 RTX HDR、RTX 动态亮丽（RTX Dynamic Vibrance）、AMD 锐化等。
    *   使用游戏默认的亮度设置。
    *   关闭任何在游戏画面上显示信息的叠加层（如 MSI Afterburner、Fraps 等显示的帧率）。
3.  **自定义按键**：如果您修改了游戏内的默认按键，请务必在 `ok-ww` 的设置中进行同步配置。仅支持设置中列出的按键。
4.  **软件版本**：检查并确保您使用的是最新版本的 `ok-ww`。
5.  **游戏性能**：请确保游戏能稳定在 **60 FPS** 运行。如果帧率不稳定，请尝试降低游戏画质或分辨率。
6.  **游戏断线**：在 `ok-ww` 设置中开启“启动后关闭启动器”，确保启动器进程未在运行；或者使用源码运行。
7.  **OpenVINO 报错**：如果遇到 `0x000005` 报错，并且使用的是带 NPU 的 Intel CPU，请更新至 Intel 最新的 NPU 驱动。
8.  **寻求帮助**：如果以上步骤都无法解决您的问题，请通过社区渠道提交详细的错误报告。
9.  **关闭自动奔跑**：游戏设置里关闭自动奔跑。
10. **为所有角色装备主声骸**：队伍中的每个角色都必须装备主声骸（画面右下角应显示声骸技能图标）。任何一个角色未装备主声骸时，自动战斗将无法正常运行，并可能反复锁定敌人而不攻击。

---

## 💻 开发者专区

### 从源码运行

开发环境、源码运行和贡献说明请参阅[贡献指南](../development/contributing.md)。

### AI 技能

在支持项目技能的编码代理中打开本仓库，即可通过技能名称或自然语言提出相关请求。有关具体用法、准备工作和执行流程，请询问编码代理。

使用队伍评估或改进技能前，请先选好队伍，并进入游戏中的「深境再临」或「终焉矩阵」。

| 技能 | 简介 |
| --- | --- |
| [evaluate-team](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/evaluate-team/SKILL.md) | 通过多次战斗评估当前队伍的自动战斗循环并提出建议。 |
| [improve-team](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/improve-team/SKILL.md) | 根据队伍评估结果提出并验证角色自动战斗改进。 |
| [ok-script-develop](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/ok-script-develop/SKILL.md) | 使用 ok-script 开发和验证游戏自动化功能。 |
| [ok-script-tasks](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/ok-script-tasks/SKILL.md) | 创建、修改或审查自动化任务。 |
| [ok-ww-characters](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/ok-ww-characters/SKILL.md) | 开发、审查和测试角色自动战斗逻辑。 |
| [ok-script-i18n](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/ok-script-i18n/SKILL.md) | 添加、同步和编译任务界面翻译。 |
| [pr-review](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/pr-review/SKILL.md) | 审查或合并本项目的 GitHub PR。 |
| [deploy](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/deploy/SKILL.md) | 提交已完成的修改，创建版本标签并发布。 |
| [use-local-venv](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.agents/skills/use-local-venv/SKILL.md) | 运行 Python 命令时优先使用仓库的本地虚拟环境。 |

### 命令行参数

您可以通过命令行参数实现自动化启动。

```bash
# 示例：启动后自动执行第一个任务（一条龙），并在任务完成后退出程序
ok-ww.exe -t 1 -e
```

*   `-t` 或 `--task`: 启动后自动执行第 N 个任务。`1` 代表任务列表中的第一个。
*   `-e` 或 `--exit`: 任务执行完毕后自动退出程序。

## 💬 加入我们

*   **QQ 交流群**: `1126263229` (入群答案: `老王同学OK`)
*   **QQ 频道**: [点击加入](https://pd.qq.com/s/djmm6l44y) (群满或获取最新资讯)
*   **开发者群**: `926858895` ( **注意**: 此群仅面向有开发能力、希望参与贡献的开发者，入群前请确保您已能够从源码成功运行项目。)

本项目基于 [ok-script](https://ok-script.com) 框架开发，简单易维护。欢迎有兴趣的开发者使用 [ok-script](https://ok-script.com) 开发您自己的自动化项目。

## ❤️ 赞助与致谢

### 赞助商 (Sponsors)
*   **EXE 签名**: Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

### 致谢
*   [lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss)
*   [ok-oldking/OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
*   [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
*   [Toufool/AutoSplit](https://github.com/Toufool/AutoSplit)
