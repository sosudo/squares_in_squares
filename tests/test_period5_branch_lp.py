from pathlib import Path
import sys
import time
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from period5_branch_lp import corner_pairs,choose,synthetic_control


class CornerBranchControls(unittest.TestCase):
    def test_diagonal_corner_has_two_distinct_disjuncts_but_edge_contact_has_one(self):
        diagonal=np.array([[.5,.5,0.],[1.5,1.5,0.]])
        self.assertEqual(corner_pairs(diagonal,True),{(0,1)})
        diagonal[1,1]=.5
        self.assertEqual(corner_pairs(diagonal,True),set())

    def test_alternative_tied_choices_choose_different_valid_unit_axes(self):
        q=np.array([[.5,.5,0.],[1.5,1.5,0.]])
        pair=np.array([[0,1]])
        first,ties=choose(q,pair,'baseline',np.random.default_rng(1))
        second,_=choose(q,pair,'prefer_y',np.random.default_rng(1))
        self.assertEqual(ties,1)
        np.testing.assert_array_equal(first[(0,1)][:2],(1.,0.))
        np.testing.assert_array_equal(second[(0,1)][:2],(0.,1.))

    def test_omitted_corner_overlap_is_detected_then_repaired_by_an_exact_sat_cut(self):
        report=synthetic_control(time.monotonic()+10)
        self.assertEqual(report['trace'][0]['violating_pairs'],1)
        self.assertEqual(report['added_violated_pair_cuts'],1)
        self.assertEqual(report['trace'][-1]['violating_pairs'],0)
        self.assertTrue(report['trace'][-1]['passed_all_pair_and_wall_numerical_screen'])
