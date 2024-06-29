import time

from src.char.BaseChar import BaseChar, Priority


class Jinhsi(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_free_intro = 0  # free intro every 25 sec
        self.has_free_intro = False
        self.incarnation = False

    def do_perform(self):
        if not self.has_intro and not self.incarnation:
            if self.click_echo():
                return self.switch_next_char()
        if self.has_intro:
            self.handle_incarnation()
            return self.switch_next_char()
        self.click_resonance()
        self.switch_next_char()

    def reset_state(self):
        super().reset_state()
        self.incarnation = False
        self.has_free_intro = False

    def switch_next_char(self, **args):
        super().switch_next_char(free_intro=self.has_free_intro, target_low_con=True)
        self.has_free_intro = False

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro or self.incarnation:
            self.logger.info(f'switch priority max because has_intro {has_intro} incarnation {self.incarnation}')
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 8

    def count_liberation_priority(self):
        return 0

    def handle_incarnation(self, **args):
        start = time.time()
        self.logger.info(f'handle_incarnation start')
        if self.task.debug:
            self.task.screenshot(f'handle_incarnation start')
        # if not self.resonance_available(check_ready=True):
        #     if self.task.debug:
        #         self.task.screenshot(f'handle_incarnation enter with cd, cast liberation and wait')
        #     self.click_liberation()
        #     self.logger.info(f'handle_incarnation enter with cd, cast liberation and wait')
        self.wait_resonance()
        self.send_resonance_key()
        self.sleep(0.1)
        if self.task.debug:
            self.task.screenshot(f'handle_incarnation wait_resonance done')
        self.continues_normal_attack(2.1)
        self.click_resonance()
        if self.task.debug:
            self.task.screenshot(f'handle_incarnation continues_normal_attack for 3a done')
        if self.task.debug:
            self.task.screenshot(f'handle_incarnation 2e done')
        while self.has_cd('resonance'):
            self.task.click(interval=0.1)
        if self.task.debug:
            self.task.screenshot(f'handle_incarnation 4a done')
        self.click_resonance(has_animation=True)
        self.logger.info(f'handle_incarnation cast final done {time.time() - start}')

    def wait_resonance(self):
        while not self.resonance_available(check_ready=True):
            self.send_resonance_key(interval=0.1)

    # def click_resonance(self, **args):
    #     # if self.incarnation:
    #     # if self.has_intro:
    #     #     self.incarnation = True
    #     if self.incarnation:
    #         self.logger.debug(f'wait_resonance because incarnation {self.incarnation}')
    #         self.wait_resonance()
    #     elif not self.resonance_available():
    #         return False, 0, False
    #     clicked, duration, animated = super().click_resonance(has_animation=True, send_click=False)
    #     self.logger.debug(f'click_resonance: {clicked}, {duration}')
    #     if duration > 1.2 and not animated:  # incarnation switch out
    #         self.incarnation = True
    #         # self.switch_next_char()
    #         # start = time.time()
    #         # self.logger.info(f'in incarnation click until e start {duration:.2f}')
    #         # self.wait_resonance()
    #         # self.logger.info(f'in incarnation click until e end {(time.time() - start):.2f}')
    #         # clicked, duration, animated = super().click_resonance(has_animation=True, send_click=False)
    #         # self.logger.info(f'in incarnation click until e animation {duration:.2f}')
    #     if animated:
    #         self.incarnation = False
    #         if time.time() - self.last_free_intro > 25:
    #             self.last_free_intro = time.time()
    #     return clicked, duration, animated
