import unittest
from types import SimpleNamespace

from src.echo_score import calculate_echo_score, template_names


class TestEchoScore(unittest.TestCase):
    def test_all_local_wuwa_stat_echo_templates_are_available(self):
        self.assertIn("通用", template_names())
        self.assertIn("清霄", template_names())
        self.assertGreaterEqual(len(template_names()), 28)

    def test_current_and_potential_scores_follow_wuwa_stat_echo_formula(self):
        main_rows = [SimpleNamespace(), SimpleNamespace()]
        sub_rows = [SimpleNamespace(stat_name="暴击", value=10.5)]

        score = calculate_echo_score("通用", 1, "1C", main_rows, sub_rows)

        self.assertEqual((4.76, 0.0), score.row_scores[:2])
        self.assertAlmostEqual(13.125, score.row_scores[2])
        self.assertEqual(17.89, score.current_score)
        self.assertGreater(score.potential_score, score.current_score)


if __name__ == "__main__":
    unittest.main()
