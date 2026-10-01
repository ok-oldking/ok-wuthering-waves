from ok import og


def get_game_launch_arguments():
    """Read the selected game package each time the game is launched."""
    package = og.global_config.get_config('Basic Options').get('Game Package', 'hd')
    return f'-krqlv={package}'
