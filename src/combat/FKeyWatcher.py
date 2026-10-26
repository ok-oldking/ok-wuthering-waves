import ctypes
import threading
import time

from ok import Logger

logger = Logger.get_logger(__name__)

VK_F = 0x46


class FKeyWatcher:
    """Remembers when the physical F key was last pressed while the game was in the foreground.

    Only the high bit of GetAsyncKeyState is read: the low bit is shared by the whole
    process and cleared on read. Keys sent by ok-ww through PostMessage do not change the
    async key state, so pickups and F breaks done by the script are never recorded.
    """

    def __init__(self, is_game_foreground, interval=0.05):
        self.is_game_foreground = is_game_foreground
        self.interval = interval
        self.last_press = 0.0
        self._was_down = False
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._watch, name='f_key_watcher', daemon=True)
            self._thread.start()

    def _watch(self):
        try:
            get_key_state = ctypes.windll.user32.GetAsyncKeyState
            get_key_state.restype = ctypes.c_short
        except Exception as e:
            logger.error('FKeyWatcher can not read the keyboard', e)
            return
        while True:
            self.on_sample(bool(get_key_state(VK_F) & 0x8000))
            time.sleep(self.interval)

    def on_sample(self, down):
        if down and not self._was_down and self._game_foreground():
            self.last_press = time.time()
            logger.debug('physical F pressed')
        self._was_down = down

    def _game_foreground(self):
        try:
            return self.is_game_foreground()
        except Exception:
            return False
