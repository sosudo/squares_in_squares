import hashlib,json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_rectangular_persistent_search as s
from fq_torch_hop import physical_energy as square_energy
from prepare_wall_aspect_inputs import rectangular_control

class RectangularPolicy(unittest.TestCase):
    def test_oracle_and_distinct_walls(self):
        p=np.array([[.6,.6,.2],[1.4,.7,-.15],[2.2,1.5,.4],[3.1,1.3,0.],[.8,2.2,.7]],dtype=float)
        boxes=np.array([[3.4,2.6],[2.6,3.4]])
        q=torch.tensor(np.stack((p,p)),dtype=torch.float64)
        got=s.physical_energy(q,torch.tensor(boxes,dtype=torch.float64))
        for i,box in enumerate(boxes):
            expected=rectangular_control(p,*box)
            self.assertAlmostEqual(got['energy'][i].item(),expected['energy'],places=12)
        self.assertNotEqual(got['energy'][0].item(),got['energy'][1].item())
        equal=torch.tensor([[3.4,3.4]]*2,dtype=torch.float64)
        self.assertTrue(torch.allclose(s.physical_energy(q,equal)['energy'],square_energy(q,equal[:,0])['energy'],rtol=0,atol=1e-14))
        changed=q.clone();changed[:,-1]=changed[:,0]
        self.assertTrue(bool((s.physical_energy(changed,equal)['energy']>s.physical_energy(q,equal)['energy']).all()))

    def test_balanced_sources_cuts_and_independent_streams(self):
        c=dict(key='5_17_7',w=5,h=17,d=7,n=92,seed_keys=list('abcd'),reference_f_upper='.81')
        rows=s.design(c);self.assertEqual(len(rows),64)
        for seed in 'abcd':self.assertEqual(sum(r['source_key']==seed for r in rows),16)
        for cut in s.CUTS:self.assertEqual(sum(r['delta']==cut for r in rows),16)
        self.assertTrue(all(r['target_f']==.81-r['delta'] and r['width']==5+r['target_f']for r in rows))
        draws=[s.random_stream(s.SEED,7,i).normal(size=8).tobytes()for i in range(64)]
        self.assertEqual(len(set(draws)),64)
        hot,phase=s.temperatures([r['temperature']for r in rows],100.,3100.,2349.9)
        self.assertEqual(phase,'initial');self.assertEqual(set(hot),{.3,1.})
        cool,phase=s.temperatures(hot,100.,3100.,2350.)
        self.assertEqual(phase,'cool');self.assertTrue((cool==.03).all())

    def test_sampled_history_atomic_recovery_and_corruption(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)
            for name in ('family-config.json','chain-design.json'):(root/name).write_text('{}\n')
            store=s.SampledStore(root,s.digest(root/'family-config.json'),s.digest(root/'chain-design.json'))
            arrays=dict(current_after=np.zeros((64,92,3)),best_after=np.zeros((64,92,3)),boxes=np.ones((64,2))*10,
                next_energy=np.ones(64),best_energy_after=np.ones(64),proposal_input=np.ones((64,92,3)))
            for i in range(3):store.commit(arrays,dict(round=i,temperature_phase='initial',accepted=[False]*64))
            self.assertEqual(len(store.entries),1)
            # Simulate index loss: complete latest head carries all state and hashes.
            (root/'sampled-index.json').unlink();r=s.recover(root)
            self.assertEqual(r['status'],'recovered_head');self.assertEqual(r['state_origin']['round'],2)
            store.commit(arrays,dict(round=3,temperature_phase='cool'),force=True)
            r=s.recover(root);self.assertEqual(r['status'],'complete')
            self.assertEqual(r['state_origin']['round'],3)
            self.assertEqual(len((root/'scalar-events.jsonl').read_text().splitlines()),4)
            with np.load(root/'final-current-best.npz',allow_pickle=False)as z:self.assertTrue(np.array_equal(z['best_after'],arrays['best_after']))
            last=root/r['state_origin']['path'];raw=bytearray(last.read_bytes());raw[90]^=1;last.write_bytes(raw)
            with self.assertRaises(AssertionError):s.recover(root)

if __name__=='__main__':unittest.main()
