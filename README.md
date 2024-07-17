# ![icon](icon.png)

## OK-WW
* Automation for Wuthering Waves using Computer Vision, Auto Combat
* 点击[releases](https://github.com/ok-oldking/ok-wuthering-waves/releases), 下载7z压缩包, 解压缩双击运行.exe
* 下载有问题的, 也可加入腾讯QQ频道，[OK-WW](https://pd.qq.com/s/2jhl3oogp)
* QQ水群，只聊游戏, 不下载不讨论软件: [970523295](https://qm.qq.com/q/qMezq2IDGU)


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


  
