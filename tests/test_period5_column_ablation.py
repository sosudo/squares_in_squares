from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import period5_column_lp as base
from period5_column_ablation import relaxed_template,preset_mapping,dimensions


class ColumnAblationControls(unittest.TestCase):
    def fixture(self):
        t={'n':4,'x':np.array([3.]),'y':np.array([3.,4.]),'u':np.array([1.]),'v':np.array([2.]),
           'upright':np.array([2,3]),'core':np.array([0,1]),'gx':np.array([0,0]),'gy':np.array([0,1]),
           'column':np.array([0,0]),'slot':np.array([0,1]),'theta':.3,'origin':np.array([4.,4.])}
        return t,base.mapping(t,np.zeros(1),np.zeros(1))[-1]

    def test_dimer_split_releases_the_relative_position_without_changing_seed(self):
        t,p=self.fixture();split=relaxed_template(t,p,False,[0])
        self.assertNotEqual(split['column'][0],split['column'][1])
        self.assertEqual(dimensions(split),dimensions(t)+2)
        reconstructed=base.mapping(split,np.zeros(2),np.zeros(2))[-1]
        np.testing.assert_allclose(reconstructed,p,atol=1e-14,rtol=0)

    def test_individual_upright_variables_release_a_shared_line(self):
        t,p=self.fixture();free=relaxed_template(t,p,True)
        self.assertNotEqual(free['gx'][0],free['gx'][1])
        self.assertEqual(dimensions(free),dimensions(t)+1)
        np.testing.assert_allclose(base.mapping(free,np.zeros(1),np.zeros(1))[-1],p,atol=1e-14,rtol=0)

    def test_preset_angles_change_only_the_selected_unit_square_orientations(self):
        t,p=self.fixture();t['upright_angles']=np.array([.02,-.01])
        q=preset_mapping(t,np.zeros(1),np.zeros(1))[-1]
        np.testing.assert_array_equal(q[:,:2],p[:,:2])
        np.testing.assert_allclose(q[t['upright'],2],[.02,-.01])
