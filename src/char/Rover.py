import time
from ok import Logger
from src.char.BaseChar import BaseChar, Elements

_ROVER_FORM_NAMES = {
    Elements.SPECTRO: 'Rover: Spectro',
    Elements.WIND: 'Rover: Aero',
    Elements.HAVOC: 'Rover: Havoc',
}


class Rover(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_skyfall_severance = False
        self._bind_form_logger()

    def reset_state(self):
        self.ring_index = -1
        super().reset_state()
        self._bind_form_logger()

    @property
    def display_name(self):
        return _ROVER_FORM_NAMES.get(self.ring_index, 'Rover')

    def __repr__(self):
        return self.display_name

    def _bind_form_logger(self):
        self.logger = Logger.get_logger(self.display_name)

    def _known_form(self):
        if hasattr(self.task, 'get_known_ring_index'):
            return self.task.get_known_ring_index(self)
        return self.ring_index

    def is_havoc_form(self):
        return self._known_form() == Elements.HAVOC

    def ensure_display_form(self):
        if self.ring_index >= 0:
            return
        if not self.is_current_char:
            return
        if hasattr(self.task, '_ensure_ring_index'):
            self.task._ensure_ring_index()
            self._bind_form_logger()

    def _in_zani_liber_insert_window(self):
        """赞妮大招插队窗口：phase 2/3 且仍在 liberation 时跑 insert 短轴。"""
        from src.char.Zani import Zani
        zani = self.task.has_char(Zani)
        if zani is None or not getattr(zani, '_zanfei_guang', False):
            return False
        return bool(zani.try_consume_insert_handoff())

    def _discard_zani_liber_insert_handoff(self):
        """非 Spectro 形态不执行 Insert，丢弃本次 token 后继续自身 routine。"""
        from src.char.Zani import Zani
        zani = self.task.has_char(Zani)
        if (
            zani is not None
            and getattr(zani, 'in_liberation', False)
            and getattr(zani, '_liber_phase', 0) in (2, 3)
            and getattr(zani, '_liber_handoff_token', 0) > 0
        ):
            zani._liber_handoff_token = 0
            self.logger.info('rover: discard zani insert token for non-spectro routine')

    def do_perform(self):
        self.init()
        if not self.has_intro:
            self.sleep(0.01)
        if self.ring_index == Elements.HAVOC:
            self._discard_zani_liber_insert_handoff()
            self.intro_motion_freeze_duration = 0.64
            self.logger.info('rover: form-dispatch ring=HAVOC routine=havoc')
            if self.perform_havoc_routine():
                return
        elif self.ring_index == Elements.SPECTRO:
            self.intro_motion_freeze_duration = 0.92
            self.logger.info('rover: form-dispatch ring=SPECTRO routine=spectro')
            if self.perform_spectro_routine():
                return
        elif self.ring_index == Elements.WIND:
            self._discard_zani_liber_insert_handoff()
            self.intro_motion_freeze_duration = 0.52
            self.logger.info('rover: form-dispatch ring=WIND routine=wind')
            self.perform_wind_routine()
        else:
            self._discard_zani_liber_insert_handoff()
            self.logger.info('rover: form-dispatch ring=UNKNOWN routine=basic')
            self.perform_basic_routine()
        self.switch_next_char()

    INSERT_R_TO_Q_SETTLE = 0.60

    def _do_zani_liber_insert(self):
        """赞妮大招插入：E → R → Q → 切回赞妮。"""
        self.logger.info('rover: zani liber insert short axis (E+Q+R)')
        self.init()
        if self.has_intro:
            self.continues_normal_attack(0.2)
        self.wait_down()
        if self.resonance_available():
            self.click_resonance(send_click=True)
            self.sleep(0.05)
        if self.task.use_liberation:
            liber_success = self.click_liberation(send_click=True)
            if not liber_success:
                self.logger.info('rover: liber insert R first-fail, retry loop')
                retry_start = time.time()
                while time.time() - retry_start < 2:
                    remaining = 2 - (time.time() - retry_start)
                    self.continues_normal_attack(min(0.25, remaining))
                    if time.time() - retry_start >= 2:
                        break
                    if self.click_liberation(send_click=True, wait_if_cd_ready=0):
                        liber_success = True
                        self.logger.info(f'rover: liber insert R retry-success elapsed={time.time() - retry_start:.2f}s')
                        break
            else:
                self.logger.info('rover: liber insert R first-success')
            if liber_success:
                self.logger.info(f'rover: insert R settle begin duration={self.INSERT_R_TO_Q_SETTLE:.2f}s')
                self.sleep(self.INSERT_R_TO_Q_SETTLE)
                self.logger.info(f'rover: insert R settle elapsed={self.INSERT_R_TO_Q_SETTLE:.2f}s')
        if self.echo_available():
            self.logger.info('rover: insert Q input time_out=0')
            self.click_echo(time_out=0)
            self.logger.info('rover: insert Q returned')
        if self.buff_time > 0:
            self.last_buff_time = time.time()
            self.logger.info(f'rover: insert buff refreshed buff_time={self.buff_time}')
        self.logger.info('rover: insert switch-to-zani')
        from src.char.Zani import Zani
        zani = self.task.has_char(Zani)
        return super().switch_next_char()

    def init(self):
        previous_form = self.ring_index
        if hasattr(self.task, '_ensure_ring_index'):
            self.task._ensure_ring_index()
        if self.ring_index != previous_form:
            self._bind_form_logger()
            self.logger.info(
                f'rover: form-corrected previous={previous_form} current={self.ring_index}'
            )
            names = []
            for char in self.task.chars:
                if char is None:
                    continue
                name = getattr(char, 'display_name', char.name)
                names.append(self.task.tr(name) if getattr(self.task, '_app', None) is not None else name)
            self.task.info_set('Chars', ', '.join(names))
        if self.ring_index == Elements.WIND:
            self.init_wind()

    def perform_spectro_routine(self):
        if self._in_zani_liber_insert_window():
            self._do_zani_liber_insert()
            return True
        if self.has_intro:
            self.continues_normal_attack(1)
        self.wait_down()
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)
        self.click_echo(time_out=0)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
        self.check_combat()
        if not self.click_liberation(send_click=True):
            self.click_resonance()
        return False

    def perform_havoc_routine(self):
        self.wait_down()
        self.heavy_click_forte(check_fun = self.is_mouse_forte_full)
        self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))

    def init_wind(self):
        from src.char.Cartethyia import Cartethyia
        from src.char.Phoebe import Phoebe
        self.use_skyfall_severance = bool(self.task.has_char(Cartethyia) and self.task.has_char(Phoebe))

    def perform_wind_routine(self):
        if not (self.has_intro and self.wind_routine_click_while_flying(2)):
            self.wind_routine_wait_down(check_forte_full=False)
            if self.resonance_available() and not self.is_forte_full():
                self.click_echo(time_out=0)
                start = time.time()
                flying = False
                while time.time() - start < 1:
                    self.send_resonance_key(interval=0.1)
                    self.task.next_frame()
                    self.click(interval=0.1)
                    if flying := self.wind_routine_flying():
                        break
                use_skyfall_severance = self.use_skyfall_severance
                if flying:
                    self.wind_routine_click_while_flying(1.6 if use_skyfall_severance else 1.74)
                if use_skyfall_severance and self.click_resonance(send_click=False)[0]:
                    self.wind_routine_click_while_flying(1)
        self.click_liberation(send_click=True)
        self.wind_routine_wait_down()

    def wind_routine_click_while_flying(self, duration, interval=0.1):
        start = time.time()
        while time.time() - start < duration:
            if not self.wind_routine_flying():
                return False
            self.click(interval=0.1)
            self.sleep(interval)
        return True

    def wind_routine_flying(self):
        if self.task.has_lavitator:
            return self.flying()
        elif self.current_resonance() > 0.15:
            return True

    def wind_routine_wait_down(self, check_forte_full=True):
        if self.wind_routine_flying():
            if self.task.has_lavitator:
                self.wait_down()
            else:
                self.task.wait_until(lambda: self.current_resonance() < 0.15,
                                     post_action=lambda: self.click(interval=0.1, after_sleep=0.01), time_out=2.5)
        if check_forte_full:
            self.sleep(0.03)
            if self.is_forte_full():
                self.send_resonance_key()
        else:
            self.sleep(0.01)
        return True

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
        self.wait_down()
        self.click_echo()
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber or res):
            self.continues_normal_attack(1)