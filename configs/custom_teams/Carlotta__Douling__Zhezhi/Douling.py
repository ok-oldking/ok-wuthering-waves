import time

from ok import Box

from src.char.BaseChar import SwitchPriority  # 导入切人优先级枚举
from src.char.Douling import Douling as BuiltinDouling  # 导入内置卜灵（釉瑚）类，作为自定义类的父类
from src.utils.guaxiang import recognize_guaxiang as detect_guaxiang


_ROTATION_PHASE_ATTR = "_carlotta_douling_zhezhi_phase"  # 挂在 task 上、三角色共享的轮切阶段属性名
_ROTATION_HANDOFF_GUARD_ATTR = "_carlotta_douling_zhezhi_handoff_guard_until"  # 切人前后短时跳过目标重锁
_START_CARLOTTA = "start_carlotta"  # 阶段常量：开场珂莱塔
_START_DOULING = "start_douling"  # 阶段常量：开场卜灵
_DOULING_LOOP = "douling_loop"  # 阶段常量：卜灵循环轮
_ZHEZHI_BRIDGE = "zhezhi_bridge"  # 阶段常量：折枝衔接轮


class Douling(BuiltinDouling):  # 自定义卜灵：按固定轴连招覆盖默认行为
    NORMAL_ATTACK_INTERVAL = 0.3  # 两次普攻之间的间隔（秒）
    SKILL_INPUT_INTERVAL = 0.1  # 技能按键之后的等待间隔（秒）
    JUMP_INTERVAL = 0.3  # 跳跃按键之后的等待间隔（秒）
    RESONANCE_ANIMATION_WAIT = 0.8  # 释放共鸣技能后等待技能动画完整结束的时间（秒）
    LONG_HEAVY_DURATION = 2.5  # 长按重击的持续时间（秒）
    LIBERATION_READY_WAIT = 0.1  # 大招就绪时开启前的等待时间（秒）
    SWITCH_COMBAT_GUARD = 6.0  # 覆盖 switch_next_char 最长等待窗口
    POST_SWITCH_COMBAT_GUARD = 1.0  # 覆盖切人返回到下一角色 do_perform 之间的战斗检查

    def reset_state(self):  # 状态重置：每次轮换开始时调用
        super().reset_state()  # 先执行父类的重置逻辑
        self.check_f_on_switch = False  # 切人时不检查 F 协奏提示
        self._performing_fixed_rotation = False  # 当前是否正在执行固定轴（包含段末切人）
        self._waiting_for_guaxiang = False
        setattr(self.task, _ROTATION_HANDOFF_GUARD_ATTR, 0.0)  # 清理上一场战斗遗留的切人保护
        setattr(self.task, _ROTATION_PHASE_ATTR, _START_CARLOTTA)  # 把队伍阶段重置为开场珂莱塔

    def skip_combat_check(self):  # 固定轴与切人交接期间不因目标框短暂消失而误判退战
        if getattr(self, '_waiting_for_guaxiang', False):
            return False  # 普攻补卦象可能持续较久，必须允许正常退战检查
        return (
            super().skip_combat_check()
            or getattr(self, '_performing_fixed_rotation', False)
            or time.monotonic() < getattr(self.task, _ROTATION_HANDOFF_GUARD_ATTR, 0.0)
        )

    def switch_next_char(self, *args, **kwargs):  # 保护切人过程及下一角色开始行动前的空档
        setattr(
            self.task,
            _ROTATION_HANDOFF_GUARD_ATTR,
            time.monotonic() + self.SWITCH_COMBAT_GUARD,
        )
        try:
            return super().switch_next_char(*args, **kwargs)
        finally:
            setattr(
                self.task,
                _ROTATION_HANDOFF_GUARD_ATTR,
                time.monotonic() + self.POST_SWITCH_COMBAT_GUARD,
            )

    def _rotation_phase(self):  # 读取当前队伍轮切阶段
        return getattr(self.task, _ROTATION_PHASE_ATTR, _START_CARLOTTA)  # 从 task 上取阶段，缺省为开场珂莱塔

    def _switch_to_phase(self, phase):  # 更新阶段并切换到下一个角色
        setattr(self.task, _ROTATION_PHASE_ATTR, phase)  # 写入下一个阶段标记
        return self.switch_next_char()  # 切换下一个角色并返回其结果

    def _wait_for_entry(self):  # 等待入场动画结束再开始连招
        self.wait_intro(click=False)  # 等待登场 intro，不点击
        if self.flying():  # 如果角色处于空中/飞行状态
            self.wait_down(click=False)  # 等待落地，不点击

    def _tap_normal(self, count=1):  # 按固定间隔连点 count 次普攻
        for _ in range(count):  # 循环指定次数
            self.normal_attack()  # 点击一次普攻
            self.sleep(self.NORMAL_ATTACK_INTERVAL)  # 等待普攻间隔

    def _tap_resonance(self, post_sleep=None):  # 释放一次共鸣技能（E），可自定义按键后等待
        self.check_combat()  # 检查是否仍在战斗中，否则抛出中断
        if not self.resonance_available():  # 共鸣技能不可用（未就绪/冷却中）
            self.logger.warning('Douling resonance unavailable, skip fixed-axis E')  # 记录警告日志
            return False  # 返回失败，跳过本段

        if post_sleep is None:  # 未显式指定按键后等待时间时
            post_sleep = self.SKILL_INPUT_INTERVAL  # 使用默认的技能输入间隔
        self.record_resonance_use()  # 记录一次共鸣技能使用（统计用）
        self.send_resonance_key(post_sleep=post_sleep)  # 发送 E 键并按参数等待
        return True  # 释放成功

    def _jump(self):  # 执行一次跳跃
        self.check_combat()  # 确认仍在战斗中
        self.task.jump(after_sleep=self.JUMP_INTERVAL)  # 发送跳跃键并等待

    def _hold_long_heavy(self):  # 长按重击（蓄力重击）
        self.check_combat()  # 确认仍在战斗中
        try:  # 捕获重击过程中可能抛出的异常
            self.heavy_attack(duration=self.LONG_HEAVY_DURATION)  # 长按重击指定时长
        except Exception:  # 异常兜底，防止鼠标卡在按下状态
            # BaseChar.heavy_attack 中途抛错时尚未执行 mouse_up。
            self.task.mouse_up()  # 补一次松开鼠标左键
            raise  # 重新抛出异常交给上层处理

    def _tap_echo(self):  # 释放声骸技能（Q）
        self.check_combat()  # 确认仍在战斗中
        sent = self.click_echo(time_out=0)  # 立即尝试点击声骸，不等待
        if sent:  # 声骸发送成功
            self.sleep(self.SKILL_INPUT_INTERVAL)  # 等待技能输入间隔
        else:  # 声骸不可用
            self.logger.warning('Douling echo unavailable, skip fixed-axis Q')  # 记录警告日志
        return bool(sent)  # 返回是否发送成功

    def _cast_liberation(self):  # 尝试开启共鸣解放（大招）
        self.check_combat()  # 确认仍在战斗中
        return bool(self.click_liberation(  # 复用继承的大招开启逻辑
            send_click=False,  # 不直接发送点击，由内部按需处理
            wait_if_cd_ready=self.LIBERATION_READY_WAIT,  # 大招就绪时先等待一小段
            click_f=False,  # 不点击 F 键
        ))  # 返回是否成功开启大招

    def recognize_guaxiang(self, sample_point='manual'):
        """识别并记录一帧；不确定时返回 None，由调用方决定是否继续。"""
        start = time.perf_counter()
        try:
            hud_visible = self.task.in_team()[0]
            captured_frame = self.task.frame
            frame = captured_frame.copy() if captured_frame is not None else None
            result = detect_guaxiang(frame, hud_visible=hud_visible)
            elapsed_ms = (time.perf_counter() - start) * 1000
            screenshot_name = 'unavailable'
            if frame is not None:
                screenshot_name = f'guaxiang/{sample_point}_{time.time_ns()}'
                try:
                    # 后台保存识别使用的同一帧，不重新截图，也不等待写盘。
                    self.task.screenshot(screenshot_name, frame=frame, show_box=False)
                except Exception as error:
                    self.logger.warning(f'[DoulingScreenshot] name={screenshot_name} error={error}')
                    screenshot_name = 'failed'
            context = f'point={sample_point} screenshot_name={screenshot_name}'
            if result.sequence is None:
                self.logger.info(
                    f'[DoulingRecognition] status=uncertain reason={result.reason} '
                    f'elapsed_ms={elapsed_ms:.2f} {context}')
            else:
                sequence = ','.join(result.sequence) or '[]'
                self.logger.info(
                    f'[DoulingRecognition] count={len(result.sequence)} sequence={sequence} '
                    f'elapsed_ms={elapsed_ms:.2f} {context}')
            if self.task.debug:
                regions = [Box(*result.region, name='douling_guaxiang_region')] if result.region else []
                self.task.draw_boxes('douling_guaxiang_region', regions)
                boxes = [Box(*item.box, confidence=item.score,
                             name=f'{item.color} match={item.score:.2f} color={item.color_score:.2f}')
                         for item in result.detections]
                self.task.draw_boxes('douling_guaxiang_matches', boxes)
            return result.sequence
        except Exception as error:
            self.logger.warning(f'[DoulingRecognition] status=uncertain error={error}')
            return None

    def _normal_attack_until_four_guaxiang(self):
        """跳 a 后持续普攻补卦象，只有确认四个才返回并执行后续动作。"""
        self._waiting_for_guaxiang = True
        try:
            while True:
                frame = self.task.next_frame()  # 刷新画面，同时响应任务暂停/停止
                self.check_combat()
                # 抓帧失败时不沿用旧的四卦象结果，继续普攻并等待下次刷新。
                sequence = self.recognize_guaxiang('before_heavy') if frame is not None else None
                if sequence is not None and len(sequence) == 4:
                    self.logger.info('[DoulingGuaxiang] count=4 action=continue_to_heavy')
                    return
                count = 'uncertain' if sequence is None else len(sequence)
                self.logger.info(f'[DoulingGuaxiang] count={count} action=normal_attack')
                self._tap_normal()  # 沿用 0.3 秒普攻间隔，不重复开头的 E 或跳跃
        finally:
            self._waiting_for_guaxiang = False

    def do_perform(self):  # 用角色级状态保护整段固定轴，并在异常时恢复战斗检查
        self._performing_fixed_rotation = True
        setattr(self.task, _ROTATION_HANDOFF_GUARD_ATTR, 0.0)  # 当前角色已接管，结束上一次切人保护
        try:
            return self._do_fixed_rotation()
        finally:
            self._performing_fixed_rotation = False

    def _do_fixed_rotation(self):  # 轮到本角色时执行对应阶段的动作
        phase = self._rotation_phase()  # 读取当前阶段
        self.logger.info(f'fixed-axis phase {phase}')  # 实战日志中记录固定轴所处阶段
        if phase not in {_START_DOULING, _DOULING_LOOP}:  # 不是卜灵的阶段
            return self.switch_next_char()  # 不执行动作，直接切换下一个角色

        self._wait_for_entry()  # 等待入场动画结束
        self.recognize_guaxiang('entry')  # 仅记录当前序列并保存截图，不改变出招

        # 启动轴和循环轴：aa e，等待 0.8 秒，再 a 跳 a；普攻补满四卦象后 ZZQR。
        self._tap_normal(2)  # 连点两次普攻（aa）
        resonance_sent = self._tap_resonance(post_sleep=0)  # 释放共鸣 E，按键后不等待
        if resonance_sent:  # E 释放成功时
            self.sleep(self.RESONANCE_ANIMATION_WAIT)  # 整段固定轴已有保护，等待 0.8 秒技能动画
        self._tap_normal()  # 普攻一次（a）
        self._jump()  # 跳跃一次（跳）
        self._tap_normal()  # 普攻一次（a）
        self._normal_attack_until_four_guaxiang()  # 未满或不确定时持续普攻，确认四个才继续
        self._hold_long_heavy()  # 长按重击（ZZ 蓄力）
        self._tap_echo()  # 释放声骸 Q

        if not self._cast_liberation():  # 尝试开启大招（R），失败时
            self.logger.warning('Douling liberation did not start, continue fixed-axis segment')  # 记录警告并继续后续段
        return self._switch_to_phase(_ZHEZHI_BRIDGE)  # 进入折枝衔接阶段并切人

    def healer_full_con_switch_locked(self):  # 覆盖治疗角色满协奏锁切换的判定
        return False  # 卜灵本队不作治疗切换锁，始终允许按固定轴切换

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):  # 返回本角色的切人优先级
        if self._rotation_phase() in {_START_DOULING, _DOULING_LOOP}:  # 当前是卜灵的两个阶段
            return SwitchPriority.MUST  # 必须切到本角色
        return SwitchPriority.NO  # 其余阶段不主动要求切人
