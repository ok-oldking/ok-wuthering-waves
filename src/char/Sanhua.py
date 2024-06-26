from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        if self.liberation_available():
            self.click_liberation()
        need_switch = False
        if self.resonance_available():
            self.click_resonance()
            need_switch = True
        if self.echo_available():
            self.click_echo()
            need_switch = True

        if not need_switch:
            self.task.mouse_down()
            self.sleep(.7)
            self.task.mouse_up()
            self.sleep(0.3)

        self.switch_next_char()
