"""低血量战斗中断功能的集成测试。

使用 TaskTestCase 加载真实 AutoCombatTask 实例，配合血条截图验证
_detect_player_hp 的 OCR 读取、_check_hp_interrupt 的中断逻辑、
next_frame 的 hook 触发，以及 LowHpException 的继承关系。
"""
import time
import unittest

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask
from src.task.BaseCombatTask import (CharDeadException, LowHpException,
                                     NotInCombatException)

config['debug'] = True

# 三张血条截图的 OCR 基准读数 (current/max)
HIGH_HP = 18704 / 19156   # health_high.png ≈ 97.6%
MID_HP = 27317 / 50865    # health_mid.png ≈ 53.7%
LOW_HP = 1973 / 15335    # health_low.png ≈ 12.9%


class TestLowHpInterrupt(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def setUp(self):
        # set_image 内部会调 next_frame，复位避免上个测试遗留状态触发检测
        self.task._hp_check_enabled = False
        self.task._hp_check_paused = False
        self.task._low_hp_count = 0

    def _reset_hp_state(self, threshold=0.3):
        """重置 HP 检测相关字段，避免用例间互相干扰。"""
        self.task._hp_threshold = threshold
        self.task._low_hp_count = 0
        self.task._last_low_hp_trigger = 0
        self.task._hp_check_paused = False
        self.task._hp_check_enabled = False
        self.task._last_hp_check = 0

    # ===== _detect_player_hp OCR 读取 =====

    def test_detect_hp_high(self):
        """高血量截图应读出约 97.6%。"""
        self.set_image('tests/images/health_high.png')
        hp = self.task._detect_player_hp()
        self.assertIsNotNone(hp)
        self.assertAlmostEqual(hp, HIGH_HP, places=2)

    def test_detect_hp_mid(self):
        """中血量截图应读出约 53.7%。"""
        self.set_image('tests/images/health_mid.png')
        hp = self.task._detect_player_hp()
        self.assertIsNotNone(hp)
        self.assertAlmostEqual(hp, MID_HP, places=2)

    def test_detect_hp_low(self):
        """低血量截图应读出约 12.9%。"""
        self.set_image('tests/images/health_low.png')
        hp = self.task._detect_player_hp()
        self.assertIsNotNone(hp)
        self.assertAlmostEqual(hp, LOW_HP, places=2)

    def test_detect_hp_range_valid(self):
        """血量百分比应在 [0, 1] 区间内。"""
        for img in ('tests/images/health_high.png',
                    'tests/images/health_mid.png',
                    'tests/images/health_low.png'):
            with self.subTest(img=img):
                self.set_image(img)
                hp = self.task._detect_player_hp()
                self.assertIsNotNone(hp)
                self.assertGreaterEqual(hp, 0.0)
                self.assertLessEqual(hp, 1.0)

    # ===== _check_hp_interrupt 中断逻辑 =====

    def test_check_interrupt_no_raise_on_high_hp(self):
        """高血量时不应抛异常，计数归零。"""
        self.set_image('tests/images/health_high.png')
        self._reset_hp_state(threshold=0.3)
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 0)

    def test_check_interrupt_counts_low_hp_once(self):
        """低血量第一次只计数+1，不立即抛 (防 OCR 单次误读)。"""
        self.set_image('tests/images/health_low.png')
        self._reset_hp_state(threshold=0.3)
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 1)

    def test_check_interrupt_raises_after_two_low_reads(self):
        """连续 2 次低血量读数后应抛 LowHpException。"""
        self.set_image('tests/images/health_low.png')
        self._reset_hp_state(threshold=0.3)
        self.task._check_hp_interrupt()  # 第一次计数
        self.assertEqual(self.task._low_hp_count, 1)
        with self.assertRaises(LowHpException):
            self.task._check_hp_interrupt()  # 第二次抛
        self.assertEqual(self.task._low_hp_count, 0)  # 抛后重置

    def test_check_interrupt_resets_count_on_high_hp(self):
        """低血量计数后读到高血量应重置计数。"""
        self.set_image('tests/images/health_low.png')
        self._reset_hp_state(threshold=0.3)
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 1)
        self.set_image('tests/images/health_high.png')
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 0)

    def test_check_interrupt_cooldown_blocks_detection(self):
        """切换失败冷却期内不应检测 HP。"""
        self.set_image('tests/images/health_low.png')
        self._reset_hp_state(threshold=0.3)
        self.task._last_low_hp_trigger = time.time()  # 刚失败，进入冷却
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 0)

    def test_check_interrupt_threshold_boundary(self):
        """阈值边界：血量恰等于阈值时不应触发 (用 < 而非 <=)。"""
        self.set_image('tests/images/health_low.png')
        self._reset_hp_state(threshold=LOW_HP)  # 阈值=当前血量
        self.task._check_hp_interrupt()
        self.assertEqual(self.task._low_hp_count, 0)  # hp < threshold 为 False

    # ===== next_frame hook =====
    # 注意: set_image 内部会调 next_frame，故先复位 enabled=False 再 set_image，
    #       然后设置 enabled，并重置 _last_hp_check 绕过节流，再手动调 next_frame。

    def test_next_frame_triggers_hp_check_when_enabled(self):
        """enabled=True 时 next_frame 应触发 HP 检测。"""
        self._reset_hp_state(threshold=0.3)
        self.set_image('tests/images/health_low.png')
        self.task._hp_check_enabled = True
        self.task._last_hp_check = 0  # 绕过节流
        self.task.next_frame()
        self.assertEqual(self.task._low_hp_count, 1)

    def test_next_frame_skips_hp_check_when_disabled(self):
        """enabled=False 时 next_frame 不应检测 HP。"""
        self._reset_hp_state(threshold=0.3)
        self.set_image('tests/images/health_low.png')
        self.task._hp_check_enabled = False
        self.task._last_hp_check = 0
        self.task.next_frame()
        self.assertEqual(self.task._low_hp_count, 0)

    def test_next_frame_skips_hp_check_when_paused(self):
        """paused=True 时 next_frame 不应检测 HP。"""
        self._reset_hp_state(threshold=0.3)
        self.set_image('tests/images/health_low.png')
        self.task._hp_check_enabled = True
        self.task._hp_check_paused = True
        self.task._last_hp_check = 0
        self.task.next_frame()
        self.assertEqual(self.task._low_hp_count, 0)

    def test_next_frame_raises_after_two_low_reads(self):
        """enabled 时连续两次 next_frame 应在第二次抛 LowHpException。"""
        self._reset_hp_state(threshold=0.3)
        self.set_image('tests/images/health_low.png')
        self.task._hp_check_enabled = True
        self.task._last_hp_check = 0  # 第一次绕过节流
        self.task.next_frame()  # 第一次计数
        self.assertEqual(self.task._low_hp_count, 1)
        self.task._last_hp_check = 0  # 第二次也绕过节流
        with self.assertRaises(LowHpException):
            self.task.next_frame()  # 第二次抛

    # ===== LowHpException 继承关系 =====

    def test_low_hp_exception_is_exception(self):
        self.assertTrue(issubclass(LowHpException, Exception))

    def test_low_hp_exception_not_not_in_combat(self):
        """不应继承 NotInCombatException，否则被 run() 误捕导致 break。"""
        self.assertFalse(issubclass(LowHpException, NotInCombatException))

    def test_low_hp_exception_not_char_dead(self):
        self.assertFalse(issubclass(LowHpException, CharDeadException))

    def test_low_hp_not_caught_by_not_in_combat_handler(self):
        """LowHpException 不应被 except NotInCombatException 捕获。"""
        raised = False
        try:
            try:
                raise LowHpException("low hp")
            except NotInCombatException:
                pass  # 不应走到这里
        except LowHpException:
            raised = True
        self.assertTrue(raised)

    # ===== config 字段 =====

    def test_config_has_low_hp_keys(self):
        self.assertIn('Low HP Healer Switch', self.task.default_config)
        self.assertIn('Low HP Threshold', self.task.default_config)

    def test_config_descriptions_present(self):
        self.assertIn('Low HP Healer Switch', self.task.config_description)
        self.assertIn('Low HP Threshold', self.task.config_description)


if __name__ == '__main__':
    unittest.main()
