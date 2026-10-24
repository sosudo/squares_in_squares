from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from rigid_interface_rotations import controls,rotation_cells,pair_gap_upper


class RigidRotationControls(unittest.TestCase):
    def test_real_rotated_composition_positive_and_negative_controls(self):
        self.assertTrue(controls()['valid'])

    def test_angular_exclusion_encloses_random_intermediate_angles_and_translations(self):
        p=np.array([[.5,.5,0.],[1.4,.7,.4],[.9,2.1,-.2]])
        mid=np.array([-.08,.01,.07]);half=.001
        A=rotation_cells(p,np.array([0.,2.]),7.,mid,half)
        B=rotation_cells(p,np.array([2.,0.]),7.,mid,half)
        bound=pair_gap_upper(A,B,0,2,half)
        rng=np.random.default_rng(17)
        for _ in range(100):
            aa=rotation_cells(p,np.array([0.,2.]),7.,mid+rng.uniform(-half,half,len(mid)),0.)
            bb=rotation_cells(p,np.array([2.,0.]),7.,mid+rng.uniform(-half,half,len(mid)),0.)
            self.assertTrue(np.all(pair_gap_upper(aa,bb,0,2,0.)<=bound+1e-9))
