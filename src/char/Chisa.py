import time

from src.char.BaseChar import BaseChar


class Chisa(BaseChar):
    """Fixed-axis Chisa segments for the three-character rotation."""

    NORMAL_INTERVAL = 0.12
    HEAVY_DURATION = 3.0
    HEAVY_VERIFY_TIMEOUT = 1.0
    SWITCH_TIMEOUT = 2.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._axis_count = 0
        self._axis_combat_start = None

    def _prepare_axis(self):
        combat_start = getattr(self.task, 'combat_start', None)
        if combat_start != self._axis_combat_start:
            self._axis_combat_start = combat_start
            self._axis_count = 0

    def _normal_chain(self, count):
        for _ in range(count):
            self.normal_attack()
            self.sleep(self.NORMAL_INTERVAL)

    def _wait_ready(self, predicate):
        while True:
            self.check_combat()
            if predicate():
                return True
            self.normal_attack()
            self.sleep(self.NORMAL_INTERVAL)

    def _resonance(self):
        while True:
            self._wait_ready(self.resonance_available)
            if self.click_resonance(time_out=1.5)[0]:
                return True
            self.normal_attack()
            self.sleep(self.NORMAL_INTERVAL)

    def _liberation(self):
        while True:
            self._wait_ready(self.liberation_available)
            if self.click_liberation(wait_if_cd_ready=0.2):
                return True
            self.normal_attack()
            self.sleep(self.NORMAL_INTERVAL)

    def _echo(self):
        if self.echo_available():
            self.click_echo(time_out=0)
        return True

    def _heavy(self):
        forte_was_full = self.is_mouse_forte_full()
        self.heavy_attack(self.HEAVY_DURATION)

        if not forte_was_full:
            self.logger.debug('Chisa heavy attack sent without a full mouse-forte state')
            return True

        end = time.time() + self.HEAVY_VERIFY_TIMEOUT
        while time.time() < end:
            if not self.is_mouse_forte_full():
                return True
            self.task.next_frame()
        self.logger.warning('Chisa heavy attack did not consume the detected mouse-forte state')
        return False

    def _jump(self):
        self.logger.debug('Chisa fixed-axis startup jump')
        self.task.send_key('space')
        return True

    def _wait_after_jump(self):
        self.sleep(0.15, False)
        if getattr(self.task, 'has_lavitator', False):
            self.task.wait_until(lambda: not self.flying(), time_out=2.0)
        else:
            self.sleep(0.45, False)
        self.sleep(0.08, False)

    def _reset_team_axis(self):
        for char in getattr(self.task, 'chars', []):
            if hasattr(char, '_axis_count'):
                char._axis_count = 0

    def _switch_to_slot(self, slot):
        target_index = slot - 1
        self.has_intro = False
        self.has_sub_dps_intro = False
        self._liberation_available = self.liberation_available()
        self.use_tool_box()

        start = time.time()
        while time.time() - start < self.SWITCH_TIMEOUT:
            in_team, current_index, _ = self.task.in_team()
            if in_team and current_index == target_index:
                now = time.time()
                self.last_switch_time = now
                for char in getattr(self.task, 'chars', []):
                    if char:
                        char.is_current_char = char.index == target_index
                        if char.index == target_index:
                            char.last_switch_in_time = now
                return True
            self.task.send_key(str(slot))
            self.task.next_frame()
            self.sleep(0.1, False)
        return False

    def _finish(self, success, next_slot):
        if success:
            self._axis_count += 1
            self._switch_to_slot(next_slot)
        else:
            self.logger.warning('Chisa fixed-axis action failed; restarting from Chisa')
            self._reset_team_axis()
            self._switch_to_slot(3)

    def _perform_segment(self, step):
        if step < 6:
            segment = step
            startup = True
        else:
            segment = (step - 6) % 6
            startup = False

        if segment == 0:
            if startup:
                self._jump()
                self._normal_chain(1)
                self._wait_after_jump()
                if not self._resonance():
                    return False
                self._normal_chain(1)
                return True
            self._normal_chain(1)
            if not self._resonance():
                return False
            self._normal_chain(1)
            return True

        if segment in {1, 2, 5}:
            self._normal_chain(1)
            return True

        if segment == 3:
            if not self._liberation():
                return False
            return self._resonance()

        self._heavy()
        self._echo()
        return True

    def do_perform(self):
        self._prepare_axis()
        if self.has_intro:
            self.wait_intro(1.2)

        step = self._axis_count
        next_slots = (1, 1, 2, 1, 2, 1)
        self._finish(self._perform_segment(step), next_slots[step % 6])

    def on_combat_end(self, chars):
        self._axis_count = 0
        self._axis_combat_start = None
