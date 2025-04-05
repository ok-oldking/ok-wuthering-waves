import time

from src.char.BaseChar import BaseChar, Priority


class Roccia(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plunge_count = 0
        self.last_e = 0
        self.last_intro = 0
        self.can_plunge = False

    def do_perform(self):
        if self.has_intro:
            if self.liberation_available() and self.resonance_available():
                self.click_liberation()
                self.click_resonance()
                self.click_echo()
            else:
                self.heavy_attack(1.6)
                self.sleep(0.2)
                self.last_e = time.time()
                self.last_intro = time.time()
                self.can_plunge = True
            return self.switch_next_char()
        liberated = self.click_liberation()
        if self.click_resonance()[0]:
            self.last_e = time.time()
            self.can_plunge = True
            return self.switch_next_char()
        if not liberated:
            self.plunge()
        if not self.click_resonance()[0]:
            self.click_echo()
        self.switch_next_char()

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        super().switch_next_char(post_action=self.update_tool_box, free_intro=free_intro,
                                       target_low_con=target_low_con)

    def update_tool_box(self, next_char, has_intro):
        if has_intro:
            next_char.has_tool_box = True

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        return Priority.MAX - 1

    def get_plunge_count(self):
        count = 0
        boxes = []
        if self.is_color_ok('box_forte_1'):
            count = 1
            boxes.append(0)
        if self.is_color_ok('box_forte_2'):
            count = 2
            boxes.append(1)
        if self.is_color_ok('box_forte_3'):
            count = 3
            boxes.append(2)
        self.logger.debug(f'get plunge count: {count}, {boxes}')
        return count

    def is_color_ok(self, box):
        purple_percent = self.task.calculate_color_percentage(forte_purple_color, self.task.get_box_by_name(box))
        self.logger.debug(f'purple percent: {box} {purple_percent}')
        if purple_percent > 0.1:
            return True

    def plunge(self):
        start = time.time()
        starting_count = 0
        while (self.is_forte_full() and time.time() - start < 1.1) or (starting_count > 0 and time.time() - start < 5):
            self.click(interval=0.1)
            if starting_count == 0:
                starting_count = self.get_plunge_count()
            if starting_count > 0 and not self.is_forte_full():
                self.can_plunge = False
                break
            self.task.next_frame()
        self.plunge_count = 0
        # self.logger.debug(f'plunge ended after: {time.time() - start} {self.get_plunge_count()}  {self.is_forte_full()}')
        return True

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