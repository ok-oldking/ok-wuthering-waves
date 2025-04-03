<div align="center">
  <h1 align="center">
    <img src="icon.png" width="200"/>
    <br/>
      ok-ww
  </h1> 
<h3><i>Automation for Wuthering Waves using computer vision and win32api</i></h3>
</div>

![Static Badge](https://img.shields.io/badge/platfrom-Windows-blue?color=blue)
[![GitHub release (with filter)](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![GitHub all releases](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Discord](https://img.shields.io/discord/296598043787132928?color=5865f2&label=%20Discord)](https://discord.gg/vVyCatEBgA)

### English Readme | [中文说明](README_cn.md)

![img.png](readme/img.png)
![img_1.png](readme/img_1.png)

## Key Features

* Works while the Game is in the Background
* Farm Boss Echo (Dreamless, Jue, and World Bosses)
* One Press Clear All Daily Tasks and Tacet Field
* Auto Combat in Abyss, Game World, Tacet Field, etc.
* Auto Skip Dialogs in Quests
* Auto Pick-up (Echos, Flowers, Chests)
* Supports All Game Languages (Most Features)

### Usage (Run from Compiled .exe)

* Download `ok-ww.7z` from the latest releases
* Extract and double-click the `ok-ww.exe`

### Usage (Run from Python Source Code)

Use Python 3.12, other versions might work but are not tested.

```
git clone https://github.com/ok-oldking/ok-wuthering-waves
pip install -r requirements.txt --upgrade #install python dependencies, you might need do run this again after updating the code
python main.py # run the release version
python main_debug.py # run the debug version
```

### Command Line Arguments

```
ok-ww.exe -t 1 -e
```

- `-t` or `--task` represents the task number to execute automatically upon startup. `1` means the first task, a
  one-click execution task.
- `-e` or `--exit` when added, indicates that the program should automatically exit after the task is completed.

### Must Set Game Settings

![image](https://github.com/user-attachments/assets/7d5f27b4-7b28-4471-bf7b-096dccd4ec4d)
![image](https://github.com/user-attachments/assets/66deba93-d0e7-41c0-985c-248deee9b8ff)

### FAQ

## Frequently Asked Questions (FAQ)

1. **Extraction Issues:** Extract the archive to a directory with only English characters.
2. **Antivirus Interference:** Add the download and extraction directories to your antivirus/Windows Defender whitelist.
3. **Display Settings:** Disable Windows HDR, eye protection modes, and automatic color management. Use default game
   brightness and disable external overlays (FPS, GPU info).
4. **Custom Keybinding:** If you are not using default keybindings, Set yours in the app settings, keys not in the
   settings are not supported.
5. **Outdated Version:** Ensure you are using the latest version of OK-GI.
6. **Performance:** Maintain a stable 60 FPS in the game, reduce resolution if needed.
7. **Disconnection** If you often got disconnected, try open the game first, and start playing 5 mins later, or when
   disconnected, don't close the game, and re-login.
8. **Further Assistance:** Submit a bug report if issues persist.

# Disclaimer

This software is an external tool designed to automate the gameplay of “Wuthering Waves.” It interacts with the game
solely through the existing user interface and complies with relevant laws and regulations. The package aims to simplify
user interaction with the game without disrupting game balance or providing any unfair advantages. It does not modify
any game files or code.

This software is open-source and free, intended solely for personal learning and communication purposes, and is limited
to personal game accounts. It is not allowed for any commercial or profit-making purposes. The development team reserves
the final interpretation rights of this project. Any issues arising from the use of this software are unrelated to the
project and the development team. If you find merchants using this software for paid boosting services, it is their
personal behavior, and this software is not authorized for boosting services. Any issues and consequences arising from
such use are unrelated to this software. This software is not authorized for sale, and any sold versions may contain
malicious code, leading to the theft of game accounts or computer data, which is unrelated to this software.

### Related Projects

* [ok-genshin-impact](https://github.com/ok-oldking/ok-genshin-impact) Genshin Impact Automation
* [ok-gf2](https://github.com/ok-oldking/ok-gf2) Girls Frontline 2 Automation(Simplified-Chinese Only)

### Credits

[https://github.com/lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss) 
[https://gitee.com/LanRenZhiNeng/ming-chao-ai](https://gitee.com/LanRenZhiNeng/ming-chao-ai)
  
