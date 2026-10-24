"""Avoid wasting independent GPU arms on transformed copies of one tilted core."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from full_puzzle_bank import core_signature


class CoreSignatureTests(unittest.TestCase):
    def setUp(self):
        self.poses = np.array([[1., 2., .4], [2., 3., .3], [4., 7., -.2],
                               [2., 5., .7], [20., 20., 0.]])

    def test_translation_reflection_transpose_and_row_order(self):
        expected = core_signature(self.poses)
        q = self.poses[::-1].copy()
        q[:, :2] = q[:, [1, 0]]
        q[:, 2] = np.pi/2-q[:, 2]
        q[:, 0] *= -1
        q[:, 2] *= -1
        q[:, :2] += [13., -41.]
        self.assertEqual(core_signature(q), expected)

    def test_upright_extension_is_duplicate_but_tilted_change_is_not(self):
        expected = core_signature(self.poses)
        extended = np.vstack((self.poses, [[45., 31., np.pi/2]]))
        self.assertEqual(core_signature(extended), expected)
        extended[0, 2] += .01
        self.assertNotEqual(core_signature(extended), expected)


if __name__ == '__main__':
    unittest.main()
