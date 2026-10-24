"""Larger regions keep explicitly distant boundary squares frozen."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_large_region_campaign as large


class LargeRegionTests(unittest.TestCase):
    def test_sizes_and_distant_wall_preservation(self):
        pose = np.array([[x+.5, y+.5, 0.] for x in range(7) for y in range(21)])
        original = pose.copy()
        for count in [64, 96]:
            frozen, selection = large.large_neighborhood(pose, 91801, .3, count)
            self.assertEqual(selection['actual_free_count'], count)
            self.assertEqual(selection['fallback_nearest_count'], 0)
            self.assertTrue(selection['preserved_distant_wall_indices'])
            self.assertTrue(set(selection['preserved_distant_wall_indices']).issubset(frozen))
            self.assertTrue(set(selection['free_indices']).isdisjoint(frozen))
            self.assertEqual(set(selection['free_indices']) | set(frozen), set(range(len(pose))))
            np.testing.assert_array_equal(pose, original)
            again, same = large.large_neighborhood(pose, 91801, .3, count)
            np.testing.assert_array_equal(frozen, again)
            self.assertEqual(selection, same)


if __name__ == '__main__':
    unittest.main()
