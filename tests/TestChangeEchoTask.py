import unittest
from unittest.mock import Mock

from src.task.ChangeEchoTask import ChangeEchoTask


class TestChangeEchoTask(unittest.TestCase):

    def test_control_click_moves_mouse_before_pressing(self):
        task = ChangeEchoTask.__new__(ChangeEchoTask)
        task.click = Mock()
        boxes = [object()]

        task.click_with_mouse_move(boxes, after_sleep=0.8)

        task.click.assert_called_once_with(
            boxes, -1, move=True, name=None, after_sleep=0.8
        )

    def test_relative_control_click_keeps_coordinates_and_log_name(self):
        task = ChangeEchoTask.__new__(ChangeEchoTask)
        task.click = Mock()

        task.click_with_mouse_move(
            0.04, 0.41, name='数据重构入口', after_sleep=0.8
        )

        task.click.assert_called_once_with(
            0.04,
            0.41,
            move=True,
            name='数据重构入口',
            after_sleep=0.8,
        )


if __name__ == '__main__':
    unittest.main()
