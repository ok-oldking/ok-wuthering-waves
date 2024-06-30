from src.char.BaseChar import BaseChar


class Yinlin(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.sleep(0.4)
        liberation = self.click_liberation()
        if self.is_forte_full():
            if not self.has_intro and not liberation:
                self.normal_attack()
            self.heavy_attack()
            self.sleep(0.4)
        elif self.click_resonance(send_click=False)[0]:
            self.sleep(0.1)
        elif self.echo_available():
            echo_key = self.get_echo_key()
            self.sleep(0.1)
            self.task.send_key_down(echo_key)
            self.sleep(.6)
            return self.switch_next_char(post_action=self.echo_post_action)
        else:
            self.heavy_attack()
        self.switch_next_char()

    def count_base_priority(self):
        return 2

    def count_forte_priority(self):
        return 20

    def count_liberation_priority(self):
        return 0

    def count_echo_priority(self):
        return 1

    def echo_post_action(self):  # hold down the echo for 1 seconds and switch and then release the echo key
        self.task.send_key_up(self.get_echo_key())
        self.sleep(0.01)
