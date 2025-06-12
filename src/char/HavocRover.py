import time
from src.char.BaseChar import BaseChar, Elements


class HavocRover(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset_state(self):
        self.ring_index = -1
        super().reset_state()

    def do_perform(self):
        if self.ring_index == -1:
            self.task._ensure_ring_index()
        if not self.has_intro:
            self.sleep(0.01)
        if self.ring_index == Elements.HAVOC:
            self.intro_motion_freeze_duration = 0.64
            self.perform_havoc_routine()
        elif self.ring_index == Elements.SPECTRO:
            self.intro_motion_freeze_duration = 0.92
            self.perform_spectro_routine()
        elif self.ring_index == Elements.WIND:
            self.intro_motion_freeze_duration = 0.52
            self.perform_wind_routine()
        else:
            self.perform_basic_routine()
        self.switch_next_char()

    def perform_spectro_routine(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.wait_down()
        self.aftertune_combo()
        if self.echo_available():
            self.click_echo(time_out=0.2)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
                if not self.liberation_available():
                    return
        self.check_combat()
        if self.liberation_available():
            self.click_liberation()
        else:
            self.click_resonance()

    def aftertune_combo(self):
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)
    
    def perform_havoc_routine(self):
        liber = False
        if self.has_intro:
            start = time.time()
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
            if not self.liberation_available():
                att_time = 1.35 - (time.time() - start)
                if att_time > 0:
                    self.continues_normal_attack(att_time)
            else:
                liber = True
        else:
            self.wait_down()
        if liber or self.liberation_available():
            if self.is_forte_full():
                self.check_combat()
                self.task.mouse_down()
                start = time.time()
                while True:
                    current = time.time()
                    if (current - start > 0.5 and not self.is_forte_full()) or current - start > 2:
                        break
                    self.task.next_frame()
                self.task.mouse_up()
            elif self.has_intro:
                self.task.wait_until(lambda: self.current_liberation() > 0, post_action=self.click_with_interval, time_out=0.8)
            if self.click_liberation(send_click=True):
                self.liber_available = False
        self.continues_normal_attack(1)
        if self.click_resonance(send_click=True)[0]:
            return
        if self.echo_available():
            self.click_echo(time_out=0.1)
    
    # TODO: 尚未支持其他效应转风蚀
    # TODO: 存在<逆势回击>导致轴长改变打不满两次<抃风儛润>的问题，应当可以用一链提供的buff使用find_one进行优化
    def perform_wind_routine(self):
        if self.has_intro:
            self.continues_normal_attack(2.3, interval=0.15)
            return
        if self.current_resonance() > 0.25:
            self.task.wait_until(lambda: self.current_resonance() < 0.23, post_action=self.click_with_interval, time_out=0.7)
        liber = False
        if self.resonance_available() and not self.is_forte_full():
            if self.echo_available():
                self.click_echo(time_out=0.1)
            self.send_resonance_key()
            self.continues_normal_attack(1.9, interval=0.15)
            liber = self.liberation_available()
            if not liber:
                self.continues_normal_attack(0.3, interval=0.15)
                return
        if liber or self.liberation_available():
            self.click_liberation()
        if self.is_forte_full():
            self.send_resonance_key()

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
            self.wait_down()
        if self.echo_available():
            self.click_echo(time_out=0.2)
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber and res):
            self.continues_normal_attack(1)

    def do_fast_perform(self):
        if self.ring_index == Elements.WIND:
            self.fast_perform_wind_routine()
        else:
            self.do_perform()
            return
        self.switch_next_char()

    def fast_perform_wind_routine(self):
        if self.has_intro:
            self.continues_normal_attack(0.5, interval=0.15)
            return
        att_time = 1 - (time.time() - self.last_perform)
        if att_time > 0:
            self.continues_normal_attack(att_time)
        if self.is_forte_full():
            self.send_resonance_key()