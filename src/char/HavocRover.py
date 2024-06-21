from ok.logging.Logger import get_logger

from src.char.BaseChar import BaseChar

logger = get_logger(__name__)


class HavocRover(BaseChar):
    def do_perform(self):
        if self.is_forte_full() and self.liberation_available():
            logger.info(f'forte_full, and liberation_available, heavy attack')
            self.heavy_attack()
            self.sleep(0.4)
        self.click_resonance()
        self.click_liberation()
        self.click_echo()
        self.sleep(0.1)
        self.switch_next_char()
