import unittest

import cv2
import numpy as np

from ok.feature.Box import Box
from ok.feature.Feature import Feature
from ok.feature.FeatureSet import FeatureSet


class TestFeatureSet(unittest.TestCase):
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
