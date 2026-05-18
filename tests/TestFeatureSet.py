import unittest

import numpy as np

from ok.feature.Box import Box
from ok.feature.Feature import Feature
from ok.feature.FeatureSet import FeatureSet


class TestFeatureSet(unittest.TestCase):
    def test_template_larger_than_search_area_returns_no_match(self):
        feature_set = FeatureSet(False, 'missing.json', 0.002, 0.002, default_threshold=0.8)
        feature_set.width = 33
        feature_set.height = 37
        feature_set.feature_dict['large_template'] = Feature(np.zeros((39, 32, 3), dtype=np.uint8))

        frame = np.zeros((37, 33, 3), dtype=np.uint8)
        matches = feature_set.find_one_feature(
            frame,
            'large_template',
            box=Box(0, 0, 33, 37, name='small_search'),
        )

        self.assertEqual([], matches)


if __name__ == '__main__':
    unittest.main()
