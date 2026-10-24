import math
from pathlib import Path
import sys
import unittest
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from birth_continuation import mixed_energy,numpy_oracle,unit_reference,cpu_quench


class BirthControls(unittest.TestCase):
    def test_parallel_unequal_tie_uses_attainable_limiting_gradients(self):
        p=np.array([[1.,1.,0.],[1.5,1.3,0.]])
        def gradient(q):
            t=torch.tensor(q[None],dtype=torch.float64,requires_grad=True)
            e=mixed_energy(t,torch.tensor([[4.,4.]],dtype=torch.float64),.2)['energy'].sum()
            e.backward();return float(e.detach()),t.grad.detach().numpy()[0]
        e,g=gradient(p);near=[]
        for direction in (-1.,1.):
            q=p.copy();q[-1,2]+=direction*1e-7;near.append(gradient(q)[1])
        self.assertAlmostEqual(e,.01,places=14)
        self.assertLess(np.max(abs(g-np.mean(near,axis=0))),1e-7)
        self.assertTrue(np.allclose(g[:,2],[-.06,0.],atol=1e-14))

    def test_independent_mixed_oracle_and_gradient(self):
        p=np.array([[.42,.71,.13],[1.1,.9,.57],[1.8,.45,-.27],[1.49,1.49,.37]])
        box=np.array([2.1,2.2]); sizes=(.05,.41,1.)
        for size in sizes:
            q=torch.tensor(p[None],dtype=torch.float64,requires_grad=True)
            e=mixed_energy(q,torch.tensor(box[None],dtype=torch.float64),size)['energy'].sum();e.backward()
            self.assertAlmostEqual(float(e),numpy_oracle(p,box,size)['energy'],places=12)
            for i in range(len(p)):
                for k in range(3):
                    plus=p.copy();minus=p.copy();plus[i,k]+=1e-6;minus[i,k]-=1e-6
                    fd=(numpy_oracle(plus,box,size)['energy']-numpy_oracle(minus,box,size)['energy'])/2e-6
                    self.assertLess(abs(fd-float(q.grad[0,i,k])),2e-7)

    def test_all_unit_identity_including_exact_ties(self):
        fixtures=[np.array([[1.,1.,0.],[1.8,1.8,0.],[2.,1.,0.]]),
                  np.array([[1.,1.,.31],[1.8,1.2,.31],[2.,1.9,-.2]])]
        for p in fixtures:
            a=torch.tensor(p[None],dtype=torch.float64,requires_grad=True);b=a.detach().clone().requires_grad_()
            box=torch.tensor([[3.,3.]],dtype=torch.float64)
            x=mixed_energy(a,box,1.)['energy'];y=unit_reference(b,box);x.sum().backward();y.sum().backward()
            self.assertTrue(torch.equal(x,y))
            self.assertLess(float((a.grad-b.grad).abs().max()),1e-14)

    def test_nontouching_containment_last_index_and_walls(self):
        box=torch.tensor([[3.,3.]],dtype=torch.float64)
        p=torch.tensor([[[1.,1.,0.],[1.,1.,0.]]],dtype=torch.float64)
        self.assertAlmostEqual(float(mixed_energy(p,box,.2)['energy']),.36)
        p[0,1,0]=2.; self.assertEqual(float(mixed_energy(p,box,.2)['energy']),0.)
        p[0,1,0]=3.;self.assertAlmostEqual(float(mixed_energy(p,box,.2)['energy']),.01)
        with self.assertRaises(ValueError):mixed_energy(p,box,1.01)
        with self.assertRaises(ValueError):mixed_energy(p.float(),box,.2)

    def test_nontrivial_five_square_growth(self):
        torch.set_num_threads(1)
        initial=np.array([[.55,.55,0.],[2.17,.55,0.],[.55,2.17,0.],[2.17,2.17,0.],[1.36,1.36,math.pi/4]])
        self.assertEqual(numpy_oracle(initial,[2.72,2.72],.05)['energy'],0.)
        self.assertGreater(numpy_oracle(initial,[2.72,2.72],1.)['energy'],.001)
        q=initial.copy()
        for size in (.05,.2,.4,.6,.8,1.):q,_=cpu_quench(q,[2.72,2.72],size)
        self.assertLess(numpy_oracle(q,[2.72,2.72],1.)['energy'],1e-20)
        self.assertGreater(np.max(np.linalg.norm(q[:4,:2]-initial[:4,:2],axis=1)),.02)


if __name__=='__main__':unittest.main()
