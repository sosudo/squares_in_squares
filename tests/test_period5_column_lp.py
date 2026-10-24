from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from period5_column_lp import mapping,sat,clusters


class ColumnLPControls(unittest.TestCase):
    def test_rotating_and_sliding_a_column_preserves_the_unit_dimer(self):
        t={'n':3,'x':np.array([3.]),'y':np.array([3.]),'u':np.array([1.]),'v':np.array([2.]),
           'upright':np.array([2]),'core':np.array([0,1]),'gx':np.array([0]),'gy':np.array([0]),
           'column':np.array([0,0]),'slot':np.array([0,1]),'theta':.3,'origin':np.array([4.,4.])}
        _,_,_,_,q=mapping(t,np.array([.2]),np.array([.4]))
        self.assertEqual(q.shape,(3,3))
        self.assertAlmostEqual(float(np.linalg.norm(q[1,:2]-q[0,:2])),1.,places=13)
        self.assertAlmostEqual(q[0,2],.5)
        self.assertAlmostEqual(q[1,2],.5)
        np.testing.assert_array_equal(q[2],np.array([3.,3.,0.]))

    def test_full_sat_rejects_a_duplicate_and_accepts_unit_contact(self):
        touching=np.array([[.5,.5,0.],[1.5,.5,0.]])
        self.assertAlmostEqual(sat(touching),0.)
        touching[1]=touching[0]
        self.assertLess(sat(touching),-.9)

    def test_grid_lines_do_not_merge_distinct_reference_phases(self):
        labels,lines=clusters([.5,.5+1e-9,.51,1.5])
        np.testing.assert_array_equal(labels,[0,0,1,2])
        self.assertEqual(len(lines),3)
