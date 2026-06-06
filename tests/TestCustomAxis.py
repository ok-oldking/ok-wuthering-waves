import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.char.BaseChar import CharType
from src.char.Camellya import Camellya
from src.char.Sanhua import Sanhua
from src.task.AutoCombatTask import AutoCombatTask, CUSTOM_AXIS_ACTION_RETRY_INTERVAL
from src.task.AutoStartAxisFTask import AutoStartAxisFTask
from src.task.CustomAxisGlobalFTask import CustomAxisGlobalFTask
from src.task.CustomAxisRetryTask import CustomAxisRetryTask
from src.ui.CustomAxisEditor import (
    ACTION_LABELS,
    CHARACTER_DISPLAY_BY_KEY,
    FALLBACK_ACTION_LABELS,
    AxisAction,
    AxisStep,
    CustomAxisEditorWidget,
    action_display,
)


class FakeStepList:
    def __init__(self, row=-1):
        self.row = row

    def currentRow(self):
        return self.row

    def setCurrentRow(self, row):
        self.row = row


class FakeSpin:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class FakeRoleCombo:
    def __init__(self, value):
        self.value = value

    def currentData(self, role):
        return self.value

    def currentText(self):
        return self.value

    def setCurrentIndex(self, index):
        pass


class FakeConditionCombo:
    def __init__(self, text=""):
        self.text = text

    def currentText(self):
        return self.text


class FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class FakeProfileCombo:
    def __init__(self):
        self.items = []
        self.index = -1

    def clear(self):
        self.items.clear()

    def addItem(self, text, data):
        self.items.append((text, data))

    def setCurrentIndex(self, index):
        self.index = index


class FakeScriptText:
    def __init__(self, text=""):
        self.text = text

    def toPlainText(self):
        return self.text

    def setPlainText(self, text):
        self.text = text


class FakePreview:
    def __init__(self):
        self.saved_paths = []

    def save_image(self, path):
        self.saved_paths.append(path)


class FakeBox:
    def __init__(self, name="box"):
        self.name = name
        self.width = 10
        self.height = 10

    def copy(self, **kwargs):
        return FakeBox(kwargs.get("name", self.name))


class FakeScene:
    def __init__(self, in_combat=None):
        self._in_combat = in_combat

    def in_team(self, condition):
        return True

    def in_combat(self):
        return self._in_combat


class FakeToggleTask:
    def __init__(self, enabled):
        self.enabled = enabled


class FakeCombatTask:
    def __init__(self):
        self.started = 0

    def run_custom_axis_from_f_start(self):
        self.started += 1
        return True


class TestCustomAxisEditor(unittest.TestCase):

    def make_editor(self, selected_row=-1, role="Chisa", condition=""):
        editor = CustomAxisEditorWidget.__new__(CustomAxisEditorWidget)
        editor.current_axis_phase = "startup"
        editor.team_keys = ["Chisa", "Denia", "Aemeath"]
        editor.startup_steps = []
        editor.loop_steps = []
        editor.current_actions = []
        editor.current_fallback_actions = []
        editor.editing_step_index = None
        editor.step_list = FakeStepList(selected_row)
        editor.role_combo = FakeRoleCombo(role)
        editor.condition_combo = FakeConditionCombo(condition)
        editor._refresh_ui = lambda: None
        return editor

    def test_selected_step_insert_and_append_are_separate_actions(self):
        editor = self.make_editor(selected_row=1, role="Denia")
        editor.startup_steps = [
            AxisStep("Chisa", [AxisAction("e")]),
            AxisStep("Aemeath", [AxisAction("q")]),
        ]

        editor.current_actions = [AxisAction("r")]
        editor._add_step()
        self.assertEqual([step.role for step in editor.startup_steps], ["Chisa", "Denia", "Aemeath"])
        self.assertEqual(editor.startup_steps[1].actions[0].name, "r")

        editor.role_combo = FakeRoleCombo("Aemeath")
        editor.current_actions = [AxisAction("e")]
        editor._append_step()
        self.assertEqual([step.role for step in editor.startup_steps], ["Chisa", "Denia", "Aemeath", "Aemeath"])
        self.assertEqual(editor.startup_steps[-1].actions[0].name, "e")

    def test_action_buttons_include_core_and_movement_actions(self):
        self.assertEqual(
            list(ACTION_LABELS.keys()),
            ["R", "E", "E动画", "E等待", "F一次", "F持续检测", "Q", "A", "等待", "重击", "角色流程", "起跳", "闪避"],
        )

    def test_fallback_buttons_include_heavy_until_con(self):
        self.assertIn("平A到条件满足", FALLBACK_ACTION_LABELS)
        self.assertEqual(FALLBACK_ACTION_LABELS["平A到条件满足"], "attack_until_condition")
        self.assertNotIn("平A一小段", FALLBACK_ACTION_LABELS)
        self.assertIn("重击到条件满足", FALLBACK_ACTION_LABELS)
        self.assertEqual(FALLBACK_ACTION_LABELS["重击到条件满足"], "heavy_until_condition")
        self.assertIn("重击到协奏满", FALLBACK_ACTION_LABELS)
        self.assertEqual(FALLBACK_ACTION_LABELS["重击到协奏满"], "heavy_until_con")
        self.assertEqual(FALLBACK_ACTION_LABELS["等待"], "wait")
        self.assertEqual(FALLBACK_ACTION_LABELS["E动画"], "e_anim")

    def test_action_seconds_keep_two_decimal_precision(self):
        action = AxisAction("attack", 0.25)
        self.assertEqual(action.to_script(), "attack:0.25")
        self.assertIn("0.25 秒", action_display(action))

        flow = AxisAction("role_flow")
        self.assertEqual(flow.to_script(), "role_flow")
        self.assertIn("角色流程", action_display(flow))

    def test_e_wait_button_adds_timed_e_action(self):
        editor = self.make_editor()
        editor.duration_spin = FakeSpin(1.25)
        editor.action_list = FakeStepList()
        editor._refresh_current_actions = lambda: None

        editor._add_action("e_wait")

        self.assertEqual(editor.current_actions[0].name, "e")
        self.assertEqual(editor.current_actions[0].value, 1.25)
        self.assertEqual(editor.current_actions[0].to_script(), "e:1.25")

    def test_e_anim_button_adds_animation_aware_e_action(self):
        editor = self.make_editor()
        editor.count_spin = FakeSpin(1)
        editor.action_list = FakeStepList()
        editor._refresh_current_actions = lambda: None

        editor._add_action("e_anim")

        self.assertEqual(editor.current_actions[0].name, "e_anim")
        self.assertIsNone(editor.current_actions[0].value)
        self.assertEqual(editor.current_actions[0].to_script(), "e_anim")

    def test_wait_button_adds_timed_empty_wait_action(self):
        editor = self.make_editor()
        editor.duration_spin = FakeSpin(0.15)
        editor.action_list = FakeStepList()
        editor._refresh_current_actions = lambda: None

        editor._add_action("wait")

        self.assertEqual(editor.current_actions[0].name, "wait")
        self.assertEqual(editor.current_actions[0].value, 0.15)
        self.assertEqual(editor.current_actions[0].to_script(), "wait:0.15")

    def test_role_flow_button_adds_without_duration(self):
        editor = self.make_editor()
        editor.count_spin = FakeSpin(1)
        editor.action_list = FakeStepList()
        editor._refresh_current_actions = lambda: None

        editor._add_action("role_flow")

        self.assertEqual(editor.current_actions[0].name, "role_flow")
        self.assertIsNone(editor.current_actions[0].value)
        self.assertEqual(editor.current_actions[0].to_script(), "role_flow")

    def test_fallback_actions_use_separate_duration_spin(self):
        editor = self.make_editor()
        editor.fallback_duration_spin = FakeSpin(2.75)
        editor.fallback_action_list = FakeStepList()
        editor._refresh_current_fallback_actions = lambda: None

        editor._add_fallback_action("heavy_until_condition")

        self.assertEqual(editor.current_fallback_actions[0].name, "heavy_until_condition")
        self.assertEqual(editor.current_fallback_actions[0].value, 2.75)
        self.assertEqual(editor.current_fallback_actions[0].to_script(), "heavy_until_condition:2.75")

    def test_fallback_attack_button_adds_attack_until_condition(self):
        editor = self.make_editor()
        editor.fallback_duration_spin = FakeSpin(2.75)
        editor.fallback_action_list = FakeStepList()
        editor._refresh_current_fallback_actions = lambda: None

        editor._add_fallback_action("attack_until_condition")

        self.assertEqual(editor.current_fallback_actions[0].name, "attack_until_condition")
        self.assertEqual(editor.current_fallback_actions[0].value, 2.75)
        self.assertEqual(editor.current_fallback_actions[0].to_script(), "attack_until_condition:2.75")

    def test_current_actions_can_delete_and_reorder_one_item(self):
        editor = self.make_editor()
        editor.action_list = FakeStepList(1)
        editor._refresh_current_actions = lambda: None
        editor.current_actions = [AxisAction("e"), AxisAction("r"), AxisAction("q")]

        editor._delete_selected_action()
        self.assertEqual([action.name for action in editor.current_actions], ["e", "q"])
        self.assertEqual(editor.action_list.currentRow(), 1)

        editor._move_selected_action(-1)
        self.assertEqual([action.name for action in editor.current_actions], ["q", "e"])
        self.assertEqual(editor.action_list.currentRow(), 0)

    def test_step_can_keep_fallback_actions_for_unmet_condition(self):
        editor = self.make_editor(role="Chisa", condition="千咲.技能==1")
        editor.current_actions = [AxisAction("e")]
        editor.current_fallback_actions = [AxisAction("attack_until_con", 4)]

        step = editor._new_step_from_editor()
        self.assertEqual(step.condition, "千咲.技能==1")
        self.assertEqual([action.name for action in step.fallback_actions], ["attack_until_con"])
        self.assertEqual(step.fallback_role, "Chisa")
        self.assertIn("未满足 Chisa: attack_until_con:4", step.to_script())

        parsed = AxisStep.from_raw("Chisa: e | 条件 千咲.技能==1 | 未满足 Chisa: attack_until_con:4")
        self.assertEqual(parsed.condition, "千咲.技能==1")
        self.assertEqual(parsed.fallback_role, "Chisa")
        self.assertEqual(parsed.fallback_actions[0].name, "attack_until_con")
        self.assertEqual(parsed.fallback_actions[0].value, 4)

        old_style = AxisStep.from_raw("Chisa: e | 条件 千咲.技能==1 | 未满足 attack_until_con:4")
        self.assertEqual(old_style.fallback_role, "")
        self.assertEqual(old_style.fallback_actions[0].name, "attack_until_con")

    def test_condition_options_follow_current_team(self):
        editor = self.make_editor()
        editor.team_keys = ["Verina", "Sanhua", "Jinhsi"]
        options = editor._condition_options()
        self.assertIn("维里奈.buff<=2", options)
        self.assertIn("散华.协奏满==1", options)
        self.assertIn("今汐.声骸==1", options)

    def test_rover_options_include_supported_rover_forms(self):
        self.assertEqual(CHARACTER_DISPLAY_BY_KEY["HavocRover"], "暗主 / HavocRover")
        self.assertEqual(CHARACTER_DISPLAY_BY_KEY["SpectroRover"], "光主 / SpectroRover")
        self.assertEqual(CHARACTER_DISPLAY_BY_KEY["AeroRover"], "风主 / AeroRover")

    def test_douling_display_uses_buling_name(self):
        self.assertEqual(CHARACTER_DISPLAY_BY_KEY["Douling"], "卜灵 / Douling")

    def test_pasted_script_syncs_back_to_startup_and_loop_steps(self):
        editor = self.make_editor()
        editor.script_text = FakeScriptText(
            "# ===== 启动轴 =====\n"
            "Sanhua: heavy:0.85 | 条件 散华.技能==1\n"
            "\n"
            "# ===== 循环轴 =====\n"
            "Chisa: e | 条件 千咲.技能==1 | 未满足 Chisa: attack_until_con:4\n"
        )
        editor.startup_steps = [AxisStep("Aemeath", [AxisAction("q")])]
        editor.loop_steps = []

        editor._sync_script_text_to_steps()

        self.assertEqual([step.role for step in editor.startup_steps], ["Sanhua"])
        self.assertEqual(editor.startup_steps[0].actions[0].name, "heavy")
        self.assertEqual(editor.startup_steps[0].actions[0].value, 0.85)
        self.assertEqual(editor.startup_steps[0].condition, "散华.技能==1")
        self.assertEqual([step.role for step in editor.loop_steps], ["Chisa"])
        self.assertEqual(editor.loop_steps[0].fallback_role, "Chisa")
        self.assertEqual(editor.loop_steps[0].fallback_actions[0].name, "attack_until_con")

    def test_pasted_script_without_section_uses_current_axis_phase(self):
        editor = self.make_editor()
        editor.current_axis_phase = "startup"
        editor.script_text = FakeScriptText("Sanhua: heavy:0.85\n")

        editor._sync_script_text_to_steps()

        self.assertEqual([step.role for step in editor.startup_steps], ["Sanhua"])
        self.assertEqual(editor.loop_steps, [])

    def test_save_profiles_refreshes_profile_combo_label(self):
        editor = self.make_editor()
        editor.profiles = [{
            "name": "旧名字",
            "team": ["Chisa", "Denia", "Aemeath"],
            "startup_steps": [],
            "loop_steps": [],
        }]
        editor.current_profile_index = 0
        editor.profile_name_edit = FakeLineEdit("新名字")
        editor.profile_combo = FakeProfileCombo()
        editor.script_text = FakeScriptText("")
        editor._refresh_ui = lambda: None
        editor._sync_script_text_to_steps = lambda: None

        with TemporaryDirectory() as tmp_dir:
            editor.profiles_file = Path(tmp_dir) / "custom_axis_profiles.json"
            with patch("src.ui.CustomAxisEditor.QMessageBox.information"):
                editor._save_profiles()

        self.assertIn("新名字", editor.profile_combo.items[0][0])

    def test_save_all_shows_one_message(self):
        editor = self.make_editor()
        editor.profiles = [{
            "name": "测试轴",
            "team": ["Chisa", "Denia", "Aemeath"],
            "startup_steps": [],
            "loop_steps": [],
        }]
        editor.current_profile_index = 0
        editor.profile_name_edit = FakeLineEdit("测试轴")
        editor.profile_combo = FakeProfileCombo()
        editor.script_text = FakeScriptText("")
        editor.preview = FakePreview()
        editor.close_on_save = False
        editor._refresh_ui = lambda: None

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            editor.script_file = tmp_path / "custom_axis.txt"
            editor.profiles_file = tmp_path / "custom_axis_profiles.json"
            editor.image_file = tmp_path / "custom_axis.png"

            with patch("src.ui.CustomAxisEditor.QMessageBox.information") as information:
                editor._save_all_and_close()

            self.assertEqual(information.call_count, 1)
            self.assertTrue(editor.script_file.exists())
            self.assertTrue(editor.profiles_file.exists())
            self.assertEqual(len(editor.preview.saved_paths), 1)


class DummyTask:
    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return time.time() - start


class Verina:
    def __init__(self):
        self.index = 0
        self.char_name = "char_verina"
        self.char_type = CharType.HEALER
        self.buff_time = 20
        self.last_buff_time = time.time() - 3
        self.current_con = 1
        self.is_current_char = True

    def has_buff(self):
        return True

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return time.time() - start

    def get_current_con(self):
        return self.current_con

    def is_con_full(self):
        return self.current_con == 1

    def resonance_available(self):
        return True

    def liberation_available(self):
        return False

    def echo_available(self):
        return True

    def extra_action_available(self):
        return False

    def has_cd(self, box_name):
        return box_name == "liberation"

    def is_forte_full(self):
        return False


class HavocRover(Verina):
    pass


class ActionChar(Verina):
    def __init__(self):
        super().__init__()
        self.current_con = 0
        self.normal_attack_calls = []

    def continues_normal_attack(self, duration, interval=0.1, after_sleep=0, click_resonance_if_ready_and_return=False,
                                until_con_full=False):
        self.normal_attack_calls.append((duration, interval, until_con_full))
        if until_con_full:
            self.current_con = 1


class GlobalFActionChar(ActionChar):
    def __init__(self):
        super().__init__()
        self.f_break_calls = []

    def f_break(self, check_f_on_switch=True):
        self.f_break_calls.append(check_f_on_switch)


class ResonanceChar(Verina):
    def __init__(self):
        super().__init__()
        self.resonance_calls = []
        self.send_resonance_calls = 0
        self.record_resonance_calls = 0

    def click_resonance(self, **kwargs):
        self.resonance_calls.append(kwargs)
        return True, None, None

    def send_resonance_key(self):
        self.send_resonance_calls += 1

    def record_resonance_use(self):
        self.record_resonance_calls += 1


class StickyResonanceChar(Verina):
    def __init__(self):
        super().__init__()
        self.clicks = []
        self.resonance_calls = []

    def click_resonance(self, **kwargs):
        self.resonance_calls.append(kwargs)
        if kwargs.get("send_click", True):
            self.clicks.append("attack")
        return True, None, None


class CustomResonanceChar(Verina):
    def __init__(self):
        super().__init__()
        self.custom_available = True
        self.custom_resonance_calls = []
        self.standard_resonance_calls = []

    def resonance_available(self):
        return False

    def custom_axis_resonance_available(self):
        return self.custom_available

    def custom_axis_resonance(self, timeout=None):
        self.custom_resonance_calls.append(timeout)
        return self.custom_available

    def click_resonance(self, **kwargs):
        self.standard_resonance_calls.append(kwargs)
        return False, None, None


class CustomLiberationChar(Verina):
    def __init__(self):
        super().__init__()
        self.custom_liberation_calls = 0
        self.standard_liberation_calls = 0

    def liberation_available(self, check_color=True):
        return False

    def click_liberation(self, **kwargs):
        self.standard_liberation_calls += 1
        return False

    def custom_axis_liberation(self):
        self.custom_liberation_calls += 1
        return True


class EchoChar(Verina):
    def __init__(self):
        super().__init__()
        self.echo_calls = []

    def echo_available(self):
        return True

    def click_echo(self, **kwargs):
        self.echo_calls.append(kwargs)
        return True


class CustomAxisSanhua(Sanhua):
    def __init__(self):
        self.events = []
        self.task = self
        self.logger = self

    def info(self, *args, **kwargs):
        pass

    def mouse_down(self):
        self.events.append("mouse_down")

    def mouse_up(self):
        self.events.append("mouse_up")

    def wait_down(self, click=True):
        self.events.append(("wait_down", click))

    def sleep(self, value, *args, **kwargs):
        self.events.append(("sleep", value))

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return 0.2

    def liberation_available(self, check_color=True):
        return True

    def click_liberation(self, **kwargs):
        self.events.append(("liberation", kwargs))
        return True

    def resonance_available(self):
        return False


class CustomHeavyChar(Verina):
    def __init__(self):
        super().__init__()
        self.custom_heavy_calls = []
        self.heavy_calls = []

    def custom_axis_heavy_attack(self, duration=None):
        self.custom_heavy_calls.append(duration)

    def heavy_attack(self, duration=0.6):
        self.heavy_calls.append(duration)


class HeavyUntilConChar(Verina):
    def __init__(self):
        super().__init__()
        self.current_con = 0
        self.heavy_calls = []

    def heavy_attack(self, duration=0.6, until_con_full=False):
        self.heavy_calls.append((duration, until_con_full))
        if until_con_full:
            self.current_con = 1


class CustomHeavyUntilConditionChar(Verina):
    def __init__(self):
        super().__init__()
        self.custom_calls = []

    def custom_axis_heavy_until_condition(self, duration, condition_met):
        self.custom_calls.append((duration, condition_met()))
        return True


class DodgeChar(Verina):
    def __init__(self):
        super().__init__()
        self.dodge_calls = []

    def continues_right_click(self, duration, interval=0.1, direction_key=None):
        self.dodge_calls.append((duration, interval, direction_key))


class FBreakChar(Verina):
    def __init__(self):
        super().__init__()
        self.f_break_calls = []

    def f_break(self, check_f_on_switch=True):
        self.f_break_calls.append(check_f_on_switch)


class AxisSwitchChar(Verina):
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.switch_out_calls = []
        self.has_intro = False
        self.has_sub_dps_intro = False
        self.last_switch_in_time = -1
        self.last_outro_time = -1
        self.current_con = 0
        self.is_sub_dps = False

    def switch_out(self, con_full=False):
        self.switch_out_calls.append(con_full)


class RoleFlowChar(Verina):
    def __init__(self):
        super().__init__()
        self.role_flow_calls = []

    def custom_axis_role_flow(self):
        self.role_flow_calls.append("flow")
        return True


class NoRoleFlowChar(Verina):
    def __init__(self):
        super().__init__()
        self.perform_everything_calls = 0

    def perform_everything(self):
        self.perform_everything_calls += 1


class TestCustomAxisCondition(unittest.TestCase):

    def make_task(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task.config = {}
        task.chars = [Verina()]
        task.update_lib_portrait_icon = lambda: None
        task._get_aemeath_denia_chisa_axis_team = lambda: None
        task.log_error = lambda *args, **kwargs: None
        return task

    def test_axis_conditions_support_chinese_role_and_buff_aliases(self):
        task = self.make_task()
        self.assertTrue(task._axis_condition_met("维里奈.buff<=20"))
        self.assertTrue(task._axis_condition_met("维里奈.has_buff==1"))
        self.assertTrue(task._axis_condition_met("维里奈.buff_time>=20"))
        self.assertTrue(task._axis_condition_met("维里奈.con_full==1"))
        self.assertTrue(task._axis_condition_met("维里奈.协奏满==1"))
        self.assertTrue(task._axis_condition_met("维里奈.大招==0"))
        self.assertTrue(task._axis_condition_met("维里奈.技能==1 && 维里奈.声骸==1"))
        self.assertTrue(task._axis_condition_met("维里奈.e==1 && 维里奈.q==1"))
        self.assertTrue(task._axis_condition_met("维里奈.r==0"))

    def test_camellya_buff_condition_reads_crimson_bud_stacks(self):
        class Task(DummyTask):
            def find_one(self, *args, **kwargs):
                return None

        task = self.make_task()
        camellya = Camellya(Task(), 0)
        camellya.is_current_char = True
        camellya.get_forte = lambda budding=False: 0.74
        task.chars = [camellya]

        self.assertAlmostEqual(camellya.custom_axis_state_value("buff"), 2.6)
        self.assertTrue(task._axis_condition_met("椿.buff>2"))
        self.assertTrue(task._axis_condition_met("Camellya.层数>=2.5"))
        self.assertFalse(task._axis_condition_met("椿.buff>3"))

    def test_rover_form_aliases_match_havoc_rover_runtime_class(self):
        task = self.make_task()
        rover = HavocRover()
        task.chars = [rover]

        self.assertEqual(
            AutoCombatTask._normalize_team_keys(["AeroRover", "SpectroRover", "HavocRover"]),
            ["havocrover", "havocrover", "havocrover"],
        )
        self.assertIs(task._find_axis_char("风主"), rover)
        self.assertIs(task._find_axis_char("光主"), rover)
        self.assertIs(task._find_axis_char("AeroRover"), rover)
        self.assertIs(task._find_axis_char("SpectroRover"), rover)

    def test_douling_alias_supports_buling_and_legacy_name(self):
        self.assertEqual(AutoCombatTask._normalize_team_keys(["卜灵", "灯灯", "Douling"]),
                         ["douling", "douling", "douling"])


class TestAutoStartAxisFTask(unittest.TestCase):

    def make_task(self):
        task = AutoStartAxisFTask.__new__(AutoStartAxisFTask)
        task.scene = FakeScene()
        task.in_team_and_world = object()
        task.last_auto_start_axis_f_time = 0
        task.config = {'Axis Start Delay Seconds': 1.0}
        return task

    def test_auto_start_axis_f_detection_uses_f_icon_template_only(self):
        task = AutoStartAxisFTask.__new__(AutoStartAxisFTask)
        calls = []
        task.get_box_by_name = lambda name: FakeBox(name)

        def find_one(name, box=None, threshold=0):
            calls.append((name, getattr(box, "name", None), threshold))
            return object()

        task.find_one = find_one

        self.assertTrue(task._find_auto_start_axis_f())
        self.assertEqual(calls, [("pick_up_f_hcenter_vcenter", "search_dialog", 0.8)])

    def test_auto_start_axis_from_f_presses_f_once_when_task_enabled(self):
        task = self.make_task()
        task.in_combat = lambda: False
        task._find_auto_start_axis_f = lambda: object()
        combat_task = FakeCombatTask()
        sent_keys = []
        sleeps = []
        task.send_key = lambda key, **kwargs: sent_keys.append((key, kwargs))
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        task.get_task_by_class = lambda cls: combat_task

        self.assertTrue(task.run())

        self.assertEqual(sent_keys, [('f', {})])
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(combat_task.started, 1)

    def test_auto_start_axis_from_f_starts_axis_without_waiting_for_combat_detection(self):
        task = self.make_task()
        task.in_combat = lambda: self.fail('F task should not perform combat entry checks')
        task.wait_until = lambda *args, **kwargs: self.fail('F task should not wait for combat')
        task._find_auto_start_axis_f = lambda: object()
        task.send_key = lambda *args, **kwargs: None
        task.sleep = lambda *args, **kwargs: None
        task.get_task_by_class = lambda cls: FakeCombatTask()

        self.assertTrue(task.run())

    def test_auto_start_axis_from_f_skips_in_combat(self):
        task = self.make_task()
        task.scene = FakeScene(in_combat=True)
        task._find_auto_start_axis_f = lambda: self.fail('in-combat auto start should not scan F')

        self.assertFalse(task.run())

    def test_custom_axis_retry_task_is_only_a_switch(self):
        task = CustomAxisRetryTask.__new__(CustomAxisRetryTask)

        self.assertFalse(task.run())

    def test_custom_axis_global_f_task_is_only_a_switch(self):
        task = CustomAxisGlobalFTask.__new__(CustomAxisGlobalFTask)

        self.assertFalse(task.run())


class TestCustomAxisActionRetry(unittest.TestCase):

    def make_task(self):
        task = AutoCombatTask.__new__(AutoCombatTask)
        task.config = {'Auto Target': False}
        task.chars = [Verina()]
        task.update_lib_portrait_icon = lambda: None
        task._get_aemeath_denia_chisa_axis_team = lambda: None
        task.log_error = lambda *args, **kwargs: None
        return task

    def test_custom_axis_action_retries_every_005_until_success(self):
        task = self.make_task()
        task.get_task_by_class = lambda cls: FakeToggleTask(True)
        char = task.chars[0]
        results = iter([False, False, True])
        sleeps = []
        frames = []
        switch_calls = []
        task.in_combat = lambda: True
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        task.next_frame = lambda: frames.append('frame')
        task.log_info = lambda *args, **kwargs: None
        task._switch_to_axis_char = lambda target: switch_calls.append(target) or True
        task._execute_custom_axis_action = lambda target, action: next(results)

        self.assertTrue(task._execute_custom_axis_action_with_retry(char, "e"))

        self.assertEqual(sleeps, [CUSTOM_AXIS_ACTION_RETRY_INTERVAL, CUSTOM_AXIS_ACTION_RETRY_INTERVAL])
        self.assertEqual(frames, ['frame', 'frame'])
        self.assertEqual(switch_calls, [char, char])

    def test_custom_axis_global_f_checks_before_and_after_every_action(self):
        task = self.make_task()
        char = GlobalFActionChar()
        task.chars = [char]
        task._custom_axis_global_f_enabled = lambda: True
        task._switch_to_axis_char = lambda target: True
        task._custom_axis_should_stop_for_combat = lambda: False
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.next_frame = lambda *args, **kwargs: None
        task.info_set = lambda *args, **kwargs: None

        self.assertTrue(task._execute_custom_axis_line({
            'char': 'GlobalFActionChar',
            'actions': ['attack:0.1', 'attack:0.1'],
            'raw': 'GlobalFActionChar: attack:0.1, attack:0.1',
        }))

        self.assertEqual(char.f_break_calls, [False, False, False, False])

    def test_custom_axis_global_f_does_not_double_click_explicit_f_action(self):
        task = self.make_task()
        char = GlobalFActionChar()
        task.chars = [char]
        task._custom_axis_global_f_enabled = lambda: True
        task._switch_to_axis_char = lambda target: True
        task._custom_axis_should_stop_for_combat = lambda: False
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.next_frame = lambda *args, **kwargs: None
        task.info_set = lambda *args, **kwargs: None

        self.assertTrue(task._execute_custom_axis_line({
            'char': 'GlobalFActionChar',
            'actions': ['f', 'attack:0.1'],
            'raw': 'GlobalFActionChar: f, attack:0.1',
        }))

        self.assertEqual(char.f_break_calls, [False, False, False])

    def test_custom_axis_retry_until_success_retries_current_action_not_attack(self):
        task = self.make_task()
        task.get_task_by_class = lambda cls: FakeToggleTask(True)
        char = task.chars[0]
        actions = []
        task.in_combat = lambda: True
        task.sleep = lambda *args, **kwargs: None
        task.next_frame = lambda: None
        task.log_info = lambda *args, **kwargs: None
        task._switch_to_axis_char = lambda target: True

        def execute_action(target, action):
            actions.append(action)
            return len(actions) >= 3

        task._execute_custom_axis_action = execute_action

        self.assertTrue(task._execute_custom_axis_action_with_retry(char, "e"))

        self.assertEqual(actions, ["e", "e", "e"])

    def test_custom_axis_action_retry_until_success_is_off_by_default(self):
        task = self.make_task()
        task.config = {'Custom Axis Action Retry Count': 1}
        task.get_task_by_class = lambda cls: FakeToggleTask(False)
        char = task.chars[0]
        calls = []
        sleeps = []
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        task.log_info = lambda *args, **kwargs: None
        task._switch_to_axis_char = lambda target: True
        task._execute_custom_axis_action = lambda target, action: calls.append(action) or False

        self.assertFalse(task._execute_custom_axis_action_with_retry(char, "e"))

        self.assertEqual(calls, ["e", "e"])
        self.assertEqual(sleeps, [0.1])

    def test_custom_axis_force_start_runs_before_combat_and_stops_after_combat_end(self):
        task = self.make_task()
        task.scene = FakeScene()
        task.warm_up_char_features = lambda: None
        task._custom_axis_enabled = lambda: True
        task.load_chars = lambda: True
        task._custom_axis_maybe_target_enemy = lambda: None
        task.next_frame = lambda: None
        runs = []
        ended = []
        combat_checks = iter([False, True, False])
        task.in_combat = lambda: next(combat_checks)
        task.run_custom_axis_once = lambda: runs.append('axis') or True
        task.combat_end = lambda: ended.append('end')

        self.assertTrue(task.run_custom_axis_from_f_start())

        self.assertEqual(runs, ['axis', 'axis'])
        self.assertEqual(ended, ['end'])

    def test_custom_axis_target_enemy_is_throttled_to_half_second(self):
        task = self.make_task()
        task.config = {'Auto Target': True}
        calls = []
        task.target_enemy = lambda **kwargs: calls.append(kwargs)
        task.log_debug = lambda *args, **kwargs: None

        with patch("src.task.AutoCombatTask.time.time", side_effect=[100.0, 100.2, 100.6]):
            task._custom_axis_maybe_target_enemy()
            task._custom_axis_maybe_target_enemy()
            task._custom_axis_maybe_target_enemy()

        self.assertEqual(calls, [{'wait': False}, {'wait': False}])

    def test_attack_until_con_action_blocks_until_concerto_full(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = ActionChar()

        self.assertTrue(task._execute_custom_axis_action(char, "attack_until_con:4"))
        self.assertEqual(char.normal_attack_calls, [(4.0, 0.01, True)])
        self.assertEqual(char.current_con, 1)

    def test_custom_axis_attack_uses_one_centisecond_interval(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = ActionChar()

        self.assertTrue(task._execute_custom_axis_action(char, "attack:0.15"))

        self.assertEqual(char.normal_attack_calls, [(0.15, 0.01, False)])

    def test_custom_axis_attack_without_duration_defaults_to_short_combo(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = ActionChar()

        self.assertTrue(task._execute_custom_axis_action(char, "a"))

        self.assertEqual(char.normal_attack_calls, [(0.5, 0.01, False)])

    def test_timed_e_sends_resonance_then_waits_once(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        calls = []
        task.sleep = lambda value, *args, **kwargs: calls.append(('sleep', value))
        char = ResonanceChar()
        char.send_resonance_key = lambda: calls.append(('send_e', None))

        self.assertTrue(task._execute_custom_axis_action(char, "e:1.25"))

        self.assertEqual(char.resonance_calls, [])
        self.assertEqual(char.record_resonance_calls, 1)
        self.assertEqual(calls, [('send_e', None), ('sleep', 1.25)])

    def test_e_wait_without_duration_uses_short_forced_wait(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        calls = []
        task.sleep = lambda value, *args, **kwargs: calls.append(('sleep', value))
        char = ResonanceChar()
        char.send_resonance_key = lambda: calls.append(('send_e', None))

        self.assertTrue(task._execute_custom_axis_action(char, "e_wait"))

        self.assertEqual(char.resonance_calls, [])
        self.assertEqual(calls, [('send_e', None), ('sleep', 0.05)])

    def test_plain_e_keeps_old_no_wait_behavior(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        sleeps = []
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        char = ResonanceChar()

        self.assertTrue(task._execute_custom_axis_action(char, "e"))

        self.assertEqual(char.resonance_calls, [{"time_out": 1.2, "send_click": False}])
        self.assertEqual(sleeps, [])

    def test_custom_axis_e_does_not_inject_normal_attack(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = StickyResonanceChar()

        self.assertTrue(task._execute_custom_axis_action(char, "e"))

        self.assertEqual(char.resonance_calls, [{"time_out": 1.2, "send_click": False}])
        self.assertEqual(char.clicks, [])

    def test_custom_axis_resonance_uses_character_specific_available_and_release(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = CustomResonanceChar()
        task.chars = [char]

        self.assertTrue(task._axis_condition_met("1.技能==1"))
        self.assertTrue(task._execute_custom_axis_action(char, "e"))
        self.assertEqual(char.custom_resonance_calls, [1.2])
        self.assertEqual(char.standard_resonance_calls, [])

    def test_custom_axis_e_anim_uses_animation_aware_resonance(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = ResonanceChar()

        self.assertTrue(task._execute_custom_axis_action(char, "e_anim"))

        self.assertEqual(char.resonance_calls, [{
            "has_animation": True,
            "send_click": False,
            "animation_min_duration": 0,
            "time_out": 1.2,
        }])

    def test_custom_axis_e_anim_duration_waits_after_release(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        sleeps = []
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        char = ResonanceChar()

        self.assertTrue(task._execute_custom_axis_action(char, "e_anim:0.25"))

        self.assertEqual(sleeps, [0.25])

    def test_custom_axis_liberation_uses_character_specific_release(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = CustomLiberationChar()

        self.assertTrue(task._execute_custom_axis_action(char, "r"))
        self.assertEqual(char.custom_liberation_calls, 1)
        self.assertEqual(char.standard_liberation_calls, 0)

    def test_custom_axis_echo_without_duration_continues_immediately(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        sleeps = []
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        char = EchoChar()

        self.assertTrue(task._execute_custom_axis_action(char, "q"))

        self.assertEqual(char.echo_calls, [{"time_out": 0}])
        self.assertEqual(sleeps, [])

    def test_custom_axis_echo_duration_waits_after_release(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        sleeps = []
        task.sleep = lambda value, *args, **kwargs: sleeps.append(value)
        char = EchoChar()

        self.assertTrue(task._execute_custom_axis_action(char, "q:0.2"))

        self.assertEqual(char.echo_calls, [{"time_out": 0}])
        self.assertEqual(sleeps, [0.2])

    def test_custom_axis_sanhua_liberation_preinputs_heavy(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = CustomAxisSanhua()

        self.assertTrue(task._execute_custom_axis_action(char, "r"))

        self.assertLess(char.events.index("mouse_down"), char.events.index(("liberation", {"send_click": False})))
        self.assertLess(char.events.index(("liberation", {"send_click": False})), char.events.index("mouse_up"))

    def test_custom_axis_heavy_prefers_character_specific_preinput(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = CustomHeavyChar()

        self.assertTrue(task._execute_custom_axis_action(char, "heavy:0.85"))
        self.assertEqual(char.custom_heavy_calls, [0.85])
        self.assertEqual(char.heavy_calls, [])

    def test_custom_axis_heavy_until_con_holds_until_concerto_full(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = HeavyUntilConChar()

        self.assertTrue(task._execute_custom_axis_action(char, "heavy_until_con:2.75"))
        self.assertEqual(char.heavy_calls, [(2.75, True)])
        self.assertEqual(char.current_con, 1)

    def test_custom_axis_heavy_until_condition_checks_current_step_condition(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.sleep = lambda *args, **kwargs: None
        mouse_events = []
        task.mouse_down = lambda: mouse_events.append("down")
        task.mouse_up = lambda: mouse_events.append("up")
        char = HeavyUntilConChar()
        task._axis_condition_met = lambda condition: char.current_con == 1
        task.next_frame = lambda: setattr(char, "current_con", 1)

        self.assertTrue(task._execute_custom_axis_heavy_until_condition(
            char,
            "heavy_until_condition:2.75",
            "千咲.协奏满==1",
        ))
        self.assertEqual(mouse_events, ["down", "up"])
        self.assertEqual(char.current_con, 1)

    def test_custom_axis_attack_until_condition_stops_when_condition_met(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        fake_time = [100.0]
        clicks = []
        frames = []
        condition_checks = []
        task.click = lambda *args, **kwargs: clicks.append(fake_time[0])

        def sleep(value, *args, **kwargs):
            fake_time[0] += value

        def next_frame():
            frames.append(fake_time[0])
            if len(frames) == 2:
                task.condition_ready = True

        task.sleep = sleep
        task.next_frame = next_frame
        task.condition_ready = False

        def condition_met(condition):
            condition_checks.append((condition, task.condition_ready))
            return task.condition_ready

        task._axis_condition_met = condition_met

        with patch("src.task.AutoCombatTask.time.time", side_effect=lambda: fake_time[0]):
            self.assertTrue(task._execute_custom_axis_attack_until_condition(
                ActionChar(),
                "attack_until_condition:60",
                "椿.buff>6",
            ))

        self.assertEqual(len(clicks), 2)
        self.assertLess(fake_time[0] - 100.0, 0.05)
        self.assertEqual(condition_checks[-1], ("椿.buff>6", True))

    def test_custom_axis_fallback_attack_interrupts_when_condition_becomes_met(self):
        task = self.make_task()
        char = GlobalFActionChar()
        task.chars = [char]
        task._switch_to_axis_char = lambda target: True
        task._custom_axis_global_f_enabled = lambda: False
        task._custom_axis_should_stop_for_combat = lambda: False
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.info_set = lambda *args, **kwargs: None
        fake_time = [100.0]
        clicks = []
        frames = []
        task.click = lambda *args, **kwargs: clicks.append(fake_time[0])
        task.sleep = lambda value, *args, **kwargs: fake_time.__setitem__(0, fake_time[0] + value)

        def next_frame():
            frames.append(fake_time[0])
            if len(frames) == 2:
                task.condition_ready = True

        task.next_frame = next_frame
        task.condition_ready = False
        task._axis_condition_met = lambda condition: task.condition_ready

        with patch("src.task.AutoCombatTask.time.time", side_effect=lambda: fake_time[0]):
            self.assertTrue(task._execute_custom_axis_line({
                'char': 'GlobalFActionChar',
                'actions': ['attack:60'],
                'condition': '椿.buff>6',
                'condition_failed_fallback': True,
                'raw': 'Sanhua: e, attack:0.3 | 条件 椿.buff>6 | 未满足 Camellya: attack:60',
            }))

        self.assertEqual(len(clicks), 2)
        self.assertLess(fake_time[0] - 100.0, 0.05)

    def test_custom_axis_heavy_until_condition_uses_character_specific_release(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task._axis_condition_met = lambda condition: True
        char = CustomHeavyUntilConditionChar()

        self.assertTrue(task._execute_custom_axis_heavy_until_condition(
            char,
            "heavy_until_condition:1.25",
            "爱弥斯.技能==1",
        ))
        self.assertEqual(char.custom_calls, [(1.25, True)])

    def test_custom_axis_dodge_uses_right_click_duration(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = DodgeChar()

        self.assertTrue(task._execute_custom_axis_action(char, "dodge:0.10"))
        self.assertEqual(char.dodge_calls, [(0.1, 0.1, None)])

    def test_custom_axis_f_once_ignores_switch_only_guard(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = FBreakChar()
        char.check_f_on_switch = False

        self.assertTrue(task._execute_custom_axis_action(char, "f"))
        self.assertEqual(char.f_break_calls, [False])

    def test_custom_axis_switch_sends_no_normal_attack_click(self):
        task = self.make_task()
        current = AxisSwitchChar(0)
        target = AxisSwitchChar(1)
        task.chars = [current, target]
        task.in_liberation = False
        task.update_lib_portrait_icon = lambda: None
        task.log_info = lambda *args, **kwargs: None
        task.log_debug = lambda *args, **kwargs: None
        task.info_set = lambda *args, **kwargs: None
        task.add_freeze_duration = lambda *args, **kwargs: None
        task.sleep = lambda *args, **kwargs: None
        task.next_frame = lambda *args, **kwargs: None
        sent_keys = []
        clicks = []
        task.send_key = lambda key: sent_keys.append(key)
        task.click = lambda *args, **kwargs: clicks.append('click')
        task.in_team = lambda: (True, target.index if sent_keys else current.index, 2)

        self.assertTrue(task._switch_to_axis_char(target))

        self.assertEqual(sent_keys, [target.index + 1])
        self.assertEqual(clicks, [])
        self.assertEqual(current.switch_out_calls, [False])

    def test_custom_axis_same_char_step_preserves_intro_context(self):
        task = self.make_task()
        char = AxisSwitchChar(0)
        char.has_intro = True
        task.chars = [char]
        task.in_liberation = True
        task.update_lib_portrait_icon = lambda: None
        task.log_info = lambda *args, **kwargs: None
        task.in_team = lambda: (True, char.index, 2)

        self.assertTrue(task._switch_to_axis_char(char))

        self.assertTrue(char.has_intro)
        self.assertTrue(char.is_current_char)
        self.assertFalse(task.in_liberation)
        self.assertEqual(char.switch_out_calls, [])

    def test_custom_axis_role_flow_uses_character_specific_flow(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        char = RoleFlowChar()

        self.assertTrue(task._execute_custom_axis_action(char, "role_flow:12.5"))
        self.assertEqual(char.role_flow_calls, ["flow"])

        self.assertTrue(task._execute_custom_axis_action(char, "角色流程"))
        self.assertEqual(char.role_flow_calls, ["flow", "flow"])

    def test_custom_axis_role_flow_without_character_specific_flow_skips(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.log_debug = lambda *args, **kwargs: None
        char = NoRoleFlowChar()

        self.assertTrue(task._execute_custom_axis_action(char, "role_flow"))
        self.assertEqual(char.perform_everything_calls, 0)

    def test_custom_axis_f_until_checks_during_current_action(self):
        task = self.make_task()
        task._custom_axis_after_action_ok = lambda *args, **kwargs: True
        task.next_frame = lambda *args, **kwargs: None
        task.in_combat = lambda: True
        task._find_axis_char = lambda char_name: char
        task._switch_to_axis_char = lambda target: True
        task.log_debug = lambda *args, **kwargs: None
        task.info_set = lambda *args, **kwargs: None
        task.sleep = lambda *args, **kwargs: None
        char = FBreakChar()

        self.assertTrue(task._execute_custom_axis_line({
            'char': 'Verina',
            'actions': ['f_until:0.12', 'wait:0.01', 'wait:0.01'],
            'condition': '',
            'fallback_actions': [],
            'fallback_char': '',
            'raw': 'Verina: f_until:0.12, wait:0.01, wait:0.01',
        }))

        self.assertGreaterEqual(len(char.f_break_calls), 2)
        self.assertTrue(all(call is False for call in char.f_break_calls))

    def test_unmet_condition_fallback_keeps_axis_cursor_on_same_step(self):
        task = self.make_task()
        task._axis_condition_met = lambda condition: False
        task.custom_axis_cursor = 0
        task.custom_axis_loop_cursor = 0
        axis_lines = [{
            'char': 'Chisa',
            'actions': ['e'],
            'condition': '千咲.技能==1',
            'fallback_actions': ['attack_until_con:4'],
            'fallback_char': 'Chisa',
            'raw': 'Chisa: e | 条件 千咲.技能==1 | 未满足 Chisa: attack_until_con:4',
        }]

        axis_line = task._next_custom_axis_line(axis_lines, 'custom_axis_loop_cursor', loop=True)
        self.assertEqual(axis_line['char'], 'Chisa')
        self.assertEqual(axis_line['actions'], ['attack_until_con:4'])
        self.assertTrue(axis_line['condition_failed_fallback'])
        self.assertEqual(task.custom_axis_loop_cursor, 0)

    def test_custom_axis_without_matching_condition_does_not_fall_back_to_normal_perform(self):
        task = self.make_task()
        task.custom_axis_startup_done = True
        task.custom_axis_loop_cursor = 0
        task._custom_axis_sections = lambda: {
            'startup': [],
            'loop': [{
                'char': 'Aemeath',
                'actions': ['e'],
                'condition': '爱弥斯.技能==0',
                'fallback_actions': [],
                'fallback_char': '',
                'raw': 'Aemeath: e | 条件 爱弥斯.技能==0',
            }],
        }
        task._axis_condition_met = lambda condition: False
        task.log_debug = lambda *args, **kwargs: None
        frames = []
        task.next_frame = lambda: frames.append('frame')

        self.assertTrue(task.run_custom_axis_once())
        self.assertEqual(frames, ['frame'])
        self.assertEqual(task.custom_axis_loop_cursor, 0)

    def test_custom_axis_after_startup_without_loop_does_not_fall_back_to_normal_perform(self):
        task = self.make_task()
        task.custom_axis_startup_done = True
        task._custom_axis_sections = lambda: {'startup': [], 'loop': []}
        task.log_error = lambda *args, **kwargs: None
        self.assertFalse(task.run_custom_axis_once())

        task._custom_axis_sections = lambda: {'startup': [{'char': 'Aemeath', 'actions': ['r'], 'condition': ''}], 'loop': []}
        task.log_debug = lambda *args, **kwargs: None
        frames = []
        task.next_frame = lambda: frames.append('frame')

        self.assertTrue(task.run_custom_axis_once())
        self.assertEqual(frames, ['frame'])

    def test_script_fallback_role_is_parsed_as_axis_char(self):
        task = self.make_task()
        parsed = task._parse_custom_axis_line("Chisa: e | 条件 千咲.技能==1 | 未满足 Denia: attack_until_con:4")
        self.assertEqual(parsed['fallback_char'], 'Denia')
        self.assertEqual(parsed['fallback_actions'], ['attack_until_con:4'])

        old_style = task._parse_custom_axis_line("Chisa: e | 条件 千咲.技能==1 | 未满足 attack_until_con:4")
        self.assertEqual(old_style['fallback_char'], '')
        self.assertEqual(old_style['fallback_actions'], ['attack_until_con:4'])


if __name__ == "__main__":
    unittest.main()
