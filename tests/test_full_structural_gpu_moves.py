import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from full_structural_gpu_moves import coherent_start,geometry_sha
from full_structural_gpu_worker import dense_oracle


class FullCountMoves(unittest.TestCase):
    def setUp(self):
        self.p = np.array([[float(i),float(i),.3]for i in range(20)]+[[1.,8.,0.],[2.,8.,0.]])

    def test_full_count_uprights_and_hashes(self):
        for mode in ('identity','column_slide','bend','hinge'):
            q,m = coherent_start(self.p,412,mode,.18)
            self.assertEqual(q.shape,self.p.shape)
            np.testing.assert_array_equal(q[-2:],self.p[-2:])
            self.assertEqual(m['source_geometry_sha256'],geometry_sha(self.p))
            self.assertEqual(m['input_geometry_sha256'],geometry_sha(q))
            if mode!='identity':self.assertGreater(m['maximum_displacement'],.01)

    def test_hinge_preserves_selected_internal_distances(self):
        q,m = coherent_start(self.p,43,'hinge',.3);ids=m['selected']
        old = np.linalg.norm(self.p[ids,None,:2]-self.p[None,ids,:2],axis=-1)
        new = np.linalg.norm(q[ids,None,:2]-q[None,ids,:2],axis=-1)
        np.testing.assert_allclose(old,new,atol=1e-12)

    def test_dense_oracle_pair_and_wall_weights(self):
        p=np.array([[.5,.5,0.],[1.4,.5,0.]])
        energy,maximum=dense_oracle(p,[3.,3.])
        self.assertAlmostEqual(maximum,.1+2e-10,places=12)
        self.assertAlmostEqual(energy,.5*(.1+2e-10)**2,places=12)
        p[0,0]=.4
        energy,maximum=dense_oracle(p,[3.,3.])
        self.assertAlmostEqual(maximum,.1,places=12)
        self.assertAlmostEqual(energy,.02,places=12)


if __name__=='__main__':unittest.main()
