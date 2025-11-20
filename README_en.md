<div align="center">
  <h1 align="center">
    <img src="icon.png" width="200" alt="ok-ww logo"/>
    <br/>
    ok-ww
  </h1> 
  
  <p>
    An image-recognition-based automation tool for Wuthering Waves, with background mode support, developed with <a href="https://github.com/ok-oldking/ok-script">ok-script</a>.
  </p>
  
  <p><i>Operates by simulating the Windows user interface, with no memory reading or file modification.</i></p>
</div>

<!-- Badges -->
<div align="center">
  
![Platform](https://img.shields.io/badge/platform-Windows-blue)
[![GitHub release](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Total Downloads](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Discord](https://img.shields.io/discord/296598043787132928?color=5865f2&label=%20Discord)](https://discord.gg/vVyCatEBgA)

</div>

**Demo & Tutorial:** [![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/h6P1KWjdnB4)

---

## ⚠️ Disclaimer

This software is an external auxiliary tool designed to automate parts of the Wuthering Waves gameplay. It interacts with the game solely by simulating standard user interface actions, in compliance with relevant laws and regulations. This project aims to simplify repetitive user tasks and does not disrupt game balance or provide an unfair advantage. It will never modify any game files or data.

This software is open-source and free, intended for personal learning and communication purposes only. Do not use it for any commercial or profit-making activities. The development team reserves the right of final interpretation. Any issues arising from the use of this software are not the responsibility of this project or its developers.

Please note, according to Kuro Games' official Fair Play Declaration for Wuthering Waves:
> The use of any third-party tools to disrupt the game experience is strictly prohibited.
> We will take strict measures against the use of unauthorized tools such as cheats, speed hacks, cheat software, and macro scripts. This includes, but is not limited to, automated farming, skill acceleration, god mode, teleportation, and modification of game data.
> Once verified, we will impose penalties based on the severity and frequency of the violation, including but not limited to deducting illicit gains, and suspending or permanently banning the game account.

**By using this software, you acknowledge that you have read, understood, and agreed to the above statement, and you voluntarily assume all potential risks.**

## 🚀 Quick Start

1.  **Download the Installer**: From the "Downloads" section below, download the latest `ok-ww-win32-setup.exe` installer file.
2.  **Install the Program**: Double-click the `ok-ww-win32-setup.exe` file and follow the on-screen instructions to complete the installation.
3.  **Run the Program**: After installation, launch `ok-ww` from the desktop shortcut or the Start Menu.

## 📥 Downloads

*   **[GitHub](https://github.com/ok-oldking/ok-wuthering-waves/releases)**: Official release page, fast access worldwide. (**Please download the `setup.exe` installer, not the `Source Code` archive**).

## ✨ Main Features
<img width="1778" height="1186" alt="QQ_1762961412161" src="https://github.com/user-attachments/assets/0109c68e-d714-4c34-b016-b4b45f9861fd" />

*   **High-Resolution Support**: Runs smoothly on all 16:9 resolutions up to 4K (minimum 1600x900). Some features are also compatible with ultrawide resolutions like 21:9.
*   **Background Mode**: Supports running in the background while the game window is minimized or obscured, allowing you to use your computer for other tasks.
*   **Intelligent Recognition**: Automatically recognizes all characters, eliminating the need for manual skill sequence configuration. Start with a single click.
*   **Auto-Mute**: Can automatically mute the game audio when running in the background.

## 🔧 Troubleshooting

If you encounter issues, please check the following steps one by one before asking for help:

1.  **Installation Path**: Ensure the software is installed in a path containing **only English characters** (e.g., `D:\Games\ok-ww`). Do not install it in `C:\Program Files` or folders with non-English characters.
2.  **Antivirus Software**: Add the software's installation directory to the **exceptions or whitelist** of your antivirus software (including Windows Defender) to prevent files from being mistakenly deleted or blocked.
3.  **Display Settings**:
    *   Turn off all graphics card filters (like NVIDIA Game Filter) and sharpening features.
    *   Use the game's default brightness settings.
    *   Disable any overlays that display information on the game screen (e.g., frame rates from MSI Afterburner, Fraps, etc.).
4.  **Custom Keybinds**: If you have changed the default in-game keybinds, you must update them accordingly in the `ok-ww` settings. Only the keybinds listed in the settings are supported.
5.  **Software Version**: Check and ensure you are using the latest version of `ok-ww`.
6.  **Game Performance**: Make sure the game can run stably at **60 FPS**. If the frame rate is unstable, try lowering the game's graphics quality or resolution.
7.  **Game Disconnections**: If you frequently get disconnected from the server, try launching the game manually and playing for 5 minutes before starting the tool. If you get disconnected, simply log back in without closing the game.
8.  **Getting Help**: If the steps above do not solve your problem, please submit a detailed bug report through our community channels.

---

## 💻 Developer Zone

### Running from Source (Python)

This project only supports Python 3.12.

```bash
# Install or update dependencies
pip install -r requirements.txt --upgrade

# Run Release version
python main.py

# Run Debug version
python main_debug.py
```

### Command-Line Arguments

You can use command-line arguments for automated startup.

```bash
# Example: Automatically run the first task after launch and exit the program upon completion
ok-ww.exe -t 1 -e
```

*   `-t` or `--task`: Automatically runs the Nth task in the list after launch. `1` represents the first task.
*   `-e` or `--exit`: Automatically exits the program after the task is completed.

## 💬 Join Us

This project is developed based on the [ok-script](https://github.com/ok-oldking/ok-script) framework. The core code is only about 3000 lines (Python), making it simple and easy to maintain. Developers interested in creating their own automation projects are welcome to use [ok-script](https://github.com/ok-oldking/ok-script).

## 🔗 Projects using ok-script:

*   Wuthering Waves: [https://github.com/ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
*   Genshin Impact (No longer maintained, but can still be used for auto-skipping dialogue in the background): [https://github.com/ok-oldking/ok-genshin-impact](https://github.com/ok-oldking/ok-genshin-impact)
*   Girls' Frontline 2: [https://github.com/ok-oldking/ok-gf2](https://github.com/ok-oldking/ok-gf2)
*   Honkai: Star Rail: [https://github.com/Shasnow/ok-starrailassistant](https://github.com/Shasnow/ok-starrailassistant)
*   Starsee: [https://github.com/Sanheiii/ok-star-resonance](https://github.com/Sanheiii/ok-star-resonance)
*   Duet Night Abyss: [https://github.com/BnanZ0/ok-duet-night-abyss](https://github.com/BnanZ0/ok-duet-night-abyss)
*   Ash Echoes (Updates stopped): [https://github.com/ok-oldking/ok-baijing](https://github.com/ok-oldking/ok-baijing)


## ❤️ Sponsors & Acknowledgements

### Sponsors
*   **EXE Signing**: Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

### Acknowledgements
*   [lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss)
*   [ok-oldking/OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
*   [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
*   [Toufool/AutoSplit](https://github.com/Toufool/AutoSplit)
