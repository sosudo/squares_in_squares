from pathlib import Path
import sys
import time
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from n299_direct_refill import templates,changed_core,candidates,core_lp
from refill_search import sat_gaps


class DirectRefillControls(unittest.TestCase):
    def test_finite_matrix_has_fourteen_count_preserving_templates(self):
        self.assertEqual(len(templates()),14)
        self.assertEqual(3*len(templates()),42)
        a=.4;p=np.array([[1.,1.,a],[1-np.sin(a),1+np.cos(a),a],[3.,3.,a]])
        q=changed_core(p,np.array([0,1]),templates()[-1],.02)
        self.assertEqual(q.shape,p.shape)
        self.assertAlmostEqual(float(np.linalg.norm(q[1,:2]-q[0,:2])),1.,places=13)

    def test_protected_hints_are_screened_and_not_asserted_valid(self):
        core=np.array([[2.,2.,np.pi/4]])
        hints=np.array([[2.,2.,0.]])
        pool,_=candidates(core,4.,hints,0.)
        self.assertGreater(len(pool),0)
        self.assertTrue(np.all(sat_gaps(pool,core)>=0))
        self.assertFalse(np.any(np.linalg.norm(pool-[2.,2.],axis=1)<1e-9))

    def test_core_lp_keeps_unit_angles_count_and_motion_bound(self):
        warm=np.array([[1.,1.,.3],[2.5,2.5,.3]])
        q,info=core_lp(warm,4.,time.monotonic()+5)
        self.assertIsNotNone(q)
        self.assertEqual(q.shape,warm.shape)
        np.testing.assert_array_equal(q[:,2],warm[:,2])
        self.assertLessEqual(info['maximum_center_motion'],.10000001)
