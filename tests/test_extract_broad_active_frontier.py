import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from extract_broad_active_frontier import conditional_gain, family, orient, profiles


def test_tied_bottlenecks_require_joint_improvement():
    chain = [{'f': .8}, {'f': .8}, {'f': .6}]
    assert conditional_gain(chain, {0}, .01, 100) == 0
    assert math.isclose(conditional_gain(chain, {0, 1}, .01, 100), .001)


def test_partner_caps_single_stage_headroom():
    chain = [{'f': .8}, {'f': .797}]
    assert math.isclose(conditional_gain(chain, {0}, .01, 100), .0003)
    assert conditional_gain(chain, {1}, .01, 100) == 0


def test_wall_phase_changes_separator_profiles():
    p = np.array([[1.2, .5, 0.]])
    original = profiles(p, 1, 1, 45., 45., 32)
    shifted = profiles(p-np.array([.2, 0., 0.]), 1, 1, 45., 45., 32)
    assert original['outgoing_br_support'] > shifted['outgoing_br_support']
    assert original['br_bin'] != shifted['br_bin']


def test_transpose_family_preserves_distinct_geometry():
    stage = {'w': 17, 'h': 5, 'dm': 7}
    transposed = {'w': 5, 'h': 17, 'dm': 7}
    assert family(stage) == family(transposed)
    p = np.array([[.6, .7, .3], [2., 3., -.2]])
    q = orient(p, True, -1, 1)
    assert np.allclose(q[:, 2], -(math.pi/2-p[:, 2]))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(test) for test in (
        test_tied_bottlenecks_require_joint_improvement,
        test_partner_caps_single_stage_headroom,
        test_wall_phase_changes_separator_profiles,
        test_transpose_family_preserves_distinct_geometry))


if __name__ == '__main__':
    unittest.main()
