import time

from src.char.BaseChar import BaseChar, Priority


class Aemeath(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.33)
            self.f_break()
            if self.click_liberation():
                self.perform_under_liber() 
                return self.switch_next_char()
        elif self.flying():
            self.wait_down()
        self.click_echo(time_out=0)
        self.continues_normal_attack(1)
        self.task.wait_until(
            lambda: False, post_action=self.send_resonance_key, time_out=0.2
        )
        self.switch_next_char()

    def perform_under_liber(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 18:
            if self.click_liberation():
                return
            if self.check_heavy():
                self.heavy_attack(0.8)
            elif self.is_forte_full():
                if not self.handle_resonance():
                    return
            self.click()
            self.check_combat()
            self.task.next_frame()

    def handle_resonance(self):
        start = time.time()
        animation_start = 0
        last_op = "resonance"
        self.task.in_liberation = True
        while True:
            if time.time() - start > 6:
                self.logger.info(f"handle resonance too long")
                break
            if self.task.in_team()[0]:
                if last_op == "resonance":
                    self.task.click(interval=0.1)
                    last_op = "click"
                else:
                    self.send_resonance_key()
                    last_op = "resonance"
                if animation_start != 0:
                    break
            else:
                if animation_start == 0:
                    animation_start = time.time()
                self.task.in_liberation = True
            self.check_combat()
            self.task.next_frame()
        self.task.in_liberation = False
        self.add_freeze_duration(animation_start)
        self.logger.info(f"handle_resonance end {time.time() - start}")
        if time.time() - start > 4:
            self.logger.info("maybe using the liber2")
            return False
        return True

    def do_get_switch_priority(
        self, current_char: BaseChar, has_intro=False, target_low_con=False
    ):
        if has_intro:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)

    def check_heavy(self):
        if not self.task.in_team_and_world():
            return False
        best = self.task.find_best_match_in_box(
            self.task.get_box_by_name("box_target_enemy_long"),
            ["has_target", "no_target"],
            threshold=0.6,
        )
        self.logger.debug(f"check res {best}")
        return best
