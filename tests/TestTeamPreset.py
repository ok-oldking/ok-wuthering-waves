import json
import tempfile
import unittest
from pathlib import Path

from src.team_preset.TeamPresetStore import (
    TeamPreset, TeamPresetSlot, TeamPresetStore,
)
from src.team_preset.TeamLogicLoader import load_team_logic, clear_team_logic_cache


class TestTeamPresetStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        TeamPresetStore.override_folder = self.base
        TeamPresetStore.set_forced("")

    def tearDown(self):
        TeamPresetStore.override_folder = None
        self.tmp.cleanup()

    def _add_preset(self, name="test", slots=None):
        preset = TeamPreset(id=TeamPresetStore.generate_id(name), name=name, slots=slots or [])
        TeamPresetStore.add_preset(preset)
        return preset

    def test_add_and_get(self):
        preset = self._add_preset("alpha")
        loaded = TeamPresetStore.get_preset(preset.id)
        self.assertEqual(loaded.name, "alpha")
        self.assertEqual([p.name for p in TeamPresetStore.list_presets()], ["alpha"])

    def test_add_duplicate_id_raises(self):
        preset = self._add_preset("alpha")
        with self.assertRaises(ValueError):
            TeamPresetStore.add_preset(TeamPreset(id=preset.id, name="beta"))

    def test_save_updates_existing(self):
        preset = self._add_preset("alpha")
        preset.note = "共鸣效率 120%"
        preset.slots = [TeamPresetSlot(char="Iuno", note="C6", params={"Iuno C6": True})]
        TeamPresetStore.save_preset(preset)
        loaded = TeamPresetStore.get_preset(preset.id)
        self.assertEqual(loaded.note, "共鸣效率 120%")
        self.assertEqual(loaded.slots[0].params, {"Iuno C6": True})

    def test_delete_removes_preset_and_code(self):
        preset = self._add_preset("alpha")
        TeamPresetStore.save_custom_code(preset.id, "Iuno", "class Iuno:\n    pass\n")
        self.assertTrue(TeamPresetStore.has_custom_code(preset.id, "Iuno"))
        TeamPresetStore.delete_preset(preset.id)
        self.assertIsNone(TeamPresetStore.get_preset(preset.id))
        self.assertFalse(TeamPresetStore.has_custom_code(preset.id, "Iuno"))

    def test_generate_id_avoids_collision(self):
        self._add_preset("alpha")
        self._add_preset("alpha")
        ids = TeamPresetStore.list_preset_ids()
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(ids & {"alpha", "alpha_2"}), 2)

    def test_merged_char_config(self):
        preset = TeamPreset(
            id="t", name="t",
            slots=[
                TeamPresetSlot(char="Iuno", enabled=True, params={"Iuno C6": True}),
                TeamPresetSlot(char="Chisa", enabled=True, params={"Chisa DPS": False}),
                TeamPresetSlot(char="A", enabled=False, params={"ignored": True}),
            ],
        )
        self.assertEqual(preset.merged_char_config(),
                         {"Iuno C6": True, "Chisa DPS": False})

    def test_custom_code_roundtrip(self):
        preset = self._add_preset("alpha")
        code = "class Iuno:\n    pass\n"
        TeamPresetStore.save_custom_code(preset.id, "Iuno", code)
        self.assertTrue(TeamPresetStore.has_custom_code(preset.id, "Iuno"))
        self.assertEqual(TeamPresetStore.read_custom_code(preset.id, "Iuno"), code)
        TeamPresetStore.remove_custom_code(preset.id, "Iuno")
        self.assertFalse(TeamPresetStore.has_custom_code(preset.id, "Iuno"))

    def test_save_custom_code_rejects_invalid(self):
        preset = self._add_preset("alpha")
        with self.assertRaises(SyntaxError):
            TeamPresetStore.save_custom_code(preset.id, "Iuno", "def broken(")
        self.assertFalse(TeamPresetStore.has_custom_code(preset.id, "Iuno"))

    def test_duplicate_copies_code(self):
        preset = self._add_preset("alpha")
        TeamPresetStore.save_custom_code(preset.id, "Iuno", "class Iuno:\n    pass\n")
        dup = TeamPresetStore.duplicate_preset(preset.id)
        self.assertNotEqual(dup.id, preset.id)
        self.assertTrue(TeamPresetStore.has_custom_code(dup.id, "Iuno"))
        self.assertEqual(TeamPresetStore.read_custom_code(dup.id, "Iuno"),
                         TeamPresetStore.read_custom_code(preset.id, "Iuno"))

    def test_export_import_roundtrip(self):
        preset = self._add_preset("alpha")
        preset.slots = [TeamPresetSlot(char="Iuno", note="n", params={"Iuno C6": True})]
        TeamPresetStore.save_preset(preset)
        TeamPresetStore.save_custom_code(preset.id, "Iuno", "class Iuno:\n    pass\n")

        data = TeamPresetStore.export_preset(preset.id)
        self.assertEqual(data["type"], "ok_ww_team_preset")
        TeamPresetStore.delete_preset(preset.id)

        imported = TeamPresetStore.import_preset(data)
        self.assertEqual(imported.name, "alpha")
        self.assertEqual(imported.slots[0].params, {"Iuno C6": True})
        self.assertTrue(TeamPresetStore.has_custom_code(imported.id, "Iuno"))

    def test_import_reassigns_id_on_conflict(self):
        self._add_preset("alpha")
        data = {
            "type": "ok_ww_team_preset",
            "version": 1,
            "preset": TeamPreset(id="alpha", name="alpha").to_dict(),
            "custom_code": {},
        }
        imported = TeamPresetStore.import_preset(data)
        self.assertNotEqual(imported.id, "alpha")

    def test_import_accepts_bare_preset(self):
        data = TeamPreset(id="bare", name="bare").to_dict()
        imported = TeamPresetStore.import_preset(data)
        self.assertEqual(imported.id, "bare")

    def test_forced_preset(self):
        preset = self._add_preset("alpha")
        self.assertIsNone(TeamPresetStore.get_forced_preset())
        TeamPresetStore.set_forced(preset.id)
        self.assertEqual(TeamPresetStore.get_forced_name(), preset.id)
        self.assertEqual(TeamPresetStore.get_forced_preset().id, preset.id)
        TeamPresetStore.delete_preset(preset.id)
        self.assertEqual(TeamPresetStore.get_forced_name(), "")

    def test_resolve_forced_override(self):
        a = self._add_preset("a", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        self._add_preset("b", slots=[TeamPresetSlot(char="Chisa", enabled=True)])
        TeamPresetStore.set_forced(a.id)
        resolved = TeamPresetStore.resolve_preset_for_team(["Chisa"])
        self.assertEqual(resolved.id, a.id)

    def test_resolve_forced_skipped_when_disabled(self):
        a = self._add_preset("a", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        TeamPresetStore.set_forced(a.id)
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(["Chisa"], use_forced=False))

    def test_resolve_priority_order(self):
        first = self._add_preset("first", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        second = self._add_preset("second", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Chisa"])
        self.assertEqual(resolved.id, first.id)
        TeamPresetStore.move_preset(second.id, -1)
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Chisa"])
        self.assertEqual(resolved.id, second.id)

    def test_resolve_excludes_auto_match_off(self):
        preset = self._add_preset("x", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        preset.auto_match = False
        TeamPresetStore.save_preset(preset)
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(["Iuno"]))

    def test_resolve_subset_and_disabled_slots(self):
        preset = self._add_preset("x", slots=[
            TeamPresetSlot(char="Iuno", enabled=True),
            TeamPresetSlot(char="Chisa", enabled=False),
        ])
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Galbrena"])
        self.assertEqual(resolved.id, preset.id)
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(["Chisa"]))
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team([]))

    def test_resolve_empty_team_no_match(self):
        self._add_preset("x", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team([]))
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(None))

    def test_auto_match_field_roundtrip(self):
        preset = self._add_preset("x")
        preset.auto_match = False
        TeamPresetStore.save_preset(preset)
        self.assertFalse(TeamPresetStore.get_preset(preset.id).auto_match)
        self.assertTrue(TeamPresetStore.get_preset("missing") is None)

    def test_last_auto_match(self):
        preset = self._add_preset("x")
        self.assertIsNone(TeamPresetStore.get_last_auto_match())
        TeamPresetStore.record_auto_match(preset.id)
        self.assertEqual(TeamPresetStore.get_last_auto_match().id, preset.id)
        TeamPresetStore.record_auto_match("")
        self.assertIsNone(TeamPresetStore.get_last_auto_match())
        TeamPresetStore.delete_preset(preset.id)
        self.assertIsNone(TeamPresetStore.get_last_auto_match())

    def test_detected_team_roundtrip(self):
        self.assertEqual(TeamPresetStore.get_last_detected_team(), [])
        TeamPresetStore.record_detected_team(["Iuno", "Lucilla"])
        self.assertEqual(TeamPresetStore.get_last_detected_team(), ["Iuno", "Lucilla"])
        TeamPresetStore.record_detected_team([])
        self.assertEqual(TeamPresetStore.get_last_detected_team(), [])

    def test_team_code_roundtrip(self):
        preset = self._add_preset("logic")
        self.assertFalse(TeamPresetStore.has_team_code(preset.id))
        self.assertIsNone(TeamPresetStore.read_team_code(preset.id))
        code = "class MyLogic(BaseTeamCombat):\n    def perform(self):\n        pass\n"
        TeamPresetStore.save_team_code(preset.id, code)
        self.assertTrue(TeamPresetStore.has_team_code(preset.id))
        self.assertEqual(TeamPresetStore.read_team_code(preset.id), code)
        TeamPresetStore.remove_team_code(preset.id)
        self.assertFalse(TeamPresetStore.has_team_code(preset.id))
        self.assertIsNone(TeamPresetStore.read_team_code(preset.id))

    def test_team_code_invalid_rejected(self):
        preset = self._add_preset("badlogic")
        with self.assertRaises(SyntaxError):
            TeamPresetStore.save_team_code(preset.id, "def broken(:\n")
        self.assertFalse(TeamPresetStore.has_team_code(preset.id))

    def test_team_code_copy_and_export_import(self):
        preset = self._add_preset("share")
        code = "class MyLogic(BaseTeamCombat):\n    def perform(self):\n        pass\n"
        TeamPresetStore.save_team_code(preset.id, code)
        dup = TeamPresetStore.duplicate_preset(preset.id)
        self.assertTrue(TeamPresetStore.has_team_code(dup.id))
        data = TeamPresetStore.export_preset(preset.id)
        self.assertEqual(data["custom_code"].get("team_code.py"), code)
        TeamPresetStore.delete_preset(dup.id)
        imported = TeamPresetStore.import_preset(data)
        self.assertTrue(TeamPresetStore.has_team_code(imported.id))
        self.assertEqual(TeamPresetStore.read_team_code(imported.id), code)

    def test_team_logic_loader_valid(self):
        preset = self._add_preset("loader")
        TeamPresetStore.save_team_code(preset.id,
                                       "class MyLogic(BaseTeamCombat):\n"
                                       "    def perform(self):\n"
                                       "        self.task._hits += 1\n")
        cls = load_team_logic(preset.id)
        self.assertIsNotNone(cls)
        self.assertTrue(issubclass(cls, __import__(
            "src.team_preset.BaseTeamCombat", fromlist=["BaseTeamCombat"]).BaseTeamCombat))
        logic = cls(task=None, chars=[None, None, None])
        self.assertIsNotNone(logic.perform)

    def test_team_logic_loader_invalid_fallback(self):
        preset = self._add_preset("brokenlogic")
        TeamPresetStore.save_team_code(preset.id, "x = 1\n")
        self.assertIsNone(load_team_logic(preset.id))
        TeamPresetStore.save_team_code(preset.id, "raise RuntimeError('boom')\n")
        self.assertIsNone(load_team_logic(preset.id))
        self.assertIsNone(load_team_logic("no_such_preset"))

    def test_team_logic_loader_cache_invalidation(self):
        preset = self._add_preset("cachelogic")
        TeamPresetStore.save_team_code(preset.id,
                                       "class A(BaseTeamCombat):\n    def perform(self):\n        pass\n")
        first = load_team_logic(preset.id)
        self.assertIsNotNone(first)
        TeamPresetStore.save_team_code(preset.id,
                                       "class B(BaseTeamCombat):\n    def perform(self):\n        pass\n")
        second = load_team_logic(preset.id)
        self.assertIsNotNone(second)
        self.assertIsNot(first, second)
        clear_team_logic_cache(preset.id)

    def test_move_preset_bounds(self):
        a = self._add_preset("a")
        b = self._add_preset("b")
        self.assertFalse(TeamPresetStore.move_preset(a.id, -1))
        self.assertFalse(TeamPresetStore.move_preset(b.id, 1))
        self.assertTrue(TeamPresetStore.move_preset(b.id, -1))
        self.assertEqual([p.name for p in TeamPresetStore.list_presets()], ["b", "a"])

    def test_char_names_to_classes(self):
        self.assertEqual(TeamPresetStore.char_names_to_classes(["char_iuno"]), ["Iuno"])
        self.assertEqual(TeamPresetStore.char_names_to_classes(["char_iuno", "unknown"]),
                         ["Iuno"])
        self.assertEqual(TeamPresetStore.char_names_to_classes([]), [])

    def test_resolve_after_char_name_mapping(self):
        preset = self._add_preset("x", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        classes = TeamPresetStore.char_names_to_classes(["char_iuno", "char_chisa"])
        self.assertEqual(TeamPresetStore.resolve_preset_for_team(classes).id, preset.id)

    def test_index_saved_to_disk(self):
        preset = self._add_preset("alpha")
        index_path = self.base / "team_presets" / "index.json"
        self.assertTrue(index_path.exists())
        data = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(data["presets"][0]["id"], preset.id)

    def test_team_logic_error_roundtrip(self):
        preset = self._add_preset("err")
        TeamPresetStore.set_forced(preset.id)
        self.assertIsNone(TeamPresetStore.get_last_team_logic_error())
        TeamPresetStore.record_team_logic_error(preset.id, "boom")
        error = TeamPresetStore.get_last_team_logic_error()
        self.assertIsNotNone(error)
        self.assertEqual(error["message"], "boom")
        TeamPresetStore.record_team_logic_error(preset.id, None)
        self.assertIsNone(TeamPresetStore.get_last_team_logic_error())

    def test_export_invalid_team_code_warns_but_continues(self):
        preset = self._add_preset("badcode")
        path = TeamPresetStore.get_team_code_path(preset.id)
        path.write_text("def broken(:\n", encoding="utf-8")
        data = TeamPresetStore.export_preset(preset.id)
        self.assertIsNotNone(data["team_code_error"])
        self.assertEqual(data["custom_code"]["team_code.py"], "def broken(:\n")
        imported = TeamPresetStore.import_preset(data)
        self.assertTrue(TeamPresetStore.has_team_code(imported.id))

    def test_description_roundtrip(self):
        preset = self._add_preset("desc")
        preset.description = "奶妈+副C+主C,通用轮换"
        TeamPresetStore.save_preset(preset)
        loaded = TeamPresetStore.get_preset(preset.id)
        self.assertEqual(loaded.description, "奶妈+副C+主C,通用轮换")
        data = TeamPresetStore.export_preset(preset.id)
        self.assertEqual(data["description"], "奶妈+副C+主C,通用轮换")
        imported = TeamPresetStore.import_preset(data)
        self.assertEqual(imported.description, "奶妈+副C+主C,通用轮换")

    def test_builtin_templates_scan_and_install(self):
        templates = TeamPresetStore.list_builtin_templates()
        names = [t["name"] for t in templates]
        self.assertIn("Quick Start", names)
        template = next(t for t in templates if t["name"] == "Quick Start")
        self.assertTrue(template["description"])
        preset = TeamPresetStore.install_builtin_template(template["folder"])
        self.assertIsNotNone(TeamPresetStore.get_preset(preset.id))
        self.assertTrue(TeamPresetStore.has_team_code(preset.id))
        self.assertEqual(preset.description, template["description"])
        from src.team_preset.TeamLogicLoader import load_team_logic
        self.assertIsNotNone(load_team_logic(preset.id))

    def test_slot_required_roundtrip(self):
        preset = self._add_preset("req")
        preset.slots = [TeamPresetSlot(char="Iuno", enabled=True, required=True)]
        TeamPresetStore.save_preset(preset)
        loaded = TeamPresetStore.get_preset(preset.id)
        self.assertTrue(loaded.slots[0].required)
        data = TeamPresetStore.export_preset(preset.id)
        self.assertTrue(data["preset"]["slots"][0]["required"])
        imported = TeamPresetStore.import_preset(data)
        self.assertTrue(imported.slots[0].required)

    def test_required_slot_blocks_auto_match(self):
        preset = self._add_preset("x", slots=[
            TeamPresetSlot(char="Iuno", enabled=True, required=True),
            TeamPresetSlot(char="Chisa", enabled=True),
        ])
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(["Chisa", "Galbrena"]))
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Chisa"])
        self.assertEqual(resolved.id, preset.id)
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno"])
        self.assertEqual(resolved.id, preset.id)

    def test_required_slot_does_not_block_forced(self):
        preset = self._add_preset("x", slots=[
            TeamPresetSlot(char="Iuno", enabled=True, required=True)])
        TeamPresetStore.set_forced(preset.id)
        resolved = TeamPresetStore.resolve_preset_for_team(["Chisa"])
        self.assertEqual(resolved.id, preset.id)

    def test_resolve_best_score_wins(self):
        low = self._add_preset("low", slots=[
            TeamPresetSlot(char="Iuno", enabled=True),
            TeamPresetSlot(char="Chisa", enabled=True),
        ])
        high = self._add_preset("high", slots=[
            TeamPresetSlot(char="Iuno", enabled=True),
            TeamPresetSlot(char="Verina", enabled=True),
        ])
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Verina", "Galbrena"])
        self.assertEqual(resolved.id, high.id)
        self.assertNotEqual(resolved.id, low.id)

    def test_resolve_full_match_preferred(self):
        exact = self._add_preset("exact", slots=[
            TeamPresetSlot(char="Iuno", enabled=True),
            TeamPresetSlot(char="Chisa", enabled=True),
            TeamPresetSlot(char="Verina", enabled=True),
        ])
        partial = self._add_preset("partial", slots=[
            TeamPresetSlot(char="Iuno", enabled=True),
            TeamPresetSlot(char="Chisa", enabled=True),
        ])
        resolved = TeamPresetStore.resolve_preset_for_team(["Iuno", "Chisa", "Verina"])
        self.assertEqual(resolved.id, exact.id)
        self.assertNotEqual(resolved.id, partial.id)

    def test_match_attempts_recorded(self):
        self._add_preset("a", slots=[TeamPresetSlot(char="Iuno", enabled=True)])
        TeamPresetStore.resolve_preset_for_team(["Iuno"])
        attempts = TeamPresetStore.get_last_match_attempts()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["score"], 1.0)
        self.assertEqual(attempts[0]["hits"], ["Iuno"])

    def test_match_attempts_recorded_on_fail(self):
        self._add_preset("a", slots=[
            TeamPresetSlot(char="Iuno", enabled=True, required=True)])
        TeamPresetStore.resolve_preset_for_team(["Chisa"])
        attempts = TeamPresetStore.get_last_match_attempts()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["score"], 0.0)
        self.assertEqual(attempts[0]["missing_required"], ["Iuno"])

    def test_meta_file_written_on_add_and_save(self):
        preset = self._add_preset("meta")
        meta = self.base / "team_presets" / preset.id / "preset.json"
        self.assertTrue(meta.exists())
        data = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "meta")
        preset.name = "renamed"
        TeamPresetStore.save_preset(preset)
        data = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "renamed")

    def test_rebuild_index_recovers_presets(self):
        a = self._add_preset("alpha")
        b = self._add_preset("beta")
        index_path = self.base / "team_presets" / "index.json"
        index_path.unlink()
        index = TeamPresetStore.rebuild_index()
        self.assertEqual(len(index["presets"]), 2)
        ids = {p["id"] for p in index["presets"]}
        self.assertEqual(ids, {a.id, b.id})
        self.assertEqual([p.name for p in TeamPresetStore.list_presets()],
                         ["alpha", "beta"])

    def test_load_index_recovers_broken_json(self):
        self._add_preset("alpha")
        index_path = self.base / "team_presets" / "index.json"
        index_path.write_text("not valid json {{{", encoding="utf-8")
        loaded = TeamPresetStore.get_preset("alpha")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "alpha")

    def test_rebuild_index_preserves_forced(self):
        preset = self._add_preset("alpha")
        TeamPresetStore.set_forced(preset.id)
        TeamPresetStore.rebuild_index()
        self.assertEqual(TeamPresetStore.get_forced_name(), preset.id)


class _FakeChar:
    def __init__(self, index, char_name="Fake"):
        self.index = index
        self.char_name = char_name
        self.is_current_char = False
        self.perform_calls = 0
        self.switch_out_calls = 0
        self.last_switch_in_time = 0
        self._liberation_available = False

    def perform(self):
        self.perform_calls += 1

    def switch_out(self, con_full=False):
        self.switch_out_calls += 1

    def liberation_available(self):
        return True


class TestTeamLogicDriving(unittest.TestCase):
    """BaseCombatTask._perform_current 的三级优先级驱动测试。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        TeamPresetStore.override_folder = self.base
        TeamPresetStore.set_forced("")
        self.preset = TeamPreset(id=TeamPresetStore.generate_id("driving"), name="driving")
        TeamPresetStore.add_preset(self.preset)
        TeamPresetStore.set_forced(self.preset.id)
        self.char_a = _FakeChar(0, "A")
        self.char_b = _FakeChar(1, "B")
        self.char_a.is_current_char = True
        from src.task.BaseCombatTask import BaseCombatTask
        self.task = object.__new__(BaseCombatTask)
        self.task.chars = [self.char_a, self.char_b]
        self.task.active_team_logic = None
        self.task.active_preset = self.preset
        self.task.info = {}

    def tearDown(self):
        TeamPresetStore.override_folder = None
        self.tmp.cleanup()

    def _load_logic(self, code):
        TeamPresetStore.save_team_code(self.preset.id, code)
        cls = load_team_logic(self.preset.id)
        self.assertIsNotNone(cls)
        return cls(self.task, self.task.chars)

    def test_team_logic_takes_precedence(self):
        logic = self._load_logic(
            "class L(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        self.task._logic_calls = getattr(self.task, '_logic_calls', 0) + 1\n")
        self.task.active_team_logic = logic
        self.task._perform_current()
        self.assertEqual(self.task._logic_calls, 1)
        self.assertEqual(self.char_a.perform_calls, 0)

    def test_team_logic_error_falls_back_and_records(self):
        logic = self._load_logic(
            "class L(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        raise RuntimeError('boom')\n")
        self.task.active_team_logic = logic
        self.task._perform_current()
        self.assertEqual(self.char_a.perform_calls, 1)
        self.assertIsNone(self.task.active_team_logic)
        error = TeamPresetStore.get_last_team_logic_error()
        self.assertIsNotNone(error)
        self.assertIn("boom", error["message"])

    def test_team_logic_not_in_combat_propagates(self):
        logic = self._load_logic(
            "class L(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        from src.task.BaseCombatTask import NotInCombatException\n"
            "        raise NotInCombatException('out')\n")
        self.task.active_team_logic = logic
        from src.task.BaseCombatTask import NotInCombatException
        with self.assertRaises(NotInCombatException):
            self.task._perform_current()
        self.assertIsNone(TeamPresetStore.get_last_team_logic_error())
        self.assertEqual(self.char_a.perform_calls, 0)

    def test_no_team_logic_uses_char(self):
        self.task._perform_current()
        self.assertEqual(self.char_a.perform_calls, 1)


class _FakeSwitchTask:
    def __init__(self, chars, current_index):
        self.chars = chars
        self.current_index = current_index
        self.pressed = []
        self.next_frames = 0

    def check_combat(self):
        pass

    def in_team(self):
        return True, self.current_index, len(self.chars)

    def raise_not_in_combat(self, msg):
        raise RuntimeError(msg)

    def send_key(self, key, after_sleep=0):
        self.pressed.append(key)

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1,
              move=False, down_time=0.01, after_sleep=0, **kwargs):
        self.current_index = 1 if self.current_index == 0 else 0

    def sleep(self, sec):
        pass

    def next_frame(self):
        self.next_frames += 1

    def log_error(self, msg):
        self.last_error = msg


class TestTeamLogicSwitch(unittest.TestCase):

    def test_switch_to_changes_current_char(self):
        a = _FakeChar(0, "A")
        b = _FakeChar(1, "B")
        a.is_current_char = True
        task = _FakeSwitchTask([a, b], 0)
        from src.team_preset.BaseTeamCombat import BaseTeamCombat
        logic = BaseTeamCombat(task, [a, b])
        self.assertTrue(logic.switch_to(1))
        self.assertTrue(b.is_current_char)
        self.assertFalse(a.is_current_char)
        self.assertEqual(a.switch_out_calls, 1)
        self.assertGreater(b.last_switch_in_time, 0)
        self.assertIn(2, task.pressed)
        self.assertGreater(task.next_frames, 0)

    def test_switch_to_same_char_is_noop(self):
        a = _FakeChar(0, "A")
        a.is_current_char = True
        task = _FakeSwitchTask([a], 0)
        from src.team_preset.BaseTeamCombat import BaseTeamCombat
        logic = BaseTeamCombat(task, [a])
        self.assertTrue(logic.switch_to(0))
        self.assertEqual(a.switch_out_calls, 0)

    def test_switch_to_missing_slot_returns_false(self):
        a = _FakeChar(0, "A")
        a.is_current_char = True
        task = _FakeSwitchTask([a], 0)
        from src.team_preset.BaseTeamCombat import BaseTeamCombat
        logic = BaseTeamCombat(task, [a])
        self.assertFalse(logic.switch_to(2))


class TestTeamLogicPrimitives(unittest.TestCase):

    def test_char_is_and_current_index(self):
        a = _FakeChar(0, "Verina")
        b = _FakeChar(1, "Iuno")
        a.is_current_char = True
        task = _FakeSwitchTask([a, b], 0)
        from src.team_preset.BaseTeamCombat import BaseTeamCombat
        logic = BaseTeamCombat(task, [a, b])
        self.assertTrue(logic.char_is(0, "Verina"))
        self.assertFalse(logic.char_is(0, "Iuno"))
        self.assertFalse(logic.char_is(2, "Verina"))
        self.assertEqual(logic.current_index, 0)
        b.is_current_char = True
        a.is_current_char = False
        self.assertEqual(logic.current_index, 1)

    def test_log_helpers_fallback_to_logger(self):
        task = _FakeSwitchTask([], 0)
        from src.team_preset.BaseTeamCombat import BaseTeamCombat
        logic = BaseTeamCombat(task, [])
        logic.log_info("hi")
        logic.log_debug("hi")
        logic.log_error("hi")


class _FakeCombatTask:
    def __init__(self, chars):
        self.chars = chars
        self.active_preset = None
        self.char_config = None
        self.global_config = {"Global": True}
        self.logs = []

    def log_info(self, msg):
        self.logs.append(msg)

    def get_global_config(self, name):
        return self.global_config


class TestTeamPresetSwitching(unittest.TestCase):
    """BaseCombatTask._apply_preset_match 的三态切换测试:
    全局配置 → 自动匹配预设 → 换预设 → 回退全局,以及强制预设覆盖。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        TeamPresetStore.override_folder = self.base
        TeamPresetStore.set_forced("")
        from src.task.BaseCombatTask import BaseCombatTask
        self.task = object.__new__(BaseCombatTask)
        self.task.chars = [_FakeChar(0, "char_iuno"), _FakeChar(1, "char_chisa")]
        self.task.active_preset = None
        self.task.char_config = None
        self.task.global_config = {"Global": True}
        self.task.logs = []
        self.task.log_info = self.task.logs.append
        self.task.get_global_config = lambda name: self.task.global_config

    def tearDown(self):
        TeamPresetStore.override_folder = None
        self.tmp.cleanup()

    def _preset(self, name, char, required=False):
        preset = TeamPreset(id=TeamPresetStore.generate_id(name), name=name,
                            slots=[TeamPresetSlot(char=char, enabled=True,
                                                  params={f"{char} C6": True},
                                                  required=required)])
        TeamPresetStore.add_preset(preset)
        return preset

    def test_global_to_auto_match(self):
        preset = self._preset("p", "Iuno")
        self.assertTrue(self.task._apply_preset_match())
        self.assertEqual(self.task.active_preset.id, preset.id)
        self.assertEqual(self.task.char_config, {"Iuno C6": True})
        self.assertEqual(TeamPresetStore.get_last_auto_match().id, preset.id)

    def test_auto_to_different_preset(self):
        first = self._preset("first", "Iuno")
        second = self._preset("second", "Chisa")
        self.task.chars = [_FakeChar(0, "char_chisa")]
        self.task.active_preset = first
        self.assertTrue(self.task._apply_preset_match())
        self.assertEqual(self.task.active_preset.id, second.id)

    def test_auto_to_global_fallback(self):
        self._preset("p", "Iuno")
        self.task.chars = [_FakeChar(0, "char_verina")]
        preset = TeamPresetStore.get_preset(TeamPresetStore.list_preset_ids().pop())
        self.task.active_preset = preset
        self.task.char_config = {"old": True}
        self.assertTrue(self.task._apply_preset_match())
        self.assertIsNone(self.task.active_preset)
        self.assertEqual(self.task.char_config, self.task.global_config)
        self.assertIsNone(TeamPresetStore.get_last_auto_match())
        self.assertTrue(any("fell back" in log for log in self.task.logs))

    def test_forced_preset_overrides_auto(self):
        forced = self._preset("forced", "Iuno", required=True)
        self._preset("auto", "Chisa")
        TeamPresetStore.set_forced(forced.id)
        self.assertTrue(self.task._apply_preset_match())
        self.assertEqual(self.task.active_preset.id, forced.id)

    def test_no_detected_chars_noop(self):
        self.task.chars = []
        self.assertFalse(self.task._apply_preset_match())
        self.assertIsNone(self.task.active_preset)


class _FakeBaseChar:
    MARKER = "base"


class TestCustomCodePriority(unittest.TestCase):
    """全局自定义代码 vs 预设自定义代码的加载优先级:
    预设自定义 > 全局自定义(启用时)> 内置。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        TeamPresetStore.override_folder = self.base
        from ok.util.config import Config
        self._old_config_folder = Config.config_folder
        Config.config_folder = str(self.base)
        from src.char.CustomCharLoader import clear_custom_char_cache
        clear_custom_char_cache()
        self.preset = TeamPreset(id=TeamPresetStore.generate_id("code"), name="code")
        TeamPresetStore.add_preset(self.preset)

    def tearDown(self):
        from ok.util.config import Config
        Config.config_folder = self._old_config_folder
        from src.char.CustomCharLoader import clear_custom_char_cache
        clear_custom_char_cache()
        TeamPresetStore.override_folder = None
        self.tmp.cleanup()

    def _code(self, marker):
        return (f"from src.char.BaseChar import BaseChar\n"
                f"class _FakeBaseChar(BaseChar):\n"
                f"    MARKER = '{marker}'\n")

    def test_preset_code_beats_global(self):
        from src.char.CustomCharLoader import (
            load_custom_char_class_with_preset, save_custom_char_code,
        )
        TeamPresetStore.save_custom_code(self.preset.id, "_FakeBaseChar",
                                         self._code("preset"))
        save_custom_char_code(_FakeBaseChar, self._code("global"), use_custom=True)
        cls = load_custom_char_class_with_preset(_FakeBaseChar, self.preset.id)
        self.assertEqual(cls.MARKER, "preset")

    def test_global_custom_when_no_preset_code(self):
        from src.char.CustomCharLoader import (
            load_custom_char_class_with_preset, save_custom_char_code,
        )
        save_custom_char_code(_FakeBaseChar, self._code("global"), use_custom=True)
        cls = load_custom_char_class_with_preset(_FakeBaseChar, self.preset.id)
        self.assertEqual(cls.MARKER, "global")

    def test_builtin_when_global_disabled(self):
        from src.char.CustomCharLoader import (
            load_custom_char_class_with_preset, save_custom_char_code,
        )
        save_custom_char_code(_FakeBaseChar, self._code("global"), use_custom=False)
        cls = load_custom_char_class_with_preset(_FakeBaseChar, self.preset.id)
        self.assertIs(cls, _FakeBaseChar)

    def test_builtin_without_any_custom(self):
        from src.char.CustomCharLoader import load_custom_char_class_with_preset
        cls = load_custom_char_class_with_preset(_FakeBaseChar, self.preset.id)
        self.assertIs(cls, _FakeBaseChar)

    def test_preset_code_fallback_to_global_on_error(self):
        from src.char.CustomCharLoader import (
            load_custom_char_class_with_preset, save_custom_char_code,
        )
        save_custom_char_code(_FakeBaseChar, self._code("global"), use_custom=True)
        TeamPresetStore.save_custom_code(
            self.preset.id, "_FakeBaseChar",
            "class _FakeBaseChar:\n"      # 不继承 BaseChar → 加载失败
            "    MARKER = 'broken'\n")
        cls = load_custom_char_class_with_preset(_FakeBaseChar, self.preset.id)
        self.assertEqual(cls.MARKER, "global")


class TestTeamPresetEnhancements(unittest.TestCase):
    """新功能:强制作用域 / 仅全匹配 / 同分偏好 / 统计 / 批量导入导出 / 检测填槽 / 试运行。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        TeamPresetStore.override_folder = self.base
        TeamPresetStore.set_forced("")
        TeamPresetStore.set_force_scope("persist")
        TeamPresetStore.set_only_full_match(False)

    def tearDown(self):
        TeamPresetStore.override_folder = None
        self.tmp.cleanup()

    def _add(self, preset_id, auto_match=True, chars=()):
        preset = TeamPreset(
            id=preset_id, name=preset_id, auto_match=auto_match,
            slots=[TeamPresetSlot(char=c) for c in chars])
        TeamPresetStore.add_preset(preset)
        return preset

    def test_force_scope_once_clears_after_use(self):
        self._add("main", chars=("Iuno",))
        TeamPresetStore.set_forced("main")
        TeamPresetStore.set_force_scope("once")
        matched = TeamPresetStore.resolve_preset_for_team(["Iuno"])
        self.assertEqual(matched.id, "main")
        self.assertEqual(TeamPresetStore.get_forced_name(), "")

    def test_force_scope_until_match_overrides(self):
        self._add("main", chars=("Iuno", "Rover"))
        self._add("alt", chars=("Iuno", "Verina"))
        TeamPresetStore.set_forced("main")
        TeamPresetStore.set_force_scope("until_match")
        matched = TeamPresetStore.resolve_preset_for_team(["Iuno", "Verina"])
        self.assertEqual(matched.id, "alt")
        self.assertEqual(TeamPresetStore.get_forced_name(), "")

    def test_force_scope_until_match_keeps_same(self):
        self._add("main", chars=("Iuno", "Verina"))
        TeamPresetStore.set_forced("main")
        TeamPresetStore.set_force_scope("until_match")
        matched = TeamPresetStore.resolve_preset_for_team(["Iuno", "Verina"])
        self.assertEqual(matched.id, "main")
        self.assertEqual(TeamPresetStore.get_forced_name(), "main")

    def test_only_full_match_blocks_subset(self):
        self._add("main", chars=("Iuno", "Verina"))
        TeamPresetStore.set_only_full_match(True)
        self.assertIsNone(TeamPresetStore.resolve_preset_for_team(["Iuno"]))
        TeamPresetStore.set_only_full_match(False)
        self.assertEqual(
            TeamPresetStore.resolve_preset_for_team(["Iuno"]).id, "main")

    def test_tie_prefers_last_auto_match(self):
        self._add("first", chars=("Iuno", "Verina"))
        self._add("second", chars=("Iuno", "Verina"))
        TeamPresetStore.record_auto_match("second")
        matched = TeamPresetStore.resolve_preset_for_team(["Iuno", "Verina"])
        self.assertEqual(matched.id, "second")

    def test_stats_recorded(self):
        TeamPresetStore.record_preset_use("main")
        TeamPresetStore.record_preset_use("main")
        TeamPresetStore.record_preset_error("main")
        stats = TeamPresetStore.get_preset_stats("main")
        self.assertEqual(stats.get("uses"), 2)
        self.assertEqual(stats.get("errors"), 1)
        self.assertTrue(stats.get("last_used"))

    def test_create_from_detected_team(self):
        TeamPresetStore.record_detected_team(["Iuno", "Verina"])
        preset = TeamPresetStore.create_from_detected_team("My Team")
        self.assertEqual([s.char for s in preset.slots], ["Iuno", "Verina"])
        self.assertEqual(preset.created_from, "Detected Team")

    def test_batch_export_import_roundtrip(self):
        self._add("one", chars=("Iuno",))
        self._add("two", chars=("Verina",))
        out = self.base / "batch.json"
        TeamPresetStore.export_presets_to_file(["one", "two"], out)
        TeamPresetStore.delete_preset("one")
        TeamPresetStore.delete_preset("two")
        imported, warnings = TeamPresetStore.import_presets_from_file(out)
        self.assertEqual(len(imported), 2)
        self.assertEqual(warnings, [])

    def test_unknown_char_warning_on_import(self):
        preset = TeamPreset(id="x", name="x",
                            slots=[TeamPresetSlot(char="NotAChar")])
        TeamPresetStore.add_preset(preset)
        out = self.base / "single.json"
        TeamPresetStore.export_presets_to_file(["x"], out)
        TeamPresetStore.delete_preset("x")
        imported, warnings = TeamPresetStore.import_presets_from_file(out)
        self.assertEqual(len(imported), 1)
        self.assertEqual(warnings[0]["unknown_chars"], ["NotAChar"])

    def test_get_preset_error_none_when_missing(self):
        self.assertIsNone(TeamPresetStore.get_preset_error("nope"))

    def test_team_logic_test_run(self):
        from src.team_preset.TeamLogicLoader import test_run_team_logic
        preset = self._add("logic")
        TeamPresetStore.save_team_code(
            preset.id,
            "class TestLogic(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        self.click(self.current_char.index)\n"
            "        self.next_frame()\n")
        ok, _ = test_run_team_logic(preset.id, frames=30)
        self.assertTrue(ok)

    def test_team_logic_test_run_reports_error(self):
        from src.team_preset.TeamLogicLoader import test_run_team_logic
        preset = self._add("logic")
        TeamPresetStore.save_team_code(
            preset.id,
            "class TestLogic(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        raise ValueError('boom')\n")
        ok, message = test_run_team_logic(preset.id, frames=30)
        self.assertFalse(ok)
        self.assertIn("ValueError", message)

    def test_tags_roundtrip(self):
        preset = self._add("main", chars=("Iuno",))
        preset.tags = ["深渊", "大世界"]
        TeamPresetStore.save_preset(preset)
        out = self.base / "tagged.json"
        TeamPresetStore.export_preset_to_file(preset.id, out)
        TeamPresetStore.delete_preset(preset.id)
        imported = TeamPresetStore.import_preset_from_file(out)
        self.assertEqual(imported.tags, ["深渊", "大世界"])

    def test_combat_result_stats(self):
        TeamPresetStore.record_preset_combat_result("main", success=True)
        TeamPresetStore.record_preset_combat_result("main", success=True)
        TeamPresetStore.record_preset_combat_result("main", success=False)
        stats = TeamPresetStore.get_preset_stats("main")
        self.assertEqual(stats.get("successes"), 2)
        self.assertEqual(stats.get("fails"), 1)

    def test_backup_restore_zip(self):
        self._add("one", chars=("Iuno",))
        self._add("two", chars=("Verina",))
        backup = self.base / "backup.zip"
        TeamPresetStore.backup_presets_to_zip(["one", "two"], backup)
        self.assertTrue(backup.exists())
        TeamPresetStore.delete_preset("one")
        TeamPresetStore.delete_preset("two")
        imported, warnings = TeamPresetStore.restore_presets_from_zip(backup)
        self.assertEqual(len(imported), 2)
        self.assertEqual(warnings, [])
        self.assertIsNotNone(TeamPresetStore.get_preset("one"))
        self.assertIsNotNone(TeamPresetStore.get_preset("two"))

    def test_export_template_folder(self):
        preset = self._add("tpl", chars=("Iuno",))
        preset.description = "示例模板"
        TeamPresetStore.save_preset(preset)
        TeamPresetStore.save_team_code(
            preset.id,
            "class TplLogic(BaseTeamCombat):\n"
            "    def perform(self):\n"
            "        pass\n")
        folder = self.base / "template"
        data = TeamPresetStore.export_preset_as_template_folder(preset.id, folder)
        self.assertTrue((folder / "preset.json").is_file())
        self.assertTrue((folder / "team_code.py").is_file())
        self.assertEqual(data["preset"]["tags"], [])
        self.assertEqual(data["name"], "tpl")


if __name__ == "__main__":
    unittest.main()
