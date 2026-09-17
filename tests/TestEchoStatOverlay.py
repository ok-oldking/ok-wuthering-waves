import unittest
from types import SimpleNamespace

from src.gui.EchoStatOverlay import find_echo_stat_rectangles


def box(x, y, width, height, name):
    return SimpleNamespace(x=x, y=y, width=width, height=height, name=name)


class TestEchoStatOverlay(unittest.TestCase):
    def test_main_and_substats_receive_requested_colours(self):
        boxes = [
            box(1250, 420, 70, 28, "声骸技能"),
            box(1257, 192, 68, 28, "生命"), box(1477, 195, 66, 23, "22.8%"),
            box(1257, 222, 68, 29, "生命"), box(1482, 224, 55, 25, "2280"),
            box(1278, 255, 45, 25, "生命"), box(1490, 257, 47, 22, "510"),
            box(1278, 285, 49, 24, "生命"), box(1480, 285, 57, 24, "8.6%"),
            box(1278, 311, 82, 28, "暴击伤害"), box(1472, 311, 66, 30, "13.8%"),
            box(1278, 339, 47, 32, "防御"), box(1470, 342, 68, 29, "10.9%"),
            box(1280, 372, 113, 23, "普攻伤害加成"), box(1470, 371, 67, 28, "10.9%"),
        ]

        rectangles = find_echo_stat_rectangles(boxes, 1600, 900)

        self.assertEqual(7, len(rectangles))
        self.assertEqual([(255, 0, 0), (255, 0, 0)], [item.color for item in rectangles[:2]])
        self.assertEqual([(255, 255, 255)] * 5, [item.color for item in rectangles[2:]])
        self.assertEqual((1252, 189, 296, 34),
                         (rectangles[0].x, rectangles[0].y, rectangles[0].width, rectangles[0].height))

    def test_tuning_layout_uses_left_stat_panel(self):
        rectangles = find_echo_stat_rectangles([
            box(48, 42, 120, 30, "声骸强化"),
            box(177, 212, 76, 30, "生命"), box(478, 213, 70, 29, "22.8%"),
            box(177, 248, 76, 28, "生命"), box(490, 250, 58, 24, "2280"),
            box(205, 285, 87, 28, "共鸣效率"), box(475, 285, 72, 28, "10.8%"),
            box(205, 319, 163, 28, "共鸣解放伤害加成"), box(475, 319, 72, 30, "10.1%"),
            box(205, 356, 48, 29, "暴击"), box(481, 352, 66, 34, "9.9%"),
            box(205, 388, 85, 34, "暴击伤害"), box(472, 390, 75, 30, "13.8%"),
            box(205, 427, 125, 28, "重击伤害加成"), box(481, 423, 66, 34, "9.4%"),
        ], 1600, 900)

        self.assertEqual((172, 209, 381, 36),
                         (rectangles[0].x, rectangles[0].y, rectangles[0].width, rectangles[0].height))
        self.assertEqual((200, 282, 352, 34),
                         (rectangles[2].x, rectangles[2].y, rectangles[2].width, rectangles[2].height))
        self.assertEqual([(255, 0, 0), (255, 0, 0)], [item.color for item in rectangles[:2]])
        self.assertEqual([(255, 255, 255)] * 5, [item.color for item in rectangles[2:]])

    def test_other_screens_do_not_draw_stat_boxes(self):
        self.assertEqual([], find_echo_stat_rectangles([box(10, 10, 70, 28, "背包")], 1600, 900))

    def test_resonator_attribute_details_are_ignored(self):
        boxes = [box(48, 44, 120, 28, "属性详情")]
        boxes += self._left_summary_rows()

        self.assertEqual([], find_echo_stat_rectangles(boxes, 1600, 900))

    def test_initial_echo_summary_is_ignored(self):
        boxes = [box(50, 45, 60, 28, "声骸"), box(170, 365, 90, 28, "声骸技能")]
        boxes += self._left_summary_rows()

        self.assertEqual([], find_echo_stat_rectangles(boxes, 1600, 900))

    @staticmethod
    def _left_summary_rows():
        names = ["生命", "攻击", "防御", "共鸣效率", "暴击", "暴击伤害"]
        values = ["22005", "1089", "4110", "274.2%", "19.4%", "213.6%"]
        boxes = []
        for index, (name, value) in enumerate(zip(names, values)):
            y = 285 + index * 35
            boxes.extend((box(177, y, 100, 28, name), box(400, y, 70, 28, value)))
        return boxes
