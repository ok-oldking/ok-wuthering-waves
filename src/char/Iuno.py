import time

from src.char.BaseChar import BaseChar, Priority


class Iuno(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.priority = Priority.BASE + 1
        self.last_heavy = 0

    def do_perform(self):
        self.wait_down()
        self.do_everything()
        self.switch_next_char()

    def do_everything(self, time_out=1.5):
        if self.has_intro:
            time_out += 4
        start = time.time()
        last_action = "click"
        self.click_echo()
        c6_performed = False
        jumped = False
        while time.time() - float(start) < time_out:
            self.check_combat()
            heavy_success = False
            while self.time_elapsed_accounting_for_freeze(
                    self.last_heavy) > 20 and self.task.find_feature("iuno_heavy",
                                                                     box="box_extra_action",
                                                                     threshold=0.6):
                self.sleep(0.05)
                self.heavy_attack()
                self.sleep(0.05)
                heavy_success = True
            if heavy_success:
                self.last_heavy = time.time()
                if not c6_performed and self.task.char_config.get("Iuno C6"):
                    c6_performed = True
                    start = time.time()
                    time_out = 5
                    self.logger.debug('iuno c6 continue')
                else:
                    return True
            if not jumped and self.task.find_feature("iuno_jump", box="box_extra_action", threshold=0.6):
                while self.task.find_feature("iuno_jump", box="box_extra_action", threshold=0.6):
                    self.task.send_key('space', after_sleep=0.1)
                time_out += 3
                jumped = True
                if self.has_intro:
                    continue
                else:
                    return
            if self.time_elapsed_accounting_for_freeze(
                    self.last_liberation) > 20 and self.click_liberation(
                wait_if_cd_ready=0):
                start = time.time()
                time_out = 3
                continue
            if last_action == "click":
                last_action = "resonance"
                self.send_resonance_key(post_sleep=0.1)
            else:
                last_action = "click"
                self.click(after_sleep=0.1)
