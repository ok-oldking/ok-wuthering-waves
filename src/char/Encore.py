from ok.logging.Logger import get_logger

from src.char.BaseChar import BaseChar

logger = get_logger(__name__)


class Encore(BaseChar):
    def do_perform(self):
        if self.has_intro:
            logger.info('Encore has_intro sleep')
        if self.has_intro and self.liberation_available():
            self.click_liberation()
            self.sleep(2)
            self.n4()
            self.click_resonance()
            self.n4()
            self.sleep(0.5)
        elif self.resonance_available():
            self.click_resonance()
            self.sleep(0.2)
        elif self.echo_available():
            self.click_echo()
            self.sleep(0.2)
            self.click_echo()
            self.sleep(0.2)
            self.click_echo()
            self.sleep(0.2)
        self.switch_next_char()

    def n4(self):
        self.normal_attack()
        self.sleep(.4)
        self.normal_attack()
        self.sleep(.4)
        self.normal_attack()
        self.sleep(.4)
        self.normal_attack()
        self.sleep(.4)
