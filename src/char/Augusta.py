import re
import time

from src.char.BaseChar import BaseChar

""" 
    几个长派生帧动作的切人时间阈值,改小可以减少站场时间
    初始为 3
"""
switch_time = 3


class Augusta(BaseChar):
    # Augusta's stacking buff shows a count badge that maxes at 10. The second
    # liberation (majesty recast) must only fire at max stacks -- recasting below
    # 10 wastes the empowered hit. The count is read by OCR over the badge; the
    # box is in 3840x2160 reference px (auto-scaled to the live resolution) and
    # is tunable in-game -- enable debug logging to see the value being read. If
    # OCR can't pick up the badge, point AUGUSTA_BUFF_STACK_BOX at it.
    AUGUSTA_BUFF_STACK_BOX = (3560, 1860, 3700, 1990)
    AUGUSTA_BUFF_STACK_TARGET = 10

    def do_perform(self):
        from src.combat.StrictRotation import get_strict_rotation
        if get_strict_rotation(self.task).run_current(self):
            return
        self._do_perform_default()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        from src.combat.StrictRotation import get_strict_rotation, MUST, NO
        from src.char.BaseChar import SwitchPriority
        rot = get_strict_rotation(self.task)
        if rot.is_active():
            priority = rot.priority_for(self.name)
            if priority == MUST:
                return SwitchPriority.MUST
            if priority == NO:
                return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def perform_beat(self, beat):
        """Execute one strict-rotation beat (see src/combat/StrictRotation.py)."""
        from src.combat.StrictRotation import heavy
        if beat.intro:
            self.wait_down()
        if beat.name == 'aug_open':
            # 1. skill
            self.click_resonance()
        elif beat.name == 'aug_open2':
            # 5. ha
            self._heavy_or_prowess()
        elif beat.name == 'aug_loop1':
            # 11. intro, ha
            self._heavy_or_prowess()
        elif beat.name == 'aug_loop2':
            # 13. skill, ha
            self.click_resonance()
            self._heavy_or_prowess()
        elif beat.name == 'aug_burst':
            # 9. intro, ha, lib (griffin), skill, ha, 2nd lib, echo, outro
            self._augusta_burst(with_basics=False)
        elif beat.name == 'aug_burst2':
            # 15. ha, lib (griffin), skill, ha, 2nd lib, ba123, ha, echo, outro
            self._augusta_burst(with_basics=True)
        else:  # defensive: unknown beat -> conservative damage
            self.click_resonance()
            heavy(self)

    def _heavy_or_prowess(self):
        from src.combat.StrictRotation import heavy
        if self.check_prowess():
            self.perform_prowess()
        else:
            heavy(self)

    def _augusta_burst(self, with_basics):
        from src.combat.StrictRotation import heavy, basic_attacks
        self._heavy_or_prowess()                 # ha
        self.click_liberation()                  # lib -> summons griffin
        self.click_resonance()                   # skill
        self._heavy_or_prowess()                 # ha
        if self.check_majesty():                 # 2nd lib (majesty recast)
            # only recast the 2nd lib at max buff stacks; build to it first
            if self.wait_for_buff_stacks():
                self.perform_majesty()
            else:
                self.logger.info(
                    f'Augusta burst: buff under {self.AUGUSTA_BUFF_STACK_TARGET} '
                    f'stacks, skipping 2nd lib')
        else:
            self.logger.info('Augusta burst: majesty (2nd lib) not detected, skipping')
        if with_basics:
            basic_attacks(self, 3)               # ba123
            heavy(self)                          # ha
        self.send_echo_key()                     # echo

    def _do_perform_default(self):
        time_out = switch_time
        if self.has_intro:
            self.continues_normal_attack(1.13)
            if self.has_sub_dps_intro and self.check_outro() in {'char_iuno'}:
                time_out = 14
        if self.flying():
            self.wait_down()
        start = time.time()
        timeout = lambda: time.time() - start < time_out + 3
        while timeout():
            self.cycle_start()
            if self.check_majesty() and self.buff_stacks_full():
                self.logger.debug('Augusta performs majesty')
                if self.perform_majesty():
                    self.send_echo_key()
                    return self.switch_next_char()
            if self.flying():
                self.shorekeeper_auto_dodge()
            if self.check_prowess() and self.perform_prowess():
                if time.time() - start > time_out:
                    return self.switch_next_char()
            if self.resonance_available():
                self.logger.debug('Augusta performs single resonance')
                now = time.time()
                self.click_resonance()
                self.logger.debug(f'time = {time.time() - now}')
                if time.time() - now < 1.4:
                    if self.flying():
                        continue
                    if self.task.wait_until(self.check_prowess, time_out=1) and self.perform_prowess():
                        if time.time() - start > time_out and not self.flying():
                            return self.switch_next_char()
                else:
                    if self.check_majesty() and self.buff_stacks_full():
                        self.wait_down()
                        if self.perform_majesty():
                            self.send_echo_key()
                        return self.switch_next_char()
            if self.liberation_available():
                self.logger.debug('Augusta performs single liberation')
                if self.task.wait_until(lambda: not self.liberation_available(), post_action=self.send_liberation_key,
                                        time_out=2):
                    self.record_liberation_use()
                    if time_out < 14:
                        return self.switch_next_char()
            self.click()
            self.cycle_sleep()
        self.send_echo_key()
        self.switch_next_char()

    def perform_prowess(self):
        self.logger.debug('Augusta performs prowess')
        if not self.heavy_click_forte(self.check_prowess):
            return False
        self.continues_normal_attack(0.3)
        return True

    def perform_majesty(self, time_out=0.6, wait_down=False):
        self.task.send_key_down(self.get_liberation_key())
        self.task.in_liberation = True
        if wait_down:
            time_out = 0.2
            self.task.wait_until(lambda: not self.task.in_team()[0] or not self.flying(), time_out=2)
        self.task.wait_until(lambda: not self.task.in_team()[0], time_out=time_out)
        start = time.time()
        self.task.send_key_up(self.get_liberation_key())
        if self.task.in_team()[0]:
            self.logger.debug('Augusta performs majesty failed: not in animation')
            self.task.in_liberation = False
            return False
        self.task.wait_until(lambda: self.task.in_team()[0], post_action=self.click, time_out=10)
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'click_liberation end {time.time() - start}')

        return True

    def check_ascendancy(self):
        return False

    def liberation_available(self, check_color=True):
        return self.current_liberation() > 0 and bool(self.task.find_one('Augusta_lib1', threshold=0.5))

    def check_majesty(self):
        return self.current_liberation() > 0 and bool(self.task.find_one('Augusta_lib2', threshold=0.5))

    def buff_stacks(self):
        """OCR Augusta's stacking-buff count badge (0 if it can't be read)."""
        box = self.task.box_of_screen_scaled(
            3840, 2160, *self.AUGUSTA_BUFF_STACK_BOX,
            name='augusta_buff_stacks', hcenter=True)
        stacks = 0
        for t in self.task.ocr(box=box, match=re.compile(r'\d+')):
            try:
                stacks = max(stacks, int(re.sub(r'\D', '', t.name)))
            except (ValueError, TypeError):
                continue
        self.logger.debug(f'Augusta buff_stacks = {stacks}')
        return stacks

    def buff_stacks_full(self):
        return self.buff_stacks() >= self.AUGUSTA_BUFF_STACK_TARGET

    def wait_for_buff_stacks(self, time_out=3):
        """Build to max buff stacks before the 2nd lib, attacking while waiting.

        Returns True once the buff is full. Gives up (returns False) after
        ``time_out`` so a missing/unreadable badge can't stall the rotation --
        the caller then skips the 2nd lib for this cycle.
        """
        if self.buff_stacks_full():
            return True
        return bool(self.task.wait_until(
            self.buff_stacks_full, post_action=self.click, time_out=time_out))

    def check_prowess(self):
        long_inner_box = 'target_enemy_long_inner'
        if self.task.find_one(long_inner_box, threshold=0.8):
            return True

    def resonance_available(self):
        return not self.has_cd('resonance')

    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition=self.flying)

    def on_combat_end(self, chars):
        next_char = str((self.index + 1) % len(chars) + 1)
        self.logger.debug(f'Augusta on_combat_end {self.index} switch next char: {next_char}')
        self.task.send_key(next_char)
