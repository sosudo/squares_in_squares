import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_full_structural as search


class StructuralTests(unittest.TestCase):
    def setUp(self):
        self.p = np.array([[float(i),float(i),.3] for i in range(16)])

    def test_exact_count_and_parent_binding(self):
        q,record = search.mutate(self.p,7,'delete',1)
        self.assertEqual(len(q),15)
        np.testing.assert_array_equal(q,np.delete(self.p,7,axis=0))
        self.assertEqual(record['ancestor_geometry_sha256'],search.geometry_sha(self.p))
        self.assertEqual(record['optimizer_input_geometry_sha256'],search.geometry_sha(q))
        self.assertEqual(record['feasible_seed_geometry_sha256'],search.geometry_sha(q))

    def test_rotation_preserves_internal_distances(self):
        q,record = search.mutate(self.p,7,'rotate6',-1)
        original = np.delete(self.p,7,axis=0)
        chosen = record['selected']
        # Direct pairwise distances in the coherently rotated cluster.
        old = np.linalg.norm(original[chosen,None,:2]-original[None,chosen,:2],axis=-1)
        new = np.linalg.norm(q[chosen,None,:2]-q[None,chosen,:2],axis=-1)
        np.testing.assert_allclose(old,new,atol=1e-12)
        self.assertGreater(record['maximum_angle_displacement'],.1)
        self.assertNotEqual(record['feasible_seed_geometry_sha256'],record['optimizer_input_geometry_sha256'])

    def test_bend_is_coherent_and_bounded(self):
        q,record = search.mutate(self.p,7,'bend',1)
        self.assertEqual(len(q),15)
        self.assertGreater(record['maximum_center_displacement'],.1)
        self.assertLessEqual(record['maximum_center_displacement'],.18000001)
        self.assertEqual(record['optimizer_input_geometry_sha256'],search.geometry_sha(q))

    def test_native_timeout_is_bounded(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            search.run_native([sys.executable,'-c','import time;time.sleep(30)'],.1)

    def test_control_mode_preserves_deleted_input(self):
        q,record = search.mutate(self.p,7,'control',1)
        np.testing.assert_array_equal(q,np.delete(self.p,7,axis=0))
        self.assertEqual(record['selected'],[])


if __name__ == '__main__':
    unittest.main()
