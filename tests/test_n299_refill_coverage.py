from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from n299_refill_coverage import augment_pool
from refill_search import sat_gaps


class CoverageControls(unittest.TestCase):
    def test_augmentation_preserves_every_old_candidate_byte(self):
        old=np.array([[.5,.5],[1.5,.5]])
        hints=np.array([[2.5,2.5,0.]])
        result=augment_pool(old,np.empty((0,3)),3.,hints,.2)
        self.assertTrue({row.tobytes()for row in old}<={row.tobytes()for row in result})
        self.assertTrue(any(np.allclose(row,[2.4,2.4])for row in result))

    def test_new_hints_still_require_actual_core_separation(self):
        core=np.array([[1.5,1.5,np.pi/4]])
        result=augment_pool(np.array([[.5,.5]]),core,3.,np.array([[1.5,1.5,0.]]),.1)
        self.assertTrue(np.all(sat_gaps(result,core)>=0.))

    def test_zero_depth_does_not_duplicate_the_identity_pool(self):
        old=np.array([[.5,.5]])
        result=augment_pool(old,np.empty((0,3)),3.,np.array([[.5,.5,0.]]),0.)
        np.testing.assert_array_equal(result,old)
