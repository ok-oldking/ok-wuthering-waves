import math
import sys

from ok import TriggerTask, Logger
from src.macos_capabilities import MacTaskUnsupportedError, get_macos_task_compatibility
from src.macos_game_integration import uses_macos_provider

logger = Logger.get_logger(__name__)


class MouseResetTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': sys.platform != 'darwin'}
        self.trigger_interval = 10
        self.name = "🖱️ Prevent Wuthering Waves from moving the mouse"
        self.description = "Turn on if you mouse jumps around"
        self.mouse_pos = None
        self._unavailable_logged = False

    def on_create(self):
        super().on_create()
        if sys.platform == 'darwin':
            # Ignore an old enabled preference on an unsupported platform.
            # Preserve the persisted preference for a later Windows launch.
            if self._enabled:
                logger.info('MouseResetTask is unsupported on macOS; not enabling saved preference')
            self._enabled = False

    def get_macos_compatibility(self):
        return get_macos_task_compatibility(self)

    def _uses_macos_provider(self) -> bool:
        return uses_macos_provider(self)

    def get_device_compatibility_state(self) -> dict:
        if self._uses_macos_provider():
            compatibility = self.get_macos_compatibility()
            return {
                'status': 'unsupported',
                'level': None,
                'missing': (),
                'reason': compatibility.note,
            }
        return super().get_device_compatibility_state()

    def ensure_device_capabilities(self) -> None:
        if self._uses_macos_provider():
            compatibility = self.get_macos_compatibility()
            raise MacTaskUnsupportedError(self.name, compatibility)
        super().ensure_device_capabilities()

    def enable(self):
        super().enable()
        self.run()

    def run(self):
        if not self.enabled or self.is_browser():
            return
        cursor_service = self.cursor_service()
        if cursor_service is None or not cursor_service.available:
            if not self._unavailable_logged:
                logger.info('Mouse reset is unavailable because no cursor service is active')
                self._unavailable_logged = True
            return False
        self._unavailable_logged = False
        logger.debug('schedule mouse reset')
        self.post_mouse_reset(0.01)
        return True

    def cursor_service(self):
        device_manager = getattr(self.executor, 'device_manager', None)
        return getattr(device_manager, 'cursor_service', None)

    def post_mouse_reset(self, delay):
        if self.enabled:
            self.handler.post(self.mouse_reset, delay, remove_existing=True)

    def mouse_reset(self):
        if not self.enabled or self.is_browser():
            return
        try:
            cursor_service = self.cursor_service()
            if cursor_service is None or not cursor_service.available:
                return False
            current_position = cursor_service.get_position()
            if self.mouse_pos and self.hwnd and self.hwnd.exists and not self.hwnd.visible and self.executor.interaction and self.executor.interaction.capture:
                center_pos = self.executor.interaction.capture.get_abs_cords(self.width_of_screen(0.5),
                                                                             self.height_of_screen(0.5))
                close_to_center = math.sqrt(
                    (current_position[0] - center_pos[0]) ** 2
                    + (current_position[1] - center_pos[1]) ** 2
                ) < 50
                distance = math.sqrt(
                    (current_position[0] - self.mouse_pos[0]) ** 2
                    + (current_position[1] - self.mouse_pos[1]) ** 2
                )
                if distance > 200 and close_to_center:
                    logger.info(f'move mouse back {self.mouse_pos}')
                    cursor_service.set_position(self.mouse_pos)
                    self.mouse_pos = self.mouse_pos
                    self.post_mouse_reset(1)
                    return
            self.mouse_pos = current_position
            self.post_mouse_reset(0.002)
        except Exception as e:
            logger.error('mouse_reset exception', e)
