from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from fq_dual_cage_soft import retaining_stage_source,cage_selection,inherited_group_run


class DualCageControls(unittest.TestCase):
    def test_stage_overlay_removes_only_scalar_discard_and_keeps_full_gates(self):
        source=retaining_stage_source()
        self.assertNotIn('original_side+.005',source)
        self.assertIn('certificate = full_certificate(q)',source)
        self.assertIn('failed-rigid-return-trace',source)
        self.assertIn("status='failed-clearance'",source)

    def test_source_cage_is_explicitly_free_in_both_region_sizes(self):
        p=np.zeros((299,3));p[:,:2]=np.random.default_rng(2).normal(size=(299,2))
        for count in(40,64):
            frozen,selection=cage_selection(p,299,count)
            self.assertEqual(len(frozen),299-count)
            self.assertTrue({112,127,276,277}<=set(selection['free_indices']))

    def test_native_timeout_is_bounded(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            inherited_group_run([sys.executable,'-c','import time; time.sleep(1)'],timeout=.02)
