import time

from src.char.BaseChar import BaseChar, CharType


class Roccia(BaseChar):

    def get_char_type(self):
        if self.task and self.task.char_config.get('Roccia C6', False):
            return CharType.MAIN_DPS
        return super().get_char_type()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plunge_count = 0
        self.last_e = 0
        self.last_intro = 0
        self.can_plunge = False
        self._air_forte_charges = 0

    def do_perform(self):
        if self.has_intro:
            self.heavy_attack(1.6)
            self.sleep(0.1)
            self.last_intro = time.time()
            self.plunge()
            if not self.liberation_available() and not self.resonance_available():
                return self.switch_next_char()
        liberated = self.click_liberation()
        if self.click_resonance()[0] or not liberated:
            self.plunge()
            return self.switch_next_char()
        self.click_echo()
        return self.switch_next_char()

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        super().switch_next_char(post_action=self.update_tool_box, free_intro=free_intro,
                                 target_low_con=target_low_con)

    def update_tool_box(self, next_char, has_intro):
        if has_intro:
            next_char.has_tool_box = True

    def plunge(self):
        if self.need_fast_perform():
            self.normal_attack_until_can_switch()
            return
        start = time.monotonic()
        last_ready = start
        entered_air = False
        last_air_seen = start
        pending_air_charges = 0
        self.task.send_key_down('w')
        try:
            while time.monotonic() - start < 8:
                self.task.next_frame()
                visible_air = self.air_forte_ready()
                airborne = visible_air
                mouse_ready = False if airborne else bool(self.is_mouse_forte_full())
                now = time.monotonic()
                if visible_air:
                    last_air_seen = now
                    # Reserve only charges left after the hold below consumes one.
                    pending_air_charges = max(0, self._air_forte_charges - 1)
                elif pending_air_charges and now - last_air_seen < 0.9 and mouse_ready:
                    # A consumption flash can hide both faces. Bridge at most
                    # one hold per observed spare charge, with a separate prompt.
                    airborne = True
                    pending_air_charges -= 1
                ready = airborne or mouse_ready
                if ready:
                    last_ready = now
                elif now - last_ready > 0.45:
                    if not pending_air_charges or now - last_air_seen >= 0.9:
                        break
                entered_air = entered_air or visible_air
                if not ready:
                    self.sleep(0.05)
                    continue
                # The same mouse hint exists before launch and in midair.
                # Hold to enter/consume the special heavy attack, rather than
                # relying on a 10 ms normal click to trigger every transition.
                self.task.mouse_down()
                try:
                    self.sleep(0.4 if airborne else 1.6)
                finally:
                    self.task.mouse_up()
                self.sleep(0.08)
            return entered_air
        finally:
            self.task.mouse_up()
            self.task.send_key_up('w')

    def air_forte_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1580, 1930, 2190, 2040,
                                            name='roccia_air_forte_area', hcenter=True)
        first = self.task.find_one('roccia_air_forte', box=box, threshold=0.7)
        second = self.task.find_one('roccia_air_forte_second', box=box, threshold=0.8)
        self._air_forte_charges = int(bool(first or second))
        if first and second and abs(first.x - second.x) > max(first.width, second.width):
            self._air_forte_charges = 2
        return bool(self._air_forte_charges)
