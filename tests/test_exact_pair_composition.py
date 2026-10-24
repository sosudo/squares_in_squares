from pathlib import Path
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from exact_pair_composition import build_pair,pair_dimensions,positive_control
from cpu_recipe_replay import public_functions


class ExactPairTests(unittest.TestCase):
    def test_join_mode_dimensions_and_surplus(self):
        a={'w':5,'h':17,'d':8};b={'w':17,'h':5,'d':8}
        self.assertEqual(pair_dimensions(a,b,0),(22,22,16))
        self.assertEqual(pair_dimensions(a,b,1),(23,22,16))
        self.assertEqual(pair_dimensions(a,b,2),(22,23,16))
        self.assertEqual(22**2+16,500)

    def test_larger_box_preserves_exact_count_formula(self):
        stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
        a={'w':2,'h':1,'d':0,'f':.1,'pose':np.array([[.5,.5,0.],[1.5,.5,0.]])}
        b={'w':1,'h':2,'d':0,'f':.1,'pose':np.array([[.5,.5,0.],[.5,1.5,0.]])}
        for mode in (0,1,2):
            w,h,d=pair_dimensions(a,b,mode)
            q=build_pair(a,b,mode,max(w,h)+1,stitch)
            self.assertIsNotNone(q)
            self.assertEqual(len(q),(max(w,h)+1)**2+d)

    def test_rotated_surplus_positive_control_is_fully_certified(self):
        stitch,_=public_functions(ROOT/'vendor/lightning_ftmc')
        proof=positive_control(stitch)
        self.assertTrue(proof['certificate']['valid'])
        self.assertEqual(proof['count'],27)
        self.assertEqual(proof['expanded_container_count'],38)


if __name__=='__main__':unittest.main()
