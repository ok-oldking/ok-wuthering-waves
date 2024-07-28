#  OK-WW
![Static Badge](https://img.shields.io/badge/platfrom-Windows-blue?color=blue)
![GitHub release (with filter)](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)
![GitHub all releases](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)
![Static Badge](https://img.shields.io/badge/QQ%E7%BE%A4-970523295-purple)

# 免责声明
本软件是一个外部工具，旨在自动化鸣潮的游戏玩法。它仅通过现有用户界面与游戏交互，并遵守相关法律法规。该软件包旨在简化用户与游戏的交互，不会破坏游戏平衡或提供不公平优势，也不会修改任何游戏文件或代码。

本软件开源、免费，仅供个人学习交流使用，仅限于个人游戏账号，不得用于任何商业或营利性目的。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目及开发者团队无关。若您发现商家使用本软件进行代练并收费，这是商家的个人行为，本软件不授权用于代练服务，产生的问题及后果与本软件无关。本软件不授权任何人进行售卖，售卖的软件可能被加入恶意代码，导致游戏账号或电脑资料被盗，与本软件无关。

This software is an external tool designed to automate the gameplay of “鸣潮”. It interacts with the game solely through the existing user interface and complies with relevant laws and regulations. The package aims to simplify user interaction with the game without disrupting game balance or providing any unfair advantages. It does not modify any game files or code.

This software is open-source and free, intended solely for personal learning and communication purposes, and is limited to personal game accounts. It is not allowed for any commercial or profit-making purposes. The development team reserves the final interpretation rights of this project. Any issues arising from the use of this software are unrelated to the project and the development team. If you find merchants using this software for paid boosting services, it is their personal behavior, and this software is not authorized for boosting services. Any issues and consequences arising from such use are unrelated to this software. This software is not authorized for sale, and any sold versions may contain malicious code, leading to the theft of game accounts or computer data, which is unrelated to this software.

请注意，根据库洛的《鸣潮》公平运营声明:

```
严禁利用任何第三方工具破坏游戏体验。
我们将严厉打击使用外挂、加速器、作弊软件、宏脚本等违规工具的行为，这些行为包括但不限于自动挂机、技能加速、无敌模式、瞬移、修改游戏数据等操作。
一经查证，我们将视违规情况和次数，采取包括但不限于扣除违规收益、冻结或永久封禁游戏账号等措施。
```

### 使用说明

* Automation for Wuthering Waves using Computer Vision, Auto Combat
* 点击[releases](https://github.com/ok-oldking/ok-wuthering-waves/releases), 下载7z压缩包(80M左右的), 解压缩双击运行.exe
* 下载有问题的, 也可加入腾讯QQ频道，[OK-WW](https://pd.qq.com/s/2jhl3oogp) 问题答案: 老王同学OK
* QQ水群，只聊游戏, 不下载不讨论软件: [970523295](https://qm.qq.com/q/qMezq2IDGU) 问题答案: 老王同学OK
* [出现问题先查看,常见问题](readme/faq.md)

### 有多强?

1. 4K分辨率流畅运行,支持所有16:9分辨率,1600x900以上, 1280x720不支持是因为鸣潮bug, 它的1280x720并不是1280x720
2. 可后台运行,可窗口化,可全屏,屏幕缩放比例无要求
3. 自动战斗比大多数玩家手操都强, 深渊可满星, 演示视频: [今汐12秒轴](https://www.bilibili.com/video/BV1Hx4y1t7NP/)
4. 无需安装Cuda之类, 基本不占用显卡资源, 性能优化到支持自动战斗10毫秒左右的响应时间
5. 可高度自定义角色出招逻辑(动态合轴) [角色列表](src/char)

### 出现问题请检查

1. 关闭windows HDR, 护眼低蓝光模式, 游戏使用默认亮度, 关闭显卡滤镜，等一切改变游戏颜色的功能
2. 所有角色必须装备主声骸, 暂时不支持卡卡罗, 会跳出战斗
3. 把下载目录和解压目录, 添加到杀毒软件白名单.
4. 不要直接解压在QQ下载文件夹里运行, 不要放中文目录
5. OK-WW没更新最新版的, 更新最新版
6. 如果手动改过鸣潮或者鸣潮启动器的DPI设置, 重置
7. 最好升级Win10最新版(至少版本20348以上)或者Win11

Demonstration: [https://youtu.be/N32I1aMfdqQ](https://youtu.be/N32I1aMfdqQ)

* Farm Boss Echo (Dreamless, Jue and World Bosses)
* Auto Combat (Beats 90% players for [Fully Supported Characters](src/char))
* Auto Skip Dialogs in Quests
* Supports All Game Languages
  ![img.png](readme/img.png)

### How to Run

* Download the 7z from [releases](https://github.com/ok-oldking/ok-wuthering-waves/releases), extract and run the exe
* May need to add the app folder to Windows Defender white list.
* Game must be a 16:9 ratio like 1920x1080, 3840x2160, lowest supported resolution is 1600*900
* Can run while game is in background, but not minimized

### Development

use Python 3.11, other versions might work but not tested

```
pip install -r requirements.txt
python main_debug.py
```

the images assets was generated using this [roboflow project](https://app.roboflow.com/test-7ruyi/ww-jamcc)

### 致谢

[https://github.com/lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss) 后台点击代码
  
