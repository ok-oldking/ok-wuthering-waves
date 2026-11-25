import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Lily(BaseChar):
    """Finish the heavy channel and build Concerto before entering Slumberland."""

    FORTE_TIMEOUT = 10
    HEAVY_START_TIMEOUT = 2
    HEAVY_TIMEOUT = 6
    CONCERTO_TIMEOUT = 3
    # Slumberland lasts 50s and hides her normal attack, Resonance Skill and
    # Echo, so on a plain switch-in she cannot act.
    SLUMBERLAND_DURATION = 50
    # The same cast grants Cradle Lullaby for 25s. Bringing Lily back in
    # removes it and its Dream Aroma stacks, so even an Intro is refused for
    # that long. Her Intro ends Slumberland, so after that an Intro is the
    # way back in. Set it to 0 to take Intros right after the cast.
    SLUMBERLAND_INTRO_LOCKOUT = 25
    # Finding her asleep does not tell how long she has been that way: it may
    # be the tail end of the state. A sighting therefore holds the selector
    # off only briefly instead of for the whole duration.
    SLUMBERLAND_SIGHTING_BLOCK = 10
    slumberland_start = 0.0
    slumberland_block = SLUMBERLAND_DURATION

    def skip_combat_check(self):
        # Slumberland cannot lock on normally. Keep the short handoff alive
        # while its visible End control is present; switching restores checks.
        return self.in_slumberland()

    def do_perform(self):
        # Kit: https://ww.nanoka.cc/character/1512/ (E: 13s, Liberation: 25s).
        if self.has_intro:
            self.continues_normal_attack(0.8)
        if not self.in_slumberland():
            if self.slumberland_block_active():
                # Seen awake on field: the state is over, so stop avoiding her.
                self.slumberland_start = 0.0
                self.logger.info('Lily awake on field, Slumberland block cleared')
            self.click_echo(time_out=0)
            self.build_forte()
            if self.is_mouse_forte_full() or self.is_forte_full():
                self.perform_heavy()
            can_liberate = self.task.use_liberation and self.liberation_available()
            self.fill_concerto(0.8 if can_liberate else 1)
            # Slumberland hides E/echo/normal attacks. Enter it only after the
            # heavy finisher, then pass the healing and Outro buffs to the team.
            liberated = self.click_liberation(wait_if_cd_ready=0, click_f=False)
            if liberated:
                self.arm_slumberland_block(self.SLUMBERLAND_DURATION)
            if can_liberate and not liberated:
                self.fill_concerto()
        elif not self.slumberland_block_active():
            # Found asleep with no window running: this object never saw the
            # cast. Keep the selector off her briefly, then look again.
            self.arm_slumberland_block(self.SLUMBERLAND_SIGHTING_BLOCK)
        self.switch_next_char()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        # The selector drops NO targets, so it stops visiting a Lily who
        # cannot act. Her Intro ends Slumberland, so an Intro is let through
        # once Cradle Lullaby has lapsed.
        if self.slumberland_block_active() and (
                not has_intro
                or self.time_elapsed_accounting_for_freeze(self.slumberland_start)
                < self.SLUMBERLAND_INTRO_LOCKOUT):
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def slumberland_block_active(self):
        return (self.slumberland_start > 0
                and self.time_elapsed_accounting_for_freeze(self.slumberland_start)
                < self.slumberland_block)

    def arm_slumberland_block(self, duration):
        # Time-stops must not use the window up, so it runs on the freeze-
        # adjusted clock.
        self.slumberland_start = time.time()
        self.slumberland_block = duration
        self.logger.info(f'Lily Slumberland: no switch-ins for {duration}s')

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
