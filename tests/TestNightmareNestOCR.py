import unittest
import re
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.NightmareNestTask import NightmareNestTask

class TestNightmareNestOCR(TaskTestCase):
    task_class = NightmareNestTask
    config = config
    config['debug'] = True

    def test_nest_ocr_1(self):
        self.set_image('tests/images/nightmare_nest_1.png')
        text_boxes = self.task.ocr(0.43, 0.13, 0.58, 0.94, frame_processor=self.task.ocr_preprocess)
        processed_boxes = self.task._process_ocr_results(text_boxes, 0.43, 0.13)
        found = [b.name for b in processed_boxes if re.search(self.task.count_re, b.name)]
        self.assertEqual(len(found), 4)

    def test_nest_ocr_2(self):
        self.set_image('tests/images/nightmare_nest_2.png')
        text_boxes = self.task.ocr(0.43, 0.13, 0.58, 0.94, frame_processor=self.task.ocr_preprocess)
        processed_boxes = self.task._process_ocr_results(text_boxes, 0.43, 0.13)
        found = [b.name for b in processed_boxes if re.search(self.task.count_re, b.name)]
        self.assertEqual(len(found), 3)

if __name__ == '__main__':
    unittest.main()
