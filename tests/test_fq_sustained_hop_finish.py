"""Frozen derivation and actual forked seed/retention controls; no optimizer."""
import hashlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_sustained_hop_finish as subject


class SustainedFinisherTests(unittest.TestCase):
    def test_only_terminal_seed_expression_changes(self):
        old=inspect.getsource(subject.terminal._finish_slot)
        expected=old.replace("str(9710000+DELTAS.index(slot['delta']))",'str(9710000)',1)
        self.assertEqual(hashlib.sha256(expected.encode()).hexdigest(),subject.DERIVATION['seeded_terminal_function_sha256'])
        self.assertEqual(subject.DERIVATION['terminal_function_changes'],1)
        self.assertEqual(subject._file_sha(subject.cold.__file__),subject.COLD_SHA)
        self.assertEqual(subject._file_sha(subject.terminal.__file__),subject.TERMINAL_SHA)

    def make_case(self,root,B):
        n=341;reference=20.;design=[];poses=np.zeros((B,n,3),dtype=np.float64)
        poses[:,:,0]=1.;poses[:,:,1]=1.
        for i in range(B):
            cut=subject.CUTS[i//(B//2)];poses[i,0,0]+=.05*i
            design.append(dict(chain=i,n=n,arm='cold',delta=cut,side=reference-cut,source_key='reference341'))
        arrays=dict(current_after=poses.copy(),best_after=poses,sides=np.array([r['side']for r in design]),
            next_energy=np.ones(B),best_energy_after=np.ones(B))
        metadata=dict(status='completed',design=design,array_sha256={k:hashlib.sha256(v.tobytes()).hexdigest()for k,v in arrays.items()})
        (root/'raw-hop').mkdir();packet=root/'raw-hop/packet-0000.npz'
        with packet.open('wb')as stream:np.savez(stream,**arrays,metadata_json=np.frombuffer(json.dumps(metadata).encode(),dtype=np.uint8))
        with(root/'final-current-best.npz').open('wb')as stream:np.savez(stream,**arrays)
        (root/'chain-design.json').write_text(json.dumps(design))
        (root/'raw-index.json').write_text(json.dumps(dict(packets=[dict(path='raw-hop/packet-0000.npz',status='completed',bytes=packet.stat().st_size,sha256=subject._file_sha(packet))])))
        binary=root/'fq';binary.write_bytes(b'mocked native binary; never executed')
        return dict(n=n,reference_side='20',source_key='reference341',binary_path=str(binary),batch_size=B,baseline_sha256='mock-only'),binary

    def test_actual_fork_uses_same_seed_for_both_cuts_and_retains_worse(self):
        proxy=subject._DERIVED['original'];seeded=proxy._finish_slot
        certificate=dict(valid=True,shared_official_gate=dict(raw_side='21',roundtrip_side='21'),
            ordinary_pandas_official_side='21',independent_raw=dict(side_upper='21'),independent_roundtrip=dict(side_upper='21'))

        class FakeNative:
            def __init__(self,command,stdout,stderr):
                self.command=command;self.stdout=stdout;self.returncode=0
                inp=Path(command[command.index('--in')+1]);out=Path(command[command.index('--out')+1]);out.write_bytes(inp.read_bytes())
                stderr.write(b'mock only; no optimizer\n')
            def wait(self,timeout):
                self.stdout.write(json.dumps(dict(timeout=timeout,seed=self.command[self.command.index('--seed')+1])).encode());self.stdout.flush();return 0
            def poll(self):return self.returncode
            def kill(self):self.returncode=-9

        for B in (32,64,128):
            with self.subTest(batch=B),tempfile.TemporaryDirectory()as directory:
                root=Path(directory);config,binary=self.make_case(root,B)
                fake_pose=np.zeros((341,3));fake_pose[:,0]=np.arange(341)+.5;fake_pose[:,1]=.5
                with patch.object(proxy,'BINARY_SHA',subject._file_sha(binary)), \
                     patch.object(subject.terminal.subprocess,'Popen',FakeNative), \
                     patch.object(seeded.__globals__['fq'],'decode',lambda *_:fake_pose.copy()), \
                     patch.dict(seeded.__globals__,full_certificate=lambda _:certificate):
                    result=subject.finish_case(root,config,time.monotonic()+200)
                self.assertEqual(result['certified'],4)
                self.assertEqual(result['strict_improvements'],0)
                self.assertEqual({r['delta']for r in result['slots']},{.0005,.002})
                for record in result['slots']:
                    command=record['command']
                    self.assertEqual(command[command.index('--seed')+1],'9710000')
                    self.assertEqual(command[command.index('--seed')+2:],subject.terminal.OPTIONS)
                    self.assertEqual(record['native_seconds_cap'],60.)
                    self.assertEqual(record['certificate_seconds_cap'],8.)
                    self.assertEqual(record['side_gain'],'-1')
                    self.assertTrue(Path(record['certified_archive']).exists())
                manifest=json.loads((root/'finish/manifest.json').read_text())
                self.assertEqual(manifest['batch_size'],B)
                self.assertEqual(manifest['derivation'],subject.DERIVATION)

    def test_explicit_batch_and_design_agreement_required(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);config,_=self.make_case(root,32)
            for value in (None,16,64):
                config['batch_size']=value
                with self.assertRaises(ValueError):subject.finish_case(root,config,time.monotonic()+1)
            self.assertFalse((root/'finish').exists())


if __name__=='__main__':unittest.main()
