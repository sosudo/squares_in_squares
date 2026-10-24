from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fractional_interface_search import potential_pairs,controls


class FractionalInterfaceTests(unittest.TestCase):
    def test_neighbor_bound_includes_a_pair_that_only_collides_after_sliding(self):
        p=np.array([[0.,0.,0.],[3.,0.,0.]])
        C=np.zeros((2,2,7));C[1,0,3]=-1
        low=np.zeros(7);high=np.zeros(7);high[3]=2.2
        pairs,mid,rho,radius=potential_pairs(p,C,low,high)
        self.assertGreater(np.linalg.norm(mid[1]-mid[0]),np.sqrt(2))
        self.assertIn((0,1),map(tuple,pairs))
        self.assertLess(abs(p[1,0]-high[3]),1)
        self.assertGreaterEqual(radius,np.sqrt(2)+2*rho.max())

    def test_forced_fractional_control_and_impossible_zero_buffer_control(self):
        result=controls()
        self.assertTrue(result['positive']['certificate']['valid'])
        self.assertAlmostEqual(result['positive']['phase_variables'][3],.02)
        self.assertIn(result['negative']['status'],('pair-domain-impossible','milp-2'))


if __name__=='__main__':unittest.main()
