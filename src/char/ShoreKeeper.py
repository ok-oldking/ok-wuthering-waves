import time

from src.char.BaseChar import BaseChar, SwitchPriority


class ShoreKeeper(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outrotime = -1
        self.dodge_count = 0
        self.attribute = 0

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        from src.combat.StrictRotation import get_strict_rotation, MUST, NO
        rot = get_strict_rotation(self.task)
        if rot.is_active():
            priority = rot.priority_for(self.name)
            if priority == MUST:
                return SwitchPriority.MUST
            if priority == NO:
                return SwitchPriority.NO
        self.decide_teammate()
        current_name = current_char.char_name if current_char else None
        if self.attribute == 2 and has_intro and current_name in {'Augusta', 'char_augusta'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def skip_combat_check(self):
        return self.has_intro or self.flying()

    def decide_teammate(self):
        from src.char.Augusta import Augusta
        if self.attribute > 0:
            return
        if self.task.has_char(Augusta):
            self.attribute = 2
        else:
            self.attribute = 1

    def do_perform(self):
        from src.combat.StrictRotation import get_strict_rotation
        if get_strict_rotation(self.task).run_current(self):
            return
        self._do_perform_default()

    def _do_perform_default(self):
        if self.has_intro:
            self._intro_wait()
        self.click_echo(time_out=0)
        self.click_liberation()
        # click_resonance returns a (clicked, duration, animated) tuple; index
        # [0] so the forte fallback actually runs when the skill didn't fire.
        if not self.click_resonance()[0]:
            self.heavy_click_forte(self.is_mouse_forte_full)
        self.switch_next_char()

    def _intro_wait(self):
        self.task.skip_combat_check = True
        try:
            self.logger.debug('ShoreKeeper wait intro animation')
            time.sleep(0.1)
            if not self.task.in_team_and_world():
                self.task.wait_in_team_and_world(time_out=4, raise_if_not_found=False)
            else:
                self.continues_normal_attack(1.2)
        finally:
            self.task.skip_combat_check = False

    def perform_beat(self, beat):
        """Execute one strict-rotation beat (see src/combat/StrictRotation.py).

        Concerto for outro beats is topped off centrally by run_current, so
        these only need to spend the kit; build_concerto recasts echo/skill
        (and falls back to basics) to finish the ring before the swap.
        """
        from src.combat.StrictRotation import basic_attacks, heavy
        if beat.intro:
            # R2 enters on an enhanced intro handed over by Augusta's outro.
            self._intro_wait()
        if beat.name == 'sk_r1':
            # First Rotation: ba x5, ha, skill, ba x3, lib, ba x2, ha, echo, outro.
            # Combat opens on ShoreKeeper, so there is no intro to wait for here.
            basic_attacks(self, 5)
            heavy(self)
            self.click_resonance()
            basic_attacks(self, 3)
            self.click_liberation()
            basic_attacks(self, 2)
            heavy(self)
            # Echo is ShoreKeeper's main concerto source (her basics generate
            # almost none); time_out=0 only fires when it is off cooldown.
            self.click_echo(time_out=0)
        elif beat.name == 'sk_r2':
            # Second Rotation: enhanced intro, ba x3, lib, ba x2, ha, skill,
            # ba x2 (the 2nd basic is cancelled by the outro swap). Echo is held
            # this beat on purpose so build_concerto can recast it to finish the
            # ring for the outro (basics alone barely build her concerto).
            basic_attacks(self, 3)
            self.click_liberation()
            basic_attacks(self, 2)
            heavy(self)
            self.click_resonance()
            basic_attacks(self, 2)
        else:  # defensive: unknown beat
            self.click_echo(time_out=0)
            self.click_liberation()

    def switch_next_char(self, *args, **kwargs):
        if self.is_con_full():
            self.outrotime = time.time()
            self.dodge_count = 5
        return super().switch_next_char(*args, **kwargs)

    def auto_dodge(self, condition):
        clicked = False
        if self.time_elapsed_accounting_for_freeze(self.outrotime) < 30 and self.dodge_count > 0:
            start = time.time()
            while time.time() - start < 1.5:
                if not condition():
                    break
                self.continues_right_click(0.05)
                self.sleep(0.05)
                clicked = True
                self.task.next_frame()
        if clicked:
            self.dodge_count -= 1
            self.logger.info('ShoreKeepers auto dodge success!')
        return clicked
