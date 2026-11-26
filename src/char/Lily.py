import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Lily(BaseChar):
    """Finish the heavy channel and build Concerto before entering Slumberland."""

    FORTE_TIMEOUT = 10
    HEAVY_START_TIMEOUT = 2
    HEAVY_TIMEOUT = 6
    CONCERTO_TIMEOUT = 3
    # A hold that starts inside the animation of the skill that filled Dream
    # Perfume is swallowed. After a failed start, look this long for the forte
    # prompt, and press again after a short gap if it is still up.
    HEAVY_RETRY_CHECK = 0.3
    HEAVY_RETRY_GAP = 0.05
    # Lily alternates between two heavy forms that share Dream Perfume: only
    # the Nightmare form displays Labels.lily_heavy, while the Fairytale form
    # consumes the forte prompt without showing that icon. Confirming the
    # prompt disappeared while Lily stays on field detects the alternate form.
    HEAVY_PROMPT_GONE_SETTLE = 0.4
    HEAVY_ALT_HOLD = 4.6
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
            if not can_liberate:
                # Tells a drained Liberation apart from one that was not read.
                self.logger.info('Lily Liberation is ' +
                                 ('off' if not self.task.use_liberation else 'not ready'))
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

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        # The End control is not on screen yet when the cast's animation ends,
        # so skip_combat_check() does not cover this hand-off. The combat check
        # before the switch key would find no lock and no health bar, then spend
        # its whole retarget timeout middle-clicking while she sleeps. She
        # cannot act either way: hand off first, and let the incoming
        # Resonator's own check decide whether the fight is over.
        if not self.slumberland_block_active():
            return super().switch_next_char(post_action=post_action, free_intro=free_intro,
                                            target_low_con=target_low_con)
        previous = getattr(self.task, 'skip_combat_check', False)
        self.task.skip_combat_check = True
        try:
            return super().switch_next_char(post_action=post_action, free_intro=free_intro,
                                            target_low_con=target_low_con)
        finally:
            self.task.skip_combat_check = previous

    def on_combat_end(self, chars):
        # If combat ends while Lily is still on field asleep (for example when
        # her Liberation killed the last enemy), switch to a teammate who can
        # walk to Echo drops instead of leaving her stuck on field.
        if self.slumberland_block_active() or self.in_slumberland():
            self.switch_other_char()

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

    def on_field(self):
        in_team, current, _ = self.task.in_team()
        return bool(in_team) and current == self.index

    def heavy_still_ready(self):
        # Another Resonator's forte prompt looks the same, so also require the
        # party frame to show Lily as the active one.
        return bool(self.is_mouse_forte_full()) and self.on_field()

    def perform_heavy(self):
        self.check_combat()
        held = False
        mode = None
        finished = False

        def wait_heavy_start():
            gone_since = [None]

            def detect_start():
                if self.heavy_in_progress():
                    return 'flower'
                if not self.is_mouse_forte_full() and self.on_field():
                    now = time.time()
                    if gone_since[0] is None:
                        gone_since[0] = now
                    if now - gone_since[0] >= self.HEAVY_PROMPT_GONE_SETTLE:
                        return 'alt'
                else:
                    gone_since[0] = None
                return False

            res = self.task.wait_until(
                detect_start, time_out=self.HEAVY_START_TIMEOUT,
                pre_action=self.check_combat)
            if res is True:
                return 'flower', None
            if res in ('flower', 'alt'):
                return res, gone_since[0]
            return None, None

        try:
            self.task.mouse_down()
            held = True
            mode, consumed_at = wait_heavy_start()
            if not mode and self.task.wait_until(
                    self.heavy_still_ready, time_out=self.HEAVY_RETRY_CHECK):
                # Nothing was consumed, so the hold never reached the game.
                self.logger.info('Lily heavy channel did not start, pressing again')
                self.task.mouse_up()
                held = False
                self.sleep(self.HEAVY_RETRY_GAP)
                self.task.mouse_down()
                held = True
                mode, consumed_at = wait_heavy_start()
            if not mode:
                self.logger.warning('Lily heavy channel did not start')
                return False
            if mode == 'alt':
                alt_start = consumed_at if consumed_at is not None else time.time()
                res = self.task.wait_until(
                    lambda: 'flower' if self.heavy_in_progress()
                    else ('done' if time.time() - alt_start >= self.HEAVY_ALT_HOLD else False),
                    time_out=self.HEAVY_ALT_HOLD + 0.5, pre_action=self.check_combat)
                if res == 'flower':
                    mode = 'flower'
                else:
                    finished = bool(res)
            if mode == 'flower':
                finished = bool(self.task.wait_until(
                    lambda: not self.heavy_in_progress(), time_out=self.HEAVY_TIMEOUT,
                    settle_time=0.15, pre_action=self.check_combat))
        finally:
            if held:
                self.task.mouse_up()
        if finished:
            # The prompt disappears at the start of the uninterruptible finisher.
            self.sleep(0.7)
            if mode == 'alt':
                self.logger.info('Lily heavy finisher completed (alternate form)')
            else:
                self.logger.info('Lily heavy finisher completed')
        else:
            self.logger.warning('Lily heavy channel did not finish before timeout')
        return finished
