import time

from src.char.BaseChar import BaseChar, Priority


class Jinhsi(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.incarnation = False

    def do_perform(self):
        if self.has_intro:
            self.incarnation = True
        if self.incarnation:
            if self.click_resonance()[0]:
                return self.switch_next_char()
        self.click_liberation()
        if self.click_echo():
            return self.switch_next_char()
        self.click_resonance()
        return self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro or self.incarnation:
            self.logger.info(f'switch priority max because has {has_intro}')
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 3

    def count_liberation_priority(self):
        return 0

    # def click_resonance(self):
    #     while True:
    #         current_resonance = self.current_resonance()
    #         if not self.resonance_available(current_resonance):
    #             break
    #         if current_resonance == 0:
    #             self.task.click(interval=0.1)
    #         else:
    #             self.send_resonance_key(interval=0.1)
    #
    def wait_resonance(self):
        while not self.resonance_available():
            self.task.click(interval=0.1)
            self.task.next_frame()

    def click_resonance(self, **args):
        # if self.incarnation:
        clicked, duration, animated = super().click_resonance(has_animation=True, send_click=False)
        self.logger.debug(f'click_resonance: {clicked}, {duration}')
        if duration > 1 and not animated:  # incarnation switch out
            start = time.time()
            self.logger.info(f'in incarnation click until e start {duration:.2f}')
            self.wait_resonance()
            self.logger.info(f'in incarnation click until e end {(time.time() - start):.2f}')
            clicked, duration, animated = super().click_resonance(has_animation=True, send_click=False)
            self.logger.info(f'in incarnation click until e animation {duration:.2f}')
        if animated:
            self.incarnation = False
        return clicked, duration, animated
        # while not self.resonance_available():
        #     self.task.click(interval=0.1)
        # self.send_resonance_key(interval=0.1)
        # animation_start = 0
        # while True:
        #     in_team = self.task.in_team()[0]
        #     if not in_team and animation_start == 0:
        #         animation_start = time.time()
        #     if animation_start != 0 and in_team:
        #         self.logger.info(
        #             f'incarnation e duration {time.time() - animation_start} has_intro {self.has_intro}')
        #         break
        #     if in_team and self.resonance_available():
        #         self.send_resonance_key(interval=0.1)
        #     self.task.next_frame()
