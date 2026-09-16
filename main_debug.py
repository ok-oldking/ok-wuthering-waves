import os
import ctypes
import json
import sys
from pathlib import Path

os.environ["PYAPPIFY_PYTHON_TEST"] = "1"


def ensure_windows_admin():
    """Relaunch the source debug client at the game's privilege level on Windows."""
    if os.name != "nt" or ctypes.windll.shell32.IsUserAnAdmin():
        return True

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        f'"{os.path.abspath(__file__)}"',
        os.path.dirname(os.path.abspath(__file__)),
        1,
    )
    if result <= 32:
        raise RuntimeError("Administrator permission is required to control the game window.")
    return False


def sync_debug_overlay_setting():
    """Keep the framework overlay setting aligned with the Settings-page switch."""
    config_folder = Path(__file__).resolve().parent / "configs"
    overlay_config_path = config_folder / "Development Overlay.json"
    ok_config_path = config_folder / "_ok.json"
    try:
        overlay_config = json.loads(overlay_config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        overlay_config = {"Show Game Overlay": True}
    try:
        ok_config = json.loads(ok_config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        ok_config = {}

    show_custom_content = overlay_config.get(
        "Show Custom Overlay Content", overlay_config.get("Show Game Overlay", True)
    )
    show_debug_boxes = overlay_config.get("Show Debug Boxes", False)
    # Keep a transparent native overlay available even while both switches are
    # off.  Otherwise switching custom HUD content on would require a restart
    # because ok-script only creates the overlay during application startup.
    ok_config["use_overlay"] = True
    config_folder.mkdir(exist_ok=True)
    ok_config_path.write_text(json.dumps(ok_config, ensure_ascii=False, indent=4), encoding="utf-8")


if __name__ == '__main__':
    if not ensure_windows_admin():
        sys.exit(0)

    sync_debug_overlay_setting()

    from config import config
    from ok import OK

    config = config
    config['debug'] = True
    # config['click_screenshots_folder'] = "click_screenshots"  # debug用 点击后截图文件夹]
    ok = OK(config)
    ok.start()
