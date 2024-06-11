from src.char.BaseChar import BaseChar


class Yinlin(BaseChar):
    def perform(self):
        if self.resonance_available():
            self.click_resonance()
            self.sleep(0.4)
            self.click_resonance()
            self.sleep(.6)
            self.switch_next_char()
        elif self.echo_available():
            echo_key = self.get_echo_key()
            self.task.send_key_down(echo_key)
            self.sleep(1)
            self.switch_next_char(post_action=self.echo_post_action)
        else:
            self.sleep(0.5)
            self.switch_next_char()

    def echo_post_action(self):  # hold down the echo for 1 seconds and switch and then release the echo key
        self.task.send_key_up(self.get_echo_key())
        self.sleep(0.01)
