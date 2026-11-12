import base64
import json
from pathlib import Path

from ok import Logger, og
from ok.core.notifications import alert_error

logger = Logger.get_logger(__name__)
GAME_PACKAGES = ('sd', 'hd', 'uhd')
GAME_ASSETS_QUALITY_ERROR = 'Failed to read game assets quality config. Starting with HD assets.'


def _read_launcher_config(path, encoded=False):
    try:
        data = path.read_bytes()
        if encoded:
            # Kuro's launcher stores its UI state as Base64 with an XOR mask.
            data = bytes(value ^ 0x63 for value in base64.b64decode(data, validate=True))
        config = json.loads(data.decode('utf-8-sig'))
        return config if isinstance(config, dict) else {}
    except (OSError, ValueError, UnicodeError) as error:
        logger.debug(f'Could not read launcher config {path}: {error}')
        return {}


def detect_game_package(game_exe_path):
    """Read the selected Wuthering Waves bundle from this installation's launcher."""
    game_folder = Path(game_exe_path).parent
    state = _read_launcher_config(
        game_folder.parent / 'kr_game_cache' / 'platform_ui_state.bin', encoded=True,
    )
    active = state.get('activeGameScope')
    recent_games = state.get('recentGames')
    recent = recent_games.get('Aki') if isinstance(recent_games, dict) else None
    for scope in (active, recent):
        if not isinstance(scope, dict):
            continue
        if scope is active and scope.get('gameIdentity') != 'Aki':
            continue
        package = scope.get('bundleName')
        if isinstance(package, str) and package.lower() in GAME_PACKAGES:
            return package.lower()

    # A download manifest can identify the package only when it is unambiguous.
    manifest = _read_launcher_config(game_folder / 'launcherDownloadConfig.json')
    bundles = manifest.get('bundles')
    if isinstance(bundles, dict):
        packages = {name.lower() for name in bundles if name.lower() in GAME_PACKAGES}
        if len(packages) == 1:
            return packages.pop()
    return None


def get_game_launch_arguments():
    """Detect the launcher selection on each launch, alerting and using HD on failure."""
    device_manager = getattr(og, 'device_manager', None)
    if device_manager is not None:
        device = device_manager.get_preferred_device()
        if device and device.get('device') == 'windows':
            game_exe_path = device_manager.get_exe_path(device)
            if game_exe_path and (package := detect_game_package(game_exe_path)):
                logger.info(f'Detected game package {package} from launcher config')
                return f'-krqlv={package}'
    logger.warning(GAME_ASSETS_QUALITY_ERROR)
    app = getattr(og, 'app', None)
    message = app.tr(GAME_ASSETS_QUALITY_ERROR) if app is not None else GAME_ASSETS_QUALITY_ERROR
    alert_error(message, tray=True)
    return '-krqlv=hd'
