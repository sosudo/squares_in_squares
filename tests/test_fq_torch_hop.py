"""Finite operator/acceptance and interrupted-publication controls; no search."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np
try:
    import torch
except ImportError:
    torch=None

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
if torch is not None:
    import fq_torch_hop as hop
    import fq_torch_hop_pilot as pilot


@unittest.skipIf(torch is None,'Optional Torch environment unavailable')
class HopControls(unittest.TestCase):
    def test_dense_pair_wall_and_final_index_energy(self):
        p=torch.tensor([[[2.,2.,0.],[2.9,2.2,0.]]],dtype=torch.float64)
        result=hop.physical_energy(p,torch.tensor([10.],dtype=torch.float64))
        self.assertAlmostEqual(float(result['energy'][0]),.01,places=14)
        self.assertAlmostEqual(float(result['per_square'].sum()),.01,places=14)
        p=torch.tensor([[[.4,1.,0.],[5.,5.,0.],[.4,1.,0.]]],dtype=torch.float64)
        result=hop.physical_energy(p,torch.tensor([10.],dtype=torch.float64))
        self.assertAlmostEqual(float(result['pair_energy'][0]),1.,places=14)
        self.assertAlmostEqual(float(result['wall_energy'][0]),.02,places=14)

    def test_ratio_threshold_zero_and_invalid_proposal(self):
        accepted,_=hop.acceptance(np.ones(6),[.1,100,100,np.nan,-1,10],[.3,1,1,.3,.3,3],[.9,.02,.001,.5,.5,.5])
        np.testing.assert_array_equal(accepted,[True,False,True,False,False,False])
        accepted,rule=hop.acceptance([0,0,1],[0,1,0],[.3,.3,.3],[.5,.5,.5])
        np.testing.assert_array_equal(accepted,[True,False,True]);self.assertTrue(np.isfinite(rule['log_ratio']).all())
        low,_=hop.acceptance([1],[100],[.3],[.01]);high,_=hop.acceptance([1],[100],[3],[.01])
        self.assertFalse(low[0]);self.assertTrue(high[0])

    def test_realized_operator_masks_and_finite_design(self):
        p=np.array([[x+.5,y+.5,0.]for x in range(5)for y in range(5)],float)
        for mode in hop.OPERATORS:
            for seed in range(6):
                q,record=hop.mutate(p,np.arange(1,26),np.random.default_rng(seed),1.5,mode)
                changed=np.flatnonzero(np.any(q!=p,axis=1)).tolist()
                self.assertEqual(changed,record['changed_ids']);self.assertGreater(len(changed),0)
                self.assertTrue(set(changed)<=set(record['selected_ids']));self.assertFalse(record['jam_line_claimed'])
        rows=hop.chain_design(['a','b','c']);self.assertEqual(len(rows),32)
        for temperature,count in((.3,8),(1.,12),(3.,12)):
            subset=[r for r in rows if r['temperature']==temperature];self.assertEqual(len(subset),count)
            for amp in(1.,1.5):
                for side in(18.807,18.803):self.assertEqual(sum(r['amplitude']==amp and r['side']==side for r in subset),count//4)

    def test_cooling_boundary_uses_parent_epoch(self):
        base=np.array([.3,1.,3.]);a,phase=pilot.temperature_schedule(base,200.,139.999)
        self.assertEqual(phase,'hot');np.testing.assert_array_equal(a,base)
        a,phase=pilot.temperature_schedule(base,200.,140.)
        self.assertEqual(phase,'cool');np.testing.assert_array_equal(a,base*.1)


@unittest.skipIf(torch is None,'Optional Torch environment unavailable')
class PacketControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=Path.cwd();os.chdir(self.temp.name)
    def tearDown(self):os.chdir(self.previous);self.temp.cleanup()
    def inputs(self):
        p=np.arange(12,dtype=np.float64).reshape(2,2,3)
        return dict(current_before=p,proposal_input=p+.1,best_before=p,sides=np.ones(2)*10),dict(design=[{},{}],round=0)
    def completed(self,arrays,metadata):
        p=arrays['current_before'];arrays=dict(arrays,current_after=p,proposal_quenched=p+.2,best_after=p,
            next_energy=np.array([1.,2.]),best_energy_after=np.array([.5,1.]))
        metadata=dict(metadata,event=dict(initialization=True,quench_completed=True))
        return arrays,metadata
    def test_pending_only_initialization_is_honest_and_cap_precedes_next(self):
        store=pilot.PacketStore('raw-hop',2,2,1,10*1024**2);arrays,metadata=self.inputs();store.begin(arrays,metadata)
        self.assertFalse(store.can_begin());result=pilot.recover_completed_packets('raw-index.json')
        self.assertEqual(result['completed'],0);self.assertEqual(result['pending'],1)
        self.assertFalse(Path('final-current-best.npz').exists())
    def test_completed_pose_arrays_recover_exactly(self):
        store=pilot.PacketStore('raw-hop',2,2,2,10*1024**2);arrays,metadata=self.inputs();index=store.begin(arrays,metadata)
        arrays,metadata=self.completed(arrays,metadata);store.complete(index,arrays,metadata)
        result=pilot.recover_completed_packets('raw-index.json');self.assertEqual(result['completed_chain_quenches'],2)
        with np.load('final-current-best.npz')as z:np.testing.assert_array_equal(z['current_after'],arrays['current_before'])
        self.assertFalse(Path('raw-hop/packet-0000-input.npz').exists())
    def test_index_publication_failure_preserves_both_exact_packets(self):
        store=pilot.PacketStore('raw-hop',2,2,2,10*1024**2);arrays,metadata=self.inputs();index=store.begin(arrays,metadata)
        before=Path('raw-hop/packet-0000-input.npz').read_bytes();arrays,metadata=self.completed(arrays,metadata)
        with mock.patch.object(pilot,'atom_json',side_effect=RuntimeError('simulated publication interruption')):
            with self.assertRaises(RuntimeError):store.complete(index,arrays,metadata)
        self.assertEqual(Path('raw-hop/packet-0000-input.npz').read_bytes(),before)
        result=pilot.recover_completed_packets('raw-index.json')
        self.assertEqual(result['completed'],0);self.assertEqual(result['pending'],1)
        self.assertEqual(result['unindexed_packet_files'][0]['status'],'completed')


if __name__=='__main__':unittest.main()
