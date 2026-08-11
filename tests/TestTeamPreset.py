import json
import tempfile
import unittest
from pathlib import Path

from src.team_preset.TeamPresetStore import (
    TeamPreset, TeamPresetSlot, TeamPresetStore,
)


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


if __name__ == "__main__":
    unittest.main()
