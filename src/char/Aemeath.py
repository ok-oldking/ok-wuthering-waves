import time

from src.char.BaseChar import BaseChar


class Aemeath(BaseChar):
    """Fixed-axis Aemeath for the Chisa -> Aemeath -> Denia rotation."""

    NORMAL_INTERVAL = 0.12
    HEAVY_DURATION = 0.70
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

    def enhance_e_available(self):
        return bool(
            self.task.find_one('aemeath_e1', threshold=0.7)
            or self.task.find_one('aemeath_e2', threshold=0.7)
        )

    def _enhanced_resonance(self):
        while True:
            self._wait_ready(self.enhance_e_available)
            if self.click_resonance(
                    has_animation=True,
                    send_click=True,
                    animation_min_duration=0.5,
                    time_out=1.5,
            )[0]:
                return True
            self.normal_attack()
            self.sleep(self.NORMAL_INTERVAL)

    def _form_resonance(self):
        self.click_resonance(time_out=1.5)
        return True

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
            self.logger.debug('Aemeath heavy attack sent without a full mouse-forte state')
            return True

        end = time.time() + self.HEAVY_VERIFY_TIMEOUT
        while time.time() < end:
            if not self.is_mouse_forte_full():
                return True
            self.task.next_frame()
        self.logger.warning('Aemeath heavy attack did not consume the detected mouse-forte state')
        return False

    def _break(self):
        self.f_break()
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
            self.logger.warning('Aemeath fixed-axis action failed; restarting from Chisa')
            self._reset_team_axis()
            self._switch_to_slot(3)

    def _final_segment(self):
        """aQREFaaEZR; Q and F are best-effort actions."""
        self._normal_chain(1)
        self._echo()
        if not self._liberation():
            return False
        if not self._enhanced_resonance():
            return False
        self._break()
        self._normal_chain(2)
        if not self._enhanced_resonance():
            return False
        if not self._heavy():
            return False
        return self._liberation()

    def _perform_segment(self, step):
        segment = step % 8
        if segment == 0:
            self._normal_chain(2)
            return True
        if segment == 1:
            self._normal_chain(1)
            return self._form_resonance()
        if segment == 2:
            self._normal_chain(2)
            return self._form_resonance()
        if segment == 3:
            self._normal_chain(2)
            return self._enhanced_resonance()
        if segment in {4, 5}:
            self._normal_chain(2)
            return self._form_resonance()
        if segment == 6:
            self._normal_chain(1)
            return True
        return self._final_segment()

    def do_perform(self):
        self._prepare_axis()
        if self.has_intro:
            self.wait_intro(1.2)

        step = self._axis_count % 8
        next_slots = (2, 3, 2, 3, 2, 2, 2, 2)
        self._finish(self._perform_segment(step), next_slots[step])

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def on_combat_end(self, chars):
        self._axis_count = 0
        self._axis_combat_start = None
