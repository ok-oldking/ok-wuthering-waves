import time

from src.char.BaseChar import BaseChar, Priority


class Jinhsi(BaseChar):

    def __init__(self, *args):
        super().__init__(*args)
        self.last_free_intro = 0  # free intro every 25 sec
        self.has_free_intro = False
        self.incarnation = False
        self.incarnation_cd = False
        self.last_fly_e_time = time.time()

    def do_perform(self):
        if self.incarnation:
            self.handle_incarnation()
            return self.switch_next_char()
        elif self.has_intro or self.incarnation_cd:
            self.handle_intro()
            return self.switch_next_char()
        if self.time_elapsed_accounting_for_freeze(self.task.combat_start) < 5:
            self.click_liberation()
        self.click_echo()
        return self.switch_next_char()

    def reset_state(self):
        super().reset_state()
        self.incarnation = False
        self.has_free_intro = False
        self.incarnation_cd = False

    def switch_next_char(self, **args):
        super().switch_next_char(free_intro=self.has_free_intro, target_low_con=True)
        self.has_free_intro = False

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False):
        if has_intro or self.incarnation or self.incarnation_cd:
            self.logger.info(
                f'switch priority max because has_intro {has_intro} incarnation {self.incarnation} incarnation_cd {self.incarnation_cd}')
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def count_base_priority(self):
        return 0

    def count_resonance_priority(self):
        return 0

    def count_echo_priority(self):
        return 0

    def count_liberation_priority(self):
        return 0

    def handle_incarnation(self):
        self.incarnation = False
        self.logger.info(f'handle_incarnation click_resonance start')
        start = time.time()
        while True:
            current_res = self.current_resonance()
            if current_res > 0 and not self.has_cd('resonance'):
                self.logger.info(f'handle_incarnation current_res: {current_res} breaking')
                if self.task.debug:
                    self.task.screenshot(f'handle_incarnation e available')
                # self.send_resonance_key()
                break
            self.task.click(interval=0.1)
            self.check_combat()

        self.click_resonance(has_animation=True, animation_min_duration=1)
        if not self.click_echo():
            self.task.click()
        # if self.task.debug:
        #     self.task.screenshot(f'handle_incarnation click_resonance end {time.time() - start}')
        self.logger.info(f'handle_incarnation  click_resonance end {time.time() - start}')

    def handle_intro(self):
        # self.task.screenshot(f'handle_intro start')
        self.logger.info(f'handle_intro  start')
        start = time.time()
        while not self.has_cd('resonance'):
            self.send_resonance_key(interval=0.1)
            self.check_combat()
        if time.time() - start < 1.2:
            self.logger.info(f'handle_intro fly e in_cd {time.time() - start}')
            self.incarnation_cd = True
            if not self.click_echo():
                self.task.click()
            return
        self.last_fly_e_time = start
        if self.click_liberation(send_click=True):
            self.continues_normal_attack(0.3)
        else:
            self.continues_normal_attack(1.4)
        # self.task.screenshot(f'handle_intro end {time.time() - start}')
        self.logger.info(f'handle_intro end {time.time() - start}')
        self.incarnation = True
        self.incarnation_cd = False

    def wait_resonance(self):
        while not self.resonance_available(check_ready=True):
            self.send_resonance_key(interval=0.1)
