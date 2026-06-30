import time

from src.char.BaseChar import BaseChar, SwitchPriority


class ShoreKeeper(BaseChar):
    INTRO_READY_WAIT = 0.6
    ZANI_EARLY_EMPTY_CUT_CON = 0.8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outrotime = -1
        self.dodge_count = 0
        self.attribute = 0

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        self.decide_teammate()
        current_name = current_char.char_name if current_char else None
        if self.attribute == 2 and has_intro and current_name in {'Augusta', 'char_augusta'}:
            return SwitchPriority.MUST
        if self._should_block_zani_early_empty_cut(current_char, has_intro):
            self.logger.info("ShoreKeeper v5 block early empty cut during Zani first liberation")
            return SwitchPriority.NO
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

    def _fast_intro_liberation(self):
        self.task.skip_combat_check = True
        try:
            self.task.wait_in_team_and_world(
                time_out=self.INTRO_READY_WAIT,
                raise_if_not_found=False,
            )
        finally:
            self.task.skip_combat_check = False
        return self.click_liberation()

    def _should_fast_intro_liberation(self):
        has_phoebe = False
        has_zani = False
        for char in self.task.chars:
            if char is None:
                continue
            name = getattr(char, "char_name", "")
            cls_name = char.__class__.__name__
            if name == "char_phoebe" or cls_name == "Phoebe":
                has_phoebe = True
            elif name == "char_zani" or cls_name == "Zani":
                has_zani = True
        return has_phoebe and has_zani

    def _should_block_zani_early_empty_cut(self, current_char, has_intro):
        if has_intro or current_char is None:
            return False
        if not self._should_fast_intro_liberation():
            return False
        current_name = getattr(current_char, "char_name", "")
        current_cls = current_char.__class__.__name__
        if current_name != "char_zani" and current_cls != "Zani":
            return False

        current_con = 0
        try:
            current_con = current_char.get_current_con()
        except Exception:
            current_con = 0
        if current_con < self.ZANI_EARLY_EMPTY_CUT_CON:
            return False

        if getattr(current_char, "in_liberation", False):
            return True
        if hasattr(current_char, "liberation_time_left") and current_char.liberation_time_left() > 0:
            return True
        if hasattr(current_char, "nightfall_time_left") and current_char.nightfall_time_left() > 0:
            return True
        return False

    def do_perform(self):
        if (
                self.has_intro
                and self._should_fast_intro_liberation()
                and self._fast_intro_liberation()
        ):
            return self.switch_next_char()

        if self.has_intro:
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
        self.click_echo(time_out=0)
        self.click_liberation()
        if not self.click_resonance():
            self.heavy_click_forte(self.is_mouse_forte_full)
        self.switch_next_char()

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
