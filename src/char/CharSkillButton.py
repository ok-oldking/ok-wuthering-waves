import time

import cv2

from ok.logging.Logger import get_logger

logger = get_logger(__name__)


class CharSkillButton:

    def __init__(self, name, task, t, white_limit=1, white_hints=[]):
        self.name = name
        self.type = t
        if not white_limit:
            white_limit = 1
        self.white_limit = white_limit
        self.white_hints = white_hints
        self.task = task
        self.white_list = []
        self.white_off_percent = 0.01

    # def is_available(self, percent):
    #     if percent == 0:
    #         return True
    #     for base in self.white_list:
    #         if abs(base - percent) < self.white_off_percent:
    #             return True
    #     if len(self.white_list) == self.white_limit:
    #         return False
    #     for white_hint in self.white_hints:
    #         if abs(percent - white_hint) < self.white_off_percent:
    #             logger.info(f'{self.name} set base {self.type} to {percent:.4f} by white_hint {white_hint}')
    #             self.white_list.append(percent)
    #             return True
    #     cd_text = self.task.ocr(box=self.task.get_box_by_name(f'box_{self.type}'), target_height=540, threshold=0.9)
    #     if len(cd_text) == 0 or all(not is_float(text.name) for text in cd_text):
    #         self.white_list.append(percent)
    #         if self.task.debug:
    #             self.task.screenshot(f'{self.name}_{self.type}_{percent:.4f}')
    #         logger.info(
    #             f' set base {self.name}_{self.type} to {percent:.4f} by ocr {self.white_list} {self.white_limit} {cd_text}')
    #         return True
    #     if cd_text:
    #         logger.info(f'{self.name} set base {self.type} to has text {cd_text}')
    #         return False

    def is_available(self, percent):
        if percent == 0:
            return True
        start = time.time()
        box = self.task.get_box_by_name(f'box_{self.type}')
        box = box.copy(x_offset=box.width / 4, y_offset=box.height * 0.6, width_offset=-box.width / 2,
                       height_offset=-box.height * 0.5)
        dot = self.task.find_one('edge_echo_cd_dot', box=box, canny_lower=40, canny_higher=80, threshold=0.6)
        # if self.task.debug:
        #     colored = cv2.cvtColor(self.boss_lv_edge, cv2.COLOR_GRAY2BGR)
        #     self.frame[self.boss_lv_box.y:self.boss_lv_box.y + self.boss_lv_box.height,
        #     self.boss_lv_box.x:self.boss_lv_box.x + self.boss_lv_box.width] = cv2.cvtColor(current,
        #                                                                                    cv2.COLOR_GRAY2BGR)
        if dot is None:
            logger.debug(f'find dot not exist cost : {time.time() - start}')
            return True
        else:
            logger.debug(f'find dot exist cost : {time.time() - start} {dot}')
            return False


def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


if __name__ == '__main__':
    image = cv2.imread(
        'assets\\images\\154eb284-17_01_16_406889_WindowsGraphicsCaptureMethod_3840x2160_title_None_Clie_6yGu616.png',
        cv2.IMREAD_GRAYSCALE)  # Load in grayscale

    # Apply Canny edge detection
    edges = cv2.Canny(image, 40, 80)

    # Save the result
    cv2.imwrite('edges.jpg', edges)
