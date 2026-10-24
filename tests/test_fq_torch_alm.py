"""Independence, state transport and native lifted-objective controls."""
from pathlib import Path
import sys
import unittest
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_torch_alm import independent_lbfgs,LiftedBatch,initialize_lines
from check_fq_torch_objective import call_native

torch.set_num_threads(1)


class BatchedLineSearchTests(unittest.TestCase):
    def test_heterogeneous_curvature_and_failed_replica_match_separate_solves(self):
        curvature=torch.tensor([1.,100.,7.],dtype=torch.float64)
        target=torch.tensor([[1.], [.1], [1.]],dtype=torch.float64)
        initial=torch.zeros_like(target)
        def evaluate(x):
            delta=x-target
            return .5*curvature*delta.square().sum(1),curvature[:,None]*delta
        def valid(x):
            result=x.abs().amax(1)<10
            result[2]=bool((x[2]==initial[2]).all())
            return result
        actual,state=independent_lbfgs(initial,evaluate,valid,steps=8,max_step=2.,backtracks=14)
        for b in range(3):
            def single_eval(x):
                delta=x-target[b:b+1]
                return .5*curvature[b]*delta.square().sum(1),curvature[b]*delta
            def single_valid(x):return (x==0).all(1)if b==2 else x.abs().amax(1)<10
            expected,other=independent_lbfgs(initial[b:b+1],single_eval,single_valid,steps=8,max_step=2.,backtracks=14)
            torch.testing.assert_close(actual[b:b+1],expected,rtol=0,atol=1e-14)
            if b<2:self.assertAlmostEqual(float(actual[b,0]),float(target[b,0]),places=11)
        self.assertTrue(torch.equal(actual[2],initial[2]))
        original_f,original_g=evaluate(initial)
        self.assertTrue(torch.equal(state['value'][2],original_f[2]))
        self.assertTrue(torch.equal(state['gradient'][2],original_g[2]))
        self.assertEqual(int(state['history_count'][2]),0)
        self.assertEqual(int(state['history_head'][2]),0)
        self.assertEqual(float(state['history_s'][2].abs().sum()),0.)
        self.assertEqual(float(state['history_y'][2].abs().sum()),0.)
        self.assertGreater(int(state['failed_lines'][2]),0)
        self.assertGreater(int(state['trial_evaluations'][1]),int(state['accepted_steps'][1]))

    def test_unsafe_trials_never_reach_the_evaluator(self):
        seen=[]
        def evaluate(x):
            self.assertTrue(bool((x.abs()<.25).all()));seen.append(x.clone())
            return .5*(x-1).square().sum(1),x-1
        result,state=independent_lbfgs(torch.zeros((2,1),dtype=torch.float64),evaluate,
            lambda x:x.abs().amax(1)<.25,steps=5,max_step=2.,backtracks=10)
        self.assertTrue(bool((result.abs()<.25).all()))
        self.assertGreater(len(seen),5)


class LiftedPairStateTests(unittest.TestCase):
    def fixture(self):
        p=torch.tensor([[[1.,1.,.1],[2.,1.,-.05],[3.,1.,.07],[5.,1.,0.]],
                        [[1.,1.,.2],[2.,1.,0.],[6.,1.,0.],[8.,1.,0.]]],dtype=torch.float64)
        return LiftedBatch(p,torch.tensor([10.,10.],dtype=torch.float64))

    def test_pair_transport_is_exact_and_padding_has_zero_multipliers(self):
        state=self.fixture();rng=torch.Generator().manual_seed(17)
        state.lines=torch.rand(state.lines.shape,generator=rng,dtype=torch.float64)
        state.pair_lambda=torch.rand(state.pair_lambda.shape,generator=rng,dtype=torch.float64)*state.mask[...,None]
        before={}
        for b in range(state.B):
            before[b]={tuple(ij.tolist()):(state.lines[b,k].clone(),state.pair_lambda[b,k].clone())
                       for k,ij in enumerate(state.pair_ids[b])if state.mask[b,k]}
        state.poses[0,2,0]=4.2
        mapping=state.rebuild(.3);fresh=initialize_lines(state.poses,state.pair_ids,.3)
        self.assertGreater(mapping['new'],0);self.assertGreater(mapping['removed'],0);self.assertGreater(mapping['retained'],0)
        for b in range(state.B):
            for k,ij in enumerate(state.pair_ids[b]):
                if not state.mask[b,k]:
                    self.assertEqual(float(state.pair_lambda[b,k].abs().sum()),0.);continue
                old=before[b].get(tuple(ij.tolist()))
                if old is None:
                    self.assertTrue(torch.equal(state.lines[b,k],fresh[b,k]))
                    self.assertEqual(float(state.pair_lambda[b,k].abs().sum()),0.)
                else:
                    self.assertTrue(torch.equal(state.lines[b,k],old[0]))
                    self.assertTrue(torch.equal(state.pair_lambda[b,k],old[1]))
        self.assertTrue(bool(state.valid(state.pack()).all()))

    def test_unequal_masked_lists_and_mu_match_native_prob(self):
        state=self.fixture();state.mu=torch.tensor([3.,71.],dtype=torch.float64)
        rng=np.random.default_rng(92)
        state.wall_lambda=torch.tensor(rng.uniform(0,.5,state.wall_lambda.shape),dtype=torch.float64)
        state.pair_lambda=torch.tensor(rng.uniform(0,.5,state.pair_lambda.shape),dtype=torch.float64)*state.mask[...,None]
        oracle=ROOT/'artifacts/fq-torch-objective-v1/native_prob_oracle'
        self.assertTrue(oracle.exists())
        for radius in(0.,.3):
            for fixed in(False,True):
                value,gradient=state.value_grad(state.pack(),radius,fixed)
                for b in range(state.B):
                    count=int(state.mask[b].sum());n=state.N
                    native=call_native(oracle,state.poses[b].numpy(),float(state.sides[b]),state.lines[b,:count].numpy(),
                        state.pair_ids[b,:count].numpy(),state.wall_lambda[b].numpy(),state.pair_lambda[b,:count].numpy(),
                        float(state.mu[b]),radius,fixed)
                    self.assertAlmostEqual(float(value[b]),native[0],places=10)
                    actual=np.concatenate((gradient[b,:3*n+1].numpy(),gradient[b,3*n+1:3*n+1+2*count].numpy()))
                    np.testing.assert_allclose(actual,native[2],rtol=1e-11,atol=1e-10)
                    self.assertEqual(float(gradient[b,3*n+1+2*count:].abs().sum()),0.)

    def test_small_pair_repair_returns_to_exact_zero_radius(self):
        p=torch.tensor([[[1.,1.,0.],[1.8,1.,0.]],[[1.,1.,0.],[1.9,1.,0.]]],dtype=torch.float64)
        state=LiftedBatch(p,torch.tensor([4.,4.],dtype=torch.float64))
        initial=state.poses.clone();saved=[]
        for radius in(.3,.1,0.):
            rows=state.stage(radius,True,outer=5,inner=30,callback=lambda poses,record:saved.append((poses,record)))
            self.assertEqual(rows[-1]['radius'],radius)
        self.assertTrue(torch.equal(state.sides,torch.tensor([4.,4.],dtype=torch.float64)))
        self.assertEqual(tuple(state.poses.shape),tuple(initial.shape))
        self.assertGreater(float((state.poses-initial).abs().max()),.01)
        self.assertLess(max(saved[-1][1]['violation']),1e-8)
        self.assertEqual(saved[-1][1]['radius'],0.)
        self.assertTrue(all(not r['verified']for _,r in saved))


if __name__=='__main__':unittest.main()
