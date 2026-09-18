import sys

from src.startup import configure_game_bound_overlay, ensure_windows_admin


if __name__ == '__main__':
    if not ensure_windows_admin():
        sys.exit(0)
    configure_game_bound_overlay()

    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()
