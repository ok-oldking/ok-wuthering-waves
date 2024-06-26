from ok.logging.Logger import get_logger

from src.char.BaseChar import BaseChar

logger = get_logger(__name__)


class HavocRover(BaseChar):
    def do_perform(self):
        if self.is_forte_full() and self.liberation_available():
            logger.info(f'forte_full, and liberation_available, heavy attack')
            self.wait_down()
            self.heavy_attack()
            self.sleep(0.4)
        self.click_liberation()
        if not self.click_resonance():
            self.click_echo()
        self.switch_next_char()
