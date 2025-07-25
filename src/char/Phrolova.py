import time

from src.char.BaseChar import BaseChar, Priority


class Phrolova(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_liberation = -1
        self.forte_white_color = {  # 用于检测共鸣回路UI元素可用状态的白色颜色范围。
        'r': (244, 255),  # Red range
        'g': (246, 255),  # Green range
        'b': (250, 255)  # Blue range
    }

    def skip_combat_check(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 2

    def do_perform(self):
        self.last_liberation = -1
        if self.has_intro:
            self.continues_normal_attack(0.5)
        if self.flying():
            self.wait_down()
        if self.click_liberation():
            return self.switch_next_char()
        elif self.heavy_click_forte():
            return self.switch_next_char()
        self.continues_normal_attack(3, click_resonance_if_ready_and_return=True)    
        self.click_echo()
        self.switch_next_char()
        
    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) < 24:
            return Priority.MIN
        return Priority.FAST_SWITCH
        #return super().do_get_switch_priority(current_char, has_intro)
        
    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        return not (self.flying() or self.has_cd('resonance'))

    def is_forte_full(self):
        """判断共鸣回路是否已充满/可用。

        Returns:
            bool: 如果充满/可用则返回 True。
        """
        box = self.task.box_of_screen_scaled(3840, 2160, 2281, 1993, 2341, 2016, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(self.forte_white_color, box)
        # num_labels, stats = get_connected_area_by_color(box.crop_frame(self.task.frame), forte_white_color,
        #                                                 connectivity=8)
        # total_area = 0
        # for i in range(1, num_labels):
        #     # Check if the connected co  mponent touches the border
        #     left, top, width, height, area = stats[i]
        #     total_area += area
        # white_percent = total_area / box.width / box.height
        # if self.task.debug:
        #     self.task.screenshot(f'{self}_forte_{white_percent}')
        # self.logger.debug(f'is_forte_full {white_percent}')
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        return white_percent > 0.08
    
    