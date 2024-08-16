from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        self.click_liberation()
        if self.click_resonance()[0]:
           self.task.mouse_down()
           self.sleep(0.7)
           self.task.mouse_up()
           self.sleep(0.3)
           return self.switch_next_char()
        if self.click_echo():
           return self.switch_next_char()

        self.task.mouse_down()
        self.sleep(.7)
        self.task.mouse_up()
        self.sleep(0.3)
        self.switch_next_char()
