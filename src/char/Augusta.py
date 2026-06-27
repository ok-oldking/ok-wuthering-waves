import time

from src.char.BaseChar import BaseChar

""" 
    几个长派生帧动作的切人时间阈值,改小可以减少站场时间
    初始为 3
"""
switch_time = 3


class Augusta(BaseChar):
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
        if beat.name == 'aug_r1':
            # First Rotation: ha, skill, ha, lib (Eternal Oath), skill x3,
            #                 Sunborne x9, Protector (2nd lib), echo, outro.
            self._augusta_full()
        elif beat.name == 'aug_loop':
            # Loop quickswap: ha, skill, then the Eternal Oath -> Sunborne ->
            # Protector burst only when the liberation is off cooldown, else a
            # fast forte/heavy; echo, outro.
            self._augusta_quickswap()
        else:  # defensive: unknown beat -> conservative damage
            self.click_resonance()
            heavy(self)

    def _heavy_or_prowess(self):
        from src.combat.StrictRotation import heavy
        if self.check_prowess():
            self.perform_prowess()
        else:
            heavy(self)

    def _augusta_full(self):
        self._heavy_or_prowess()                 # ha
        self.click_resonance()                   # skill
        self._heavy_or_prowess()                 # ha
        self.click_liberation()                  # Eternal Oath (1st liberation)
        for _ in range(3):                       # skill 1, 2, 3
            self.click_resonance()
        self._augusta_sunborne(9)                # Sunborne x9 (forte strikes)
        if self.check_majesty():                 # Protector (2nd liberation recast)
            self.perform_majesty()
        else:
            self.logger.info('Augusta: Protector (2nd lib) not detected, skipping')
        self.send_echo_key()                     # echo

    def _augusta_quickswap(self):
        self._heavy_or_prowess()                 # ha
        self.click_resonance()                   # skill
        if self.liberation_available():          # Eternal Oath only when ready
            self.click_liberation()
            for _ in range(3):
                self.click_resonance()
            self._augusta_sunborne(9)
            if self.check_majesty():
                self.perform_majesty()
        else:
            self._heavy_or_prowess()             # no liberation: dump a forte/heavy
        self.send_echo_key()                     # echo

    def _augusta_sunborne(self, count):
        """Spend the Eternal Oath stance with up to ``count`` Sunborne forte
        strikes. ``perform_prowess`` holds the forte heavy until prowess is no
        longer available, so the stance usually drains in one or two passes;
        the loop simply caps it and bails the moment prowess is gone."""
        for _ in range(count):
            if not self.check_prowess():
                break
            if not self.perform_prowess():
                break

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
            if self.check_majesty():
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
                    if self.check_majesty():
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
