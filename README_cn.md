<div align="center">
  <h1 align="center">
    <img src="icon.png" width="200"/>
    <br/>
    ok-ww
  </h1> 
<h3><i>基于图像识别的鸣潮自动化, 使用windows接口模拟用户点击, 无读取游戏内存或侵入修改游戏文件/数据.</i></h3>
</div>

![Static Badge](https://img.shields.io/badge/platfrom-Windows-blue?color=blue)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![GitHub all releases](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Static Badge](https://img.shields.io/badge/QQ%E7%BE%A4-970523295-purple)](https://qm.qq.com/q/ufUCrCEq6A)
[![Static Badge](https://img.shields.io/badge/Discord-blue?link=https%3A%2F%2Fdiscord.gg%2FZMHXx5QBuH)](https://discord.gg/Sy6etyCRed)

演示和教程 [![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/apalaRDDmVw)

# 免责声明

本软件是一个外部工具，旨在自动化鸣潮的游戏玩法。它仅通过现有用户界面与游戏交互，并遵守相关法律法规。该软件包旨在简化用户与游戏的交互，不会破坏游戏平衡或提供不公平优势，也不会修改任何游戏文件或代码。

本软件开源、免费，仅供个人学习交流使用，仅限于个人游戏账号，不得用于任何商业或营利性目的。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目及开发者团队无关。若您发现商家使用本软件进行代练并收费，这是商家的个人行为，本软件不授权用于代练服务，产生的问题及后果与本软件无关。本软件不授权任何人进行售卖，售卖的软件可能被加入恶意代码，导致游戏账号或电脑资料被盗，与本软件无关。

请注意，根据库洛的《鸣潮》公平运营声明:

```
严禁利用任何第三方工具破坏游戏体验。
我们将严厉打击使用外挂、加速器、作弊软件、宏脚本等违规工具的行为，这些行为包括但不限于自动挂机、技能加速、无敌模式、瞬移、修改游戏数据等操作。
一经查证，我们将视违规情况和次数，采取包括但不限于扣除违规收益、冻结或永久封禁游戏账号等措施。
```

### 使用说明

* 点击[releases](https://github.com/ok-oldking/ok-wuthering-waves/releases), 下载7z压缩包(80M左右的), 解压缩双击运行.exe
* 下载有问题的, 也可加入腾讯QQ频道，[OK-WW](https://pd.qq.com/s/2jhl3oogp) 问题答案: 老王同学OK
* QQ水群，只聊游戏, 不下载不讨论软件: [970523295](https://qm.qq.com/q/qMezq2IDGU) 问题答案: 老王同学OK

### 有多强?

1. 4K分辨率流畅运行,支持所有16:9分辨率,1600x900以上, 1280x720不支持是因为鸣潮bug, 它的1280x720并不是1280x720. 大多数功能也可以在21:9等宽屏分辨率运行
2. 可后台运行,可窗口化,可全屏,屏幕缩放比例无要求
3. 自动战斗比大多数玩家手操都强, 深渊可满星, 演示视频: [今汐12秒轴](https://www.bilibili.com/vi
4. 全角色自动识别，无需配置出招表，一键运行
5. 可后台自动静音游戏

### 出现问题请检查

有问题点这里, 挨个检查再提问:

1. GPU版本解压后5个G, 必须英伟达显卡更新最新驱动. CPU版本所有设备都支持
2. 下载前下载目录和解压目录添加杀毒软件白名单, 不要在QQ下载目录直接解压使用, 也不要在下载目录里直接解压使用,不要放在中文目录, 单独创建一个英文目录，重新解压
3. 关闭windows HDR, 护眼低蓝光模式, 高级管理器设置-自动管理应用颜色, 游戏使用默认亮度, 关闭显卡滤镜\锐化, 关闭游戏加加,
   小飞机等游戏上显示FPS,GPU等信息的浮层
4. 所有角色必须装备主声骸, 否则一直平A
5. 如果不是默认的QER按键, OK-WW设置里改键, 不支持鼠标侧键快捷键, 否则一直平A
6. OK-WW没更新最新版的, 更新最新版
7. 最低1280x720分辨率, 最好16:9分辨率. 部分功能也支持比16:9宽的分辨率, 如21:9
8. 必须要保证游戏能60fps稳定运行, 否则可能提前结束战斗,捡不到声骸, 如果不行, 尝试降低画质分辨率
9. 电脑配置好的, 打开配置里, 声骸文字识别. 如果打开后路过声骸不捡, 就关掉
10. 还有问题, 去BUG反馈, 录屏上传
11. 如果手动改过鸣潮或者鸣潮启动器的DPI设置, 重置
12. 游戏设置 开启镜头重置 保证鼠标中键可以回正视角

### Usage (Python Source Code)

Use Python 3.11, other versions might work but are not tested.

```
pip install -r requirements.txt #install python dependencies
python main.py # run the release version
python main_debug.py # run the debug version
python main_gpu_debug.py # run the gpu debug version
python main_gpu.py # run the gpu release version
```

### 致谢

[https://github.com/lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss) 后台点击代码
  
