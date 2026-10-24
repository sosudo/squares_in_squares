"""Independent persistent-chain controls; CPU only, no optimizer."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
try:
    import torch
except ImportError:
    torch = None
if torch is not None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
    import fq_cold_transfer_pilot as pilot


@unittest.skipIf(torch is None, 'Optional Torch CPU protocol control')
class ColdTransferProtocolTests(unittest.TestCase):
    def test_actual_cases_have_independent_reproducible_streams_and_no_reset(self):
        histories = []
        for n in (803, 861):
            rows = pilot.design(n, '29.8', 'original')
            self.assertEqual(len(rows), 32)
            self.assertEqual({r['arm'] for r in rows}, {'cold'})
            self.assertEqual({r['temperature'] for r in rows}, {.3})
            self.assertEqual([sum(r['delta']==d for r in rows) for d in (.002,.008)], [16,16])
            self.assertEqual([sum(r['amplitude']==a for r in rows) for a in (1.,1.5)], [16,16])
            seed = pilot.SEED+n
            values = np.array([r.random(20) for r in pilot.random_streams(seed, 3)])
            self.assertEqual(len({v.tobytes() for v in values}), 32)
            self.assertTrue(np.array_equal(values, np.array([r.random(20) for r in pilot.random_streams(seed,3)])))
            self.assertFalse(np.array_equal(values, np.array([r.random(20) for r in pilot.random_streams(seed,4)])))
            histories.append(values)
            u = pilot.acceptance_uniforms(seed,3)
            pilot.random_streams(seed,3)[0].random(10000)
            self.assertTrue(np.array_equal(u, pilot.acceptance_uniforms(seed,3)))
            self.assertFalse(np.array_equal(u[:16],u[16:]))
            for rounds in (0,1,16,32,100):
                for cooling in (False,True):
                    for initial in (False,True):
                        for completed in (False,True):
                            value=pilot.reset_mask(rows,rounds,cooling,initial,completed,-1)
                            self.assertFalse(value['mask'].any())
                            self.assertFalse(value['periodic'] or value['cooling'])
        self.assertFalse(np.array_equal(*histories))

    def test_actual_generated_loop_is_persistent_through_decision_time_cooling(self):
        # Actual controller with a synthetic energy and identity quench: protocol
        # coverage only, not numerical/physical CUDA evidence.
        clock=[0.]; calls=[0]
        class TorchCpu:
            cuda=SimpleNamespace(is_available=lambda:True,get_device_name=lambda *a:'test T4')
            def __getattr__(self,name):return getattr(torch,name)
            @staticmethod
            def device(*a):return torch.device('cpu')
            @staticmethod
            def set_num_threads(*a):pass
            @staticmethod
            def set_num_interop_threads(*a):pass
        def energy(q,sides):
            return dict(energy=q[:,0,0].clone(),per_square=torch.ones(q.shape[:2],dtype=q.dtype))
        def mutate(q,per_square,rng,amplitude):
            q=q.copy();q[0,0]+=1
            return q,dict(operator='synthetic_translation',changed_count=1,selected_count=1)
        def quench(q,sides):
            q=q.clone();clock[0]+=10.;calls[0]+=1
            if calls[0]==1:q[:,0,0]=9.+torch.arange(32,dtype=torch.float64)/100
            return q,dict(synthetic_identity_quench=True)
        with tempfile.TemporaryDirectory() as tmp:
            old=Path.cwd();os.chdir(tmp)
            try:
                pose=np.array([[10.,.5,0.],[1.5,.5,0.]])
                np.savez('pilot-inputs.npz',source=pose)
                fixture=dict(n=2,inputs_sha256=pilot.hop.digest('pilot-inputs.npz'),exploratory_sources=['source'],
                    arrays={'source':dict(shape=[2,3],dtype=pose.dtype.str,sha256=hashlib.sha256(pose.tobytes()).hexdigest())})
                for name,value in [('pilot-config.json',fixture),('case-config.json',dict(n=2,reference_side=20.,source_key='source')),
                    ('hop-config.json',dict(search_seconds=600,seed=1,max_packets=100,max_bytes=64*1024**2)),
                    ('preflight.json',dict(passed=True,backend='restart_fused_fp64'))]:
                    Path(name).write_text(json.dumps(value))
                namespace=dict(vars(pilot.hop))
                namespace.update(torch=TorchCpu(),time=SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda dt:clock.__setitem__(0,clock[0]+dt)),
                    physical_energy=energy,mutate=mutate,fused_quench=quench,PacketStore=pilot.prior.RestartPacketStore,
                    chain_design=pilot.chain_design,reset_mask=pilot.reset_mask,random_streams=pilot.random_streams,
                    temperature_schedule=pilot.prior.temperature_schedule,acceptance_uniforms=lambda *a:np.full(32,np.exp(-100.)))
                exec(compile(pilot.generated_search_source(),'<actual cold loop CPU control>','exec'),namespace)
                with redirect_stdout(io.StringIO()):namespace['search_main'](600.)
                entries=json.loads(Path('raw-index.json').read_text())['packets'];previous=None;phases=[]
                for entry in entries:
                    with np.load(entry['path'],allow_pickle=False) as z:
                        event=json.loads(z['metadata_json'].tobytes())['event']
                        for key in ('before_reset','after_reset'):
                            self.assertFalse(np.array(event[key]['mask']).any())
                            self.assertFalse(event[key]['periodic'] or event[key]['cooling'])
                        self.assertTrue(np.array_equal(z['current_before'],z['current_before_reset']))
                        if previous is not None:self.assertTrue(np.array_equal(previous,z['current_before']))
                        mh=np.where(z['accepted'][:,None,None],z['proposal_quenched'],z['current_before'])
                        self.assertTrue(np.array_equal(z['current_after'],mh))
                        self.assertTrue(np.array_equal(z['next_energy'],z['current_after'][:,0,0]))
                        previous=z['current_after'].copy();phases.append(event['temperature_phase'])
                        want=.3 if event['decision_time_monotonic']<450 else .03
                        self.assertTrue(np.allclose(event['temperature'],want,rtol=0,atol=1e-16))
                self.assertEqual(len(entries),60)
                self.assertEqual(phases[:44],['hot']*44)
                self.assertEqual(phases[44:],['cool']*16)
                self.assertTrue(json.loads(Path('pilot-summary.json').read_text())['cooling_entered'])
            finally:os.chdir(old)


if __name__=='__main__':unittest.main()
