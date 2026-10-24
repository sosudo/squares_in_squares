"""Cold BEST selection and exception retention without native execution."""
from concurrent.futures import Future
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_cold_hop_finish as finish


class ColdFinishTests(unittest.TestCase):
    def fixture(self,n=803):
        rows=[dict(chain=i,arm='cold',delta=(.002,.008)[i//16],n=n,
                   source_key='original',side=29.-(.002,.008)[i//16]) for i in range(32)]
        q=np.zeros((32,n,3));q[:,:,0]=1.;q[:,:,1]=1.
        for i in range(32):q[i,0,0]+=.01*i
        return rows,q,np.array([r['side'] for r in rows])

    def test_histogram_is_unit_permutation_and_d4_invariant(self):
        p=np.array([[1.,2.,.17],[2.,5.,-.31],[8.,4.,.65],[4.,6.,0.]])
        first=finish.histogram_orbit(p,10.)
        for swap in (False,True):
            for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
                q=p.copy();xy=q[:,:2]-5;angle=q[:,2]
                if swap:xy=xy[:,::-1];angle=np.pi/2-angle
                q[:,:2]=xy*np.array([sx,sy])+5;q[:,2]=angle*sx*sy
                self.assertEqual(finish.histogram_distance(first,finish.histogram_orbit(q[::-1],10.)),0.)

    def test_selection_respects_energy_band_and_distinct_exact_bytes(self):
        rows,q,sides=self.fixture(3);energy=np.full(32,100.)
        energy[:5]=[1.,1.1,3.,9.,1.2];q[1]=q[0]
        q[2,:,0]+=10;q[3,:,1]+=15
        energy[16:19]=[2.,20.,30.]
        slots=finish.select_slots(rows,q,energy,sides)
        self.assertEqual([s['chain'] for s in slots],[0,2,16,17])
        self.assertEqual(slots[1]['exact_duplicate_alternatives_excluded'],[1])
        self.assertEqual(slots[1]['near_best_energy_threshold'],4.)
        self.assertNotIn(3,slots[1]['eligible_alternatives'])
        self.assertTrue(slots[3]['fallback_next_lowest_energy'])
        q[:16]=q[0]
        self.assertEqual(finish.select_slots(rows,q,energy,sides)[1]['status'],'no_exactly_distinct_alternative')

    def test_histogram_equality_does_not_discard_distinct_geometry(self):
        rows,q,sides=self.fixture(3);energy=np.arange(32,dtype=float)+1
        slots=finish.select_slots(rows,q,energy,sides)
        self.assertIsNotNone(slots[1]['chain'])
        self.assertFalse(slots[1]['positive_histogram_diversity'])

    def write_case(self,root,bad_hash=False):
        rows,q,sides=self.fixture()
        values=dict(current_after=q+1,best_after=q,sides=sides,next_energy=np.full(32,99.),best_energy_after=np.arange(32,dtype=float)+1)
        hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in values.items()}
        if bad_hash:hashes['best_after']='wrong'
        metadata=dict(status='completed',design=rows,array_sha256=hashes)
        np.savez(root/'packet.npz',**values,metadata_json=np.frombuffer(json.dumps(metadata).encode(),dtype=np.uint8))
        np.savez(root/'final-current-best.npz',**values)
        (root/'chain-design.json').write_text(json.dumps(rows))
        (root/'raw-index.json').write_text(json.dumps(dict(packets=[dict(path='packet.npz',status='completed',sha256=finish._sha(root/'packet.npz'))])))
        binary=root/'fq';binary.write_bytes(b'not executable test fixture')
        return dict(n=803,source_key='original',reference_side='29.0',binary_path=str(binary),baseline_sha256='frozen'),q,binary

    def test_failed_future_preserves_all_selected_states_and_continues_fixed_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case,q,binary=self.write_case(root);submitted=[]
            class FakePool:
                def __init__(self,**kw):self.kw=kw
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def submit(self,fn,payload):
                    out,slot,pose,*_=payload
                    self_test.assertEqual(len(list(Path(out).glob('*-selected.npz'))),4)
                    self_test.assertTrue(np.array_equal(pose,q[slot['chain']]))
                    submitted.append(slot['slot']);f=Future()
                    if slot['slot']==0:f.set_exception(OSError('mock no native'))
                    else:f.set_result((dict(slot,status='mock_no_optimizer'),None))
                    return f
            self_test=self
            with patch.object(finish.original,'BINARY_SHA',finish._sha(binary)),patch.object(finish,'ProcessPoolExecutor',FakePool):
                result=finish.finish_case(root,case,time.monotonic()+20)
            self.assertEqual(submitted,[0,1,2,3]);self.assertEqual(result['certified'],0)
            self.assertEqual(result['slots'][0]['status'],'finish_error')
            self.assertIn(str(root/'finish/slot-00-selected.npz'),result['slots'][0]['preserved_artifacts'])
            self.assertEqual(len(list((root/'finish').glob('*-selected.npz'))),4)

    def test_tampered_commit_rejected_before_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case,_,binary=self.write_case(root,bad_hash=True)
            with patch.object(finish.original,'BINARY_SHA',finish._sha(binary)),patch.object(finish,'ProcessPoolExecutor') as pool:
                with self.assertRaisesRegex(ValueError,'committed_array_hash_mismatch'):
                    finish.finish_case(root,case,time.monotonic()+20)
                pool.assert_not_called()


if __name__=='__main__':unittest.main()
