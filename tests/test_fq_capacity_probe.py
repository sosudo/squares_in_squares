from pathlib import Path
import sys
import time
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_capacity_probe as probe
from refill_capacity import split_core, capacity


class CapacityProbeTests(unittest.TestCase):
    def test_transpose_canonicalization_preserves_type_and_angles(self):
        p=np.array([[.5,.5,0.],[1.5,.5,0.]])
        key,q,transposed=probe.canonical_pose('2_1_0',p)
        self.assertEqual(key,'1_2_0')
        self.assertTrue(transposed)
        self.assertTrue(np.allclose(q[:,2],np.pi/2))
        self.assertEqual(len(q),2)

    def test_near_uprights_are_reclassified_only_when_requested(self):
        p=np.array([[.6,.6,.01],[1.6,.6,0.]])
        self.assertEqual(len(split_core(p)[0]),1)
        self.assertEqual(len(split_core(p,.018)[0]),0)
        q,info=capacity(p,2.2,1.2,depth=1,upright_threshold=.018)
        self.assertEqual(info['core'],0)
        self.assertTrue(np.all(q[:,2]==0))
        # Every retained pair is a strict non-overlapping upright pair.
        for i in range(len(q)):
            for j in range(i):
                self.assertGreaterEqual(float(max(abs(q[i,:2]-q[j,:2]))),1.)

    def test_finite_worker_is_killed_at_deadline(self):
        original=probe.capacity
        def slow(*args,**kwargs):
            time.sleep(10)
            return None,None
        probe.capacity=slow
        try:
            result,elapsed=probe.bounded_capacity(np.array([[.5,.5,0.]]),1.,1.,1e-6,.3)
        finally:
            probe.capacity=original
        self.assertEqual(result[0],'timeout')
        self.assertLess(elapsed,.6)

    def test_overlap_is_rejected_by_full_certification(self):
        result=probe.full_certificate(np.array([[.5,.5,0.],[.5,.5,0.]]))
        self.assertFalse(result['valid'])


if __name__=='__main__':
    unittest.main()
