from ok.logging.Logger import get_logger

from src.char.BaseChar import BaseChar

logger = get_logger(__name__)


class HavocRover(BaseChar):
    def do_perform(self):
        if self.resonance_available():
            logger.info(f'Use e')
            self.click_resonance()
            self.sleep(0.2)
        if self.is_forte_full() and self.liberation_available():
            logger.info(f'forte_full, and liberation_available, heavy attack')
            self.heavy_attack()
            self.sleep(0.2)
        if self.resonance_available():
            self.click_resonance()
            self.sleep(0.2)
        if self.liberation_available():
            self.click_liberation()
            self.sleep(2)
        if self.echo_available():
            self.click_echo()
            self.sleep(0.1)
        self.switch_next_char()
