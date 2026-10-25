import unittest

import cv2
import numpy as np

from ok.feature.Box import Box
from ok.feature.Feature import Feature
from ok.feature.FeatureSet import FeatureSet


class TestFeatureSet(unittest.TestCase):
    def test_registered_character_templates_exist(self):
        from src.char.CharFactory import char_names

        feature_set = FeatureSet(False, 'assets/coco_annotations.json', 0.002, 0.002)
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for name in char_names:
            with self.subTest(name=name):
                self.assertIsNotNone(feature_set.get_feature_by_name(frame, name))

    def test_lingyang_portrait_matches_restored_source_image(self):
        frame = cv2.imread('ok_templates/lingyang.png')
        self.assertIsNotNone(frame)
        for coco_json in ('assets/coco_annotations.json', 'ok_templates/coco_annotations.json'):
            with self.subTest(coco_json=coco_json):
                feature_set = FeatureSet(False, coco_json, 0.002, 0.002)
                matches = feature_set.find_one_feature(frame, 'char_lingyang', threshold=0.95)

                self.assertTrue(matches)
                self.assertEqual(matches[0].name, 'char_lingyang')
                self.assertGreaterEqual(float(matches[0].confidence), 0.95)

    def test_chisa_e2_template_loads_from_current_source_image(self):
        frame = cv2.imread('ok_templates/Chisa_e2.png')
        self.assertIsNotNone(frame)

        feature_set = FeatureSet(
            False,
            'assets/coco_annotations.json',
            0.002,
            0.002,
            default_threshold=0.7,
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
