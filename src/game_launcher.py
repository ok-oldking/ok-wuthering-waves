from ok import og
from ok.util.process import WINDOWS_START_METHOD_START, execute


def execute_game(game_cmd, arguments=None, start_method=WINDOWS_START_METHOD_START):
    package = og.global_config.get_config('Basic Options').get('Game Package', 'hd')
    arguments = f'{arguments or ""} -krqlv={package}'.strip()
    return execute(game_cmd, arguments=arguments, start_method=start_method)


def install_game_launcher():
    # ok-script currently exposes no callback for custom launch arguments.
    # Limit the adapter to game startup, preserving its DX11 and launch method handling.
    from ok.core import start_controller

    start_controller.execute = execute_game
