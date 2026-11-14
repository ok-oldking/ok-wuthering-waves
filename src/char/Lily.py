import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar


class Lily(BaseChar):
    """Finish the heavy channel and build Concerto before entering Slumberland."""

    FORTE_TIMEOUT = 10
    HEAVY_START_TIMEOUT = 2
    HEAVY_TIMEOUT = 6
    CONCERTO_TIMEOUT = 3

    def skip_combat_check(self):
        # Slumberland cannot lock on normally. Keep the short handoff alive
        # while its visible End control is present; switching restores checks.
        return self.in_slumberland()

    def do_perform(self):
        # Kit: https://ww.nanoka.cc/character/1512/ (E: 13s, Liberation: 25s).
        if self.has_intro:
            self.continues_normal_attack(0.8)
        if not self.in_slumberland():
            self.click_echo(time_out=0)
            self.build_forte()
            if self.is_mouse_forte_full() or self.is_forte_full():
                self.perform_heavy()
            can_liberate = self.task.use_liberation and self.liberation_available()
            self.fill_concerto(0.8 if can_liberate else 1)
            # Slumberland hides E/echo/normal attacks. Enter it only after the
            # heavy finisher, then pass the healing and Outro buffs to the team.
            liberated = self.click_liberation(wait_if_cd_ready=0, click_f=False)
            if can_liberate and not liberated:
                self.fill_concerto()
        self.switch_next_char()

    def fill_concerto(self, target=1):
        # Liberation supplies the last 20 Concerto. Without it, finish the ring
        # with E/normals before Sillage's six-second Outro window expires.
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.CONCERTO_TIMEOUT:
            self.cycle_start()
            if self.get_current_con() >= target:
                return True
            if not self.click_resonance(send_click=False, time_out=0.8)[0]:
                self.click(interval=0.1)
            self.cycle_sleep()
        self.logger.warning(f'Lily Concerto top-up timed out: target={target}')
        return False

    def build_forte(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.FORTE_TIMEOUT:
            self.cycle_start()
            if self.is_mouse_forte_full() or self.is_forte_full():
                return True
            if not self.click_resonance(send_click=False, time_out=0.8)[0]:
                self.click(interval=0.1)
            self.cycle_sleep()
        self.logger.warning('Lily Dream Perfume did not fill before timeout')
        return False

    def heavy_in_progress(self):
        # Ready and channeling share the same inner flower. The generic full
        # gauge prompt disappears when Dream Perfume has actually been consumed.
        return (not self.is_mouse_forte_full()
                and bool(self.task.find_one(Labels.lily_heavy, threshold=0.8)))

    def in_slumberland(self):
        return bool(self.task.find_one(Labels.lily_slumberland, threshold=0.8))

    def liberation_available(self, check_color=True):
        # Slumberland's Liberation button ends the state instead of casting it.
        return (not self.in_slumberland()
                and bool(self.task.find_one(Labels.lily_liberation, threshold=0.8))
                and super().liberation_available(check_color=check_color))

    def perform_heavy(self):
        self.check_combat()
        self.task.mouse_down()
        try:
            started = bool(self.task.wait_until(
                self.heavy_in_progress, time_out=self.HEAVY_START_TIMEOUT,
                pre_action=self.check_combat))
            if not started:
                self.logger.warning('Lily heavy channel did not start')
                return False
            finished = bool(self.task.wait_until(
                lambda: not self.heavy_in_progress(), time_out=self.HEAVY_TIMEOUT,
                settle_time=0.15, pre_action=self.check_combat))
        finally:
            self.task.mouse_up()
        if finished:
            # The prompt disappears at the start of the uninterruptible finisher.
            self.sleep(0.7)
            self.logger.info('Lily heavy finisher completed')
        else:
            self.logger.warning('Lily heavy channel did not finish before timeout')
        return finished
