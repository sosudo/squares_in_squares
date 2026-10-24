import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compose_gadgets import Gadget, border_expand, legalize, side, staircase_dp, stitch
from validate_submission import Square, validate_puzzle


def five_square_gadget():
    L = 2 + math.sqrt(.5)
    p = np.array([[.5, .5, 0], [L-.5, .5, 0], [.5, L-.5, 0],
                  [L-.5, L-.5, 0], [L/2, L/2, math.pi/4]])
    p = legalize(p)
    return Gadget(2, 2, 1, 0, 0, side(p)-2 + 3e-8, p, 'five-square diamond')


def certified(p):
    rows = [Square(*(format(float(v), '.17g') for v in row)) for row in p]
    return validate_puzzle(len(p), rows)['valid']


class CompositionTests(unittest.TestCase):
    def test_occupied_tips_need_a_buffer(self):
        g = five_square_gadget()
        self.assertIsNone(stitch([(0, 3), (0, 0)], [g], 4))
        joined = stitch([(0, 3), (0, 1)], [g], 5)
        self.assertIsNotNone(joined)
        self.assertEqual(len(joined), 27)
        self.assertTrue(certified(joined))
        self.assertLess(side(joined), 5.708)

    def test_dp_requires_buffer_for_two_occupied_tips(self):
        g = five_square_gadget()
        value, *_ = staircase_dp([g], rounds=1)
        self.assertTrue(math.isinf(value[4, 4, 2, 0]))
        self.assertAlmostEqual(value[5, 4, 2, 0], g.f)
        self.assertAlmostEqual(value[4, 5, 2, 0], g.f)

    def test_l_frame_preserves_feasibility_and_expected_count(self):
        g = five_square_gadget()
        expanded = legalize(border_expand(g.p, 2))
        self.assertEqual(len(expanded), 5 + 2*2 + 2*4)
        self.assertTrue(certified(expanded))
        self.assertAlmostEqual(side(expanded), side(g.p)+2, places=6)


if __name__ == '__main__':
    unittest.main()
