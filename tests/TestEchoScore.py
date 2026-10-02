import unittest
from types import SimpleNamespace

from src.echo_score import (
    DEFAULT_TEMPLATE,
    calculate_echo_score,
    matching_template_names,
    resolve_template_name,
    substat_tier_label,
    template_names,
    auto_match_template,
)


def row(name, value):
    return SimpleNamespace(stat_name=name, value=value)


class TestEchoScore(unittest.TestCase):
    def test_auto_match_requires_equipped_marker(self):
        boxes = [SimpleNamespace(name="洛瑟菈")]

        self.assertIsNone(auto_match_template(boxes))

    def test_auto_match_uses_last_variant_for_character(self):
        boxes = [SimpleNamespace(name="洛瑟菈装配中")]

        self.assertEqual("洛瑟菈-声骸-羽落", auto_match_template(boxes))

    def test_auto_match_does_not_let_generic_role_text_override_character(self):
        boxes = [
            SimpleNamespace(name="角色为敌人添加负面效果"),
            SimpleNamespace(name="达妮娅"),
            SimpleNamespace(name="装配中"),
        ]

        self.assertEqual("达妮娅-通用", auto_match_template(boxes))

    def test_traditional_equipped_marker_matches_character(self):
        boxes = [SimpleNamespace(name="莫寧裝配中")]

        self.assertEqual("莫宁-通用", auto_match_template(boxes))

    def test_all_xwuid_character_and_modal_templates_are_available(self):
        names = template_names()

        self.assertEqual(68, len(names))
        self.assertEqual(68, len(set(names)))
        self.assertIn("洛瑟菈-霜渐", names)
        self.assertIn("洛瑟菈-霜渐-羽落", names)
        self.assertIn("洛瑟菈-声骸", names)
        self.assertIn("洛瑟菈-声骸-羽落", names)
        self.assertIn("心-通用", names)
        self.assertIn("锁暝-通用", names)

    def test_new_character_weights_and_auto_match(self):
        from src.xwuid_echo_data import TEMPLATES

        self.assertEqual(0.74, TEMPLATES["1311"]["default"]["skill_weight"][2])
        self.assertEqual(0.7, TEMPLATES["1312"]["default"]["skill_weight"][0])
        self.assertEqual(1.2, TEMPLATES["1312"]["default"]["sub_props"]["攻击%"])
        self.assertIn("心-通用", matching_template_names("心-通用"))
        self.assertEqual(["锁暝-通用"], matching_template_names("锁暝"))
        self.assertEqual("心-通用", auto_match_template([SimpleNamespace(name="心装配中")]))
        self.assertEqual("锁暝-通用", auto_match_template([SimpleNamespace(name="锁暝装配中")]))
        self.assertEqual("鉴心-通用", auto_match_template([SimpleNamespace(name="鉴心装配中")]))

    def test_readme_reference_echo_scores_49_96(self):
        main_rows = [row("暴击", 22), row("攻击", 150)]
        sub_rows = [
            row("暴击", 10.5),
            row("暴击伤害", 21),
            row("攻击%", 11.6),
            row("重击伤害加成", 11.6),
            row("攻击", 60),
        ]

        score = calculate_echo_score("嘉贝莉娜-通用", 4, "4C", main_rows, sub_rows)

        self.assertEqual((6.84, 2.33, 13.06, 13.06, 7.93, 3.01, 3.73), score.row_scores)
        self.assertEqual(49.96, score.current_score)
        self.assertEqual(49.96, score.potential_score)

    def test_potential_keeps_existing_rolls_and_fills_best_missing_substats(self):
        main_rows = [row("暴击", 22), row("攻击", 150)]
        sub_rows = [row("暴击", 6.3)]

        score = calculate_echo_score("嘉贝莉娜-通用", 4, "4C", main_rows, sub_rows)

        self.assertLess(score.current_score, score.potential_score)
        self.assertNotEqual(50.0, score.potential_score)
        # Existing low crit roll stays unchanged; four distinct best max rolls fill the gaps.
        self.assertEqual(44.73, score.potential_score)

    def test_unleveled_main_stats_use_level_25_values_in_both_scores(self):
        main_rows = [row("暴击", 4.4), row("攻击", 30)]

        score = calculate_echo_score("嘉贝莉娜-通用", 4, "4C", main_rows, [])

        # +25 values are Crit 22% and flat ATK 150, not the observed level-0 values.
        self.assertEqual((6.84, 2.33), score.row_scores)
        self.assertEqual(9.17, score.current_score)
        self.assertEqual(49.96, score.potential_score)

    def test_search_and_legacy_name_migration(self):
        self.assertEqual(4, len(matching_template_names("洛瑟菈")))
        self.assertEqual("爱弥斯-通用", resolve_template_name("爱弥斯"))
        self.assertEqual(DEFAULT_TEMPLATE, resolve_template_name("通用"))

    def test_substat_tier_labels_support_eight_and_four_roll_tables(self):
        self.assertEqual("1档", substat_tier_label("暴击", 6.3))
        self.assertEqual("8档", substat_tier_label("暴击", 10.5))
        self.assertEqual("2档", substat_tier_label("暴击伤害", 13.79))
        self.assertEqual("1档", substat_tier_label("攻击", 30))
        self.assertEqual("4档", substat_tier_label("防御", 70))
        self.assertEqual("", substat_tier_label("未知词条", 10))


if __name__ == "__main__":
    unittest.main()
