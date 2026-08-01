import time

from src.char.BaseChar import BaseChar


class Denia(BaseChar):
    """Fixed-axis Denia segments for the three-character rotation."""

    NORMAL_INTERVAL = 0.12
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

    def _liberation_best_effort(self):
        if self.liberation_available():
            self.click_liberation(wait_if_cd_ready=0.2)
        return True

    def _echo(self):
        if self.echo_available():
            self.click_echo(time_out=0)
        return True

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
            self.logger.warning('Denia fixed-axis action failed; restarting from Chisa')
            self._reset_team_axis()
            self._switch_to_slot(3)

    def _startup_segment(self, segment):
        if segment == 0:
            if not self._resonance():
                return False
            if not self._liberation():
                return False
            self._normal_chain(1)
            return True
        if segment == 1:
            self._normal_chain(2)
            return True
        if segment == 2:
            self._normal_chain(1)
            return True
        if segment in {3, 4}:
            return self._resonance()
        if segment == 5:
            self._normal_chain(2)
            if not self._liberation():
                return False
            self._echo()
            return True
        self._normal_chain(3)
        return True

    def _loop_segment(self, segment):
        if segment == 0:
            self._normal_chain(1)
            return True
        if segment in {1, 3}:
            if not self._resonance():
                return False
            if not self._liberation():
                return False
            self._normal_chain(1)
            return True
        if segment == 2:
            self._normal_chain(2)
            return True
        if segment in {4, 5}:
            return self._resonance()
        if segment == 6:
            self._normal_chain(2)
            self._liberation_best_effort()
            self._echo()
            return True
        self._normal_chain(3)
        return True

    def do_perform(self):
        self._prepare_axis()
        if self.has_intro:
            self.wait_intro(1.2)

        if self._axis_count < 7:
            segment = self._axis_count
            next_slots = (3, 1, 3, 1, 3, 1, 1)
            success = self._startup_segment(segment)
            self._finish(success, next_slots[segment])
            return

        segment = (self._axis_count - 7) % 8
        next_slots = (3, 3, 1, 3, 1, 3, 1, 1)
        self._finish(self._loop_segment(segment), next_slots[segment])

    def on_combat_end(self, chars):
        self._axis_count = 0
        self._axis_combat_start = None
