from pathlib import Path
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from cpu_recipe_replay import compatible,cross_block_separated,public_functions,select_chain


def option(f,br,tl):
    return {'f':f,'profile':{'br_bin':br,'tl_bin':tl}}


class RecipeReplayTests(unittest.TestCase):
    def test_chain_dp_uses_compatible_pair_instead_of_greedy_scalar(self):
        choices=[[option(.7,7,0),option(.72,3,0)],
                 [option(.71,0,4),option(.9,0,8)]]
        selected=select_chain(choices,[{'mode':3},{'mode':0}])
        self.assertEqual([g['f']for g in selected],[.72,.71])

    def test_buffered_join_keeps_public_bypass_rule(self):
        self.assertFalse(compatible(option(.7,7,0),option(.7,0,4),0))
        self.assertTrue(compatible(option(.7,7,0),option(.7,0,4),1))
        self.assertTrue(compatible(option(.7,7,0),option(.7,0,4),2))

    def test_public_stitch_imports_without_cuda_and_preserves_count(self):
        stitch,border=public_functions(ROOT/'vendor/lightning_ftmc')
        p=np.array([[.5,.5,0.],[1.5,.5,0.]])
        q,k=stitch([(0,3)],[dict(w=2,h=1,dm=0,f=.1,donor=0)],[(p,'test')])
        self.assertEqual(k,2)
        self.assertEqual(len(q),4)
        self.assertTrue(np.all(q[:,2]==0))
        self.assertEqual(len(border(q,1)),9)

    def test_exact_join_accepts_separated_and_touching_but_rejects_overlap(self):
        previous=np.array([[.5,.5,0.]])
        separated=np.array([[.6,.6,0.]])
        touching=np.array([[.5,.5,0.]])
        overlapping=np.array([[0.,1.,0.]])
        self.assertTrue(cross_block_separated(previous,separated,1,1,0))
        self.assertTrue(cross_block_separated(previous,touching,1,1,0))
        self.assertFalse(cross_block_separated(previous,overlapping,1,1,0))

    def test_continuous_supports_can_remove_quantization_false_negative(self):
        a=option(.7,18,0);b=option(.7,0,17)
        a['profile'].update(outgoing_degrees=45.,outgoing_br_support=.1)
        b['profile'].update(incoming_degrees=45.,incoming_tl_support=.12)
        self.assertFalse(compatible(a,b,0))
        self.assertTrue(compatible(a,b,0,'continuous'))

    def test_sat_join_can_accept_nonseparable_profile_pair(self):
        a=option(.7,20,0);b=option(.7,0,10)
        a['pose']=np.array([[.5,.5,0.]]);b['pose']=np.array([[.5,.5,0.]])
        self.assertFalse(compatible(a,b,0))
        self.assertTrue(compatible(a,b,0,'sat',{'w':1},{'h':1}))


if __name__=='__main__':unittest.main()
