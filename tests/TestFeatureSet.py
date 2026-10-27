import unittest

import cv2
import numpy as np

from ok.feature.Box import Box
from ok.feature.Feature import Feature
from ok.feature.FeatureSet import FeatureSet


class TestFeatureSet(unittest.TestCase):
    def test_suisui_hud_templates_follow_ultrawide_anchors(self):
        from config import config

        matching = dict(config['template_matching'])
        cases = (
            ('ok_templates/23.png', 'suisui_forte2', 947, False),
            ('ok_templates/23.png', 'suisui_forte3', 1036, False),
            ('ok_templates/39.png', 'suisui_e1', 3211, True),
        )
        for image_path, name, source_x, right_anchored in cases:
            source = cv2.imread(image_path)
            self.assertIsNotNone(source)
            source_height, source_width = source.shape[:2]
            feature_set = FeatureSet(False, None, **matching)
            for width, height in ((1920, 1080), (2560, 1080), (3440, 1440), (5120, 2160)):
                with self.subTest(feature=name, resolution=(width, height)):
                    scale = height / source_height
                    scaled = cv2.resize(source, (round(source_width * scale), height))
                    scaled_width = scaled.shape[1]
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    center_x = (width - scaled_width) // 2
                    frame[:, center_x:center_x + scaled_width] = scaled
                    # Keep the forte bar centered and move the skill HUD to the right edge.
                    hud_x = scaled_width * 2 // 3
                    frame[:, width - scaled_width + hud_x:] = scaled[:, hud_x:]

                    matches = feature_set.find_one_feature(frame, name)

                    self.assertTrue(matches)
                    expected_x = round(source_x * scale)
                    expected_x += width - scaled_width if right_anchored else center_x
                    self.assertAlmostEqual(matches[0].x, expected_x, delta=2)
                    self.assertFalse(feature_set.find_one_feature(np.zeros_like(frame), name))

    def test_registered_character_templates_exist(self):
        from src.char.CharFactory import char_names

        feature_set = FeatureSet(False, None, 0.002, 0.002, template_folder='assets/templates')
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for name in char_names:
            with self.subTest(name=name):
                self.assertIsNotNone(feature_set.get_feature_by_name(frame, name))

    def test_lingyang_portrait_matches_restored_source_image(self):
        frame = cv2.imread('ok_templates/lingyang.png')
        self.assertIsNotNone(frame)
        for coco_json, template_folder in ((None, 'assets/templates'), ('ok_templates/coco_annotations.json', None)):
            with self.subTest(coco_json=coco_json, template_folder=template_folder):
                feature_set = FeatureSet(False, coco_json, 0.002, 0.002, template_folder=template_folder)
                matches = feature_set.find_one_feature(frame, 'char_lingyang', threshold=0.95)

                self.assertTrue(matches)
                self.assertEqual(matches[0].name, 'char_lingyang')
                self.assertGreaterEqual(float(matches[0].confidence), 0.95)

    def test_chisa_e2_template_loads_from_current_source_image(self):
        frame = cv2.imread('ok_templates/Chisa_e2.png')
        self.assertIsNotNone(frame)

        feature_set = FeatureSet(
            False,
            None,
            0.002,
            0.002,
            default_threshold=0.7,
            template_folder='assets/templates',
        )
        matches = feature_set.find_one_feature(
            frame,
            'chisa_e2',
            threshold=0.7,
        )

        self.assertTrue(matches)
        self.assertEqual(matches[0].name, 'chisa_e2')
        self.assertGreaterEqual(float(matches[0].confidence), 0.7)

    def test_template_larger_than_search_area_raises(self):
        feature_set = FeatureSet(False, 'missing.json', 0.002, 0.002, default_threshold=0.8)
        feature_set.width = 33
        feature_set.height = 37
        feature_set.feature_dict['large_template'] = Feature(np.zeros((39, 32, 3), dtype=np.uint8))

        frame = np.zeros((37, 33, 3), dtype=np.uint8)
        with self.assertRaises(cv2.error):
            feature_set.find_one_feature(
                frame,
                'large_template',
                box=Box(0, 0, 33, 37, name='small_search'),
            )


if __name__ == '__main__':
    unittest.main()
