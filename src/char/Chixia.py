from src.char.BaseChar import BaseChar


class Chixia(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.bullets = 0

    # def do_perform(self):
    #     if self.resonance_available():
    #         if self.bullets > 35:
    #             self.task.send_key_down(self.get_resonance_key())
    #             self.sleep(3)
    #             self.click
    #         else:
    #             self.task.send_key_up(self.get_resonance_key())
    #     self.switch_next_char()
