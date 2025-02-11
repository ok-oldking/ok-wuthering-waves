import time

from src.char.BaseChar import BaseChar, Priority


class Roccia(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.plunge_count = 0
        self.last_e = 0
        self.last_intro = 0


    def do_perform(self):
        if self.has_intro:
            self.heavy_attack(1.6)
            self.sleep(0.2)
            self.last_e = time.time()
            self.last_intro = time.time()
            return self.switch_next_char()
        # self.wait_intro(time_out=1.4, click=True)
        if self.liberation_available() and self.resonance_available(check_cd=True) and self.is_forte_full():
            self.click_liberation()
            self.task.wait_until(self.resonance_available, time_out=4, post_action=self.click_with_interval,
                                 wait_until_before_delay=0, wait_until_check_delay=0)
        if self.click_resonance(check_cd=True)[0]:
            self.last_e = time.time()
        self.click()
        self.switch_next_char()

    # def switch_next_char(self, *args):
    #     # self.click(interval=0.2)
    #     # while time.time() - self.last_perform < 1.1:
    #     #     self.click(interval=0.2)
    #     self.click()
    #     # if self.plunge_count == 0:
    #     #     self.plunge_count = self.get_plunge_count()
    #     # self.logger.debug('wait plunge count: {}'.format(self.plunge_count))
    #     # post_action = self.use_t_action if self.is_con_full() else None
    #     return super().switch_next_char(*args)

    def use_t_action(self):
        self.task.send_key('t')
        self.sleep(0.01)

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if time.time() - self.last_intro < 4 and has_intro:
            return Priority.MIN + 1
        if time.time() - self.last_e < 4 and not has_intro:
            self.logger.info(
                f'switch priority max because plunge count is {self.plunge_count}')
            return Priority.MAX - 1
        else:
            return super().do_get_switch_priority(current_char, has_intro, target_low_con)

    def get_plunge_count(self):
        count = 0
        if self.is_color_ok('box_forte_1'):
            count += 1
        if self.is_color_ok('box_forte_2'):
            count += 1
        if self.is_color_ok('box_forte_3'):
            count += 1
        return count

    def is_color_ok(self, box):
        purple_percent = self.task.calculate_color_percentage(forte_purple_color, self.task.get_box_by_name(box))
        self.logger.debug(f'purple percent: {box} {purple_percent}')
        if purple_percent > 0.16:
            return True

    # def plunge(self, starting_count=3):
    #     start = time.time()
    #     while self.is_forte_full() and time.time() - start < 0.4:
    #         # plunge_count = self.get_plunge_count()
    #         # if plunge_count > 0:
    #         #     starting_count = plunge_count - 1
    #         # elif  starting_count > 1:
    #         self.click(interval=0.1)
    #         # if self.get_plunge_count() == 1:
    #         #     break
    #     self.plunge_count = 0
    #     self.logger.debug(f'plunge ended after: {time.time() - start} {self.get_plunge_count()}  {self.is_forte_full()}')
    #     return True

    def c6_continues_plunge(self):
        start = time.time()
        # has_charge = self.is_forte_full()
        while time.time() - start < 11:
            self.click(interval=0.1)
        return True


forte_purple_color = {
    'r': (70, 105),  # Red range
    'g': (30, 65),  # Green range
    'b': (160, 235)  # Blue range
}