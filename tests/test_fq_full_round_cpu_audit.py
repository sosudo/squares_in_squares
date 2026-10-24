"""Replay already-completed native held controls; no optimization/certification."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from analyze_fq_full_round_cpu import audit_native_return


class HeldReturnAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        fixture=ROOT/'tests/fixtures/fq_full_round_held_native.zip'
        with zipfile.ZipFile(fixture)as archive:
            provenance=json.loads(archive.read('provenance.json'))
            self.assertEqual(set(archive.namelist()),set(provenance['files'])|{'provenance.json'})
            for name,evidence in provenance['files'].items():
                value=archive.read(name)
                self.assertEqual(hashlib.sha256(value).hexdigest(),evidence['sha256'])
                self.assertEqual(len(value),evidence['bytes'])
                target=self.root/name
                self.assertTrue(target.resolve().is_relative_to(self.root.resolve()))
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)

    def control(self,n=335):
        root=self.root
        path=next(p for p in (root/'records').glob('*.json')if len_key(json.loads(p.read_text())['key'])==n)
        record=json.loads(path.read_text());trial=root/'trials'/path.stem
        return record,str(trial)

    def test_all_three_exact_completed_held_controls(self):
        for n in (147,299,335):
            record,trial=self.control(n)
            result=audit_native_return(record,trial,Path,lambda name:json.loads(Path(name).read_text()))
            self.assertEqual(result['final_radius'],0.)
            self.assertLess(abs(result['actual_held_side']-result['input_side']),1e-10)

    def test_changed_radius_trace_and_input_binding_are_rejected(self):
        record,trial=self.control()
        trace=json.loads(Path(trial+'.radius-trace.json').read_text())
        trace['reported_radii'][-1]=.001
        with self.assertRaisesRegex(ValueError,'zero-radius'):
            audit_native_return(record,trial,Path,lambda _:trace)
        record['input_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash differs'):
            audit_native_return(record,trial,Path,lambda name:json.loads(Path(name).read_text()))

    def test_configured_radius_or_native_report_mismatch_is_rejected(self):
        record,trial=self.control();record=copy.deepcopy(record)
        record['command_options'][record['command_options'].index('--round-r0')+1]='.1'
        record['command'][record['command'].index('--round-r0')+1]='.1'
        with self.assertRaisesRegex(ValueError,'zero-radius'):
            audit_native_return(record,trial,Path,lambda name:json.loads(Path(name).read_text()))
        record,trial=self.control();record['fq']['round']['s_hold']+=.001
        with self.assertRaisesRegex(ValueError,'scalar report'):
            audit_native_return(record,trial,Path,lambda name:json.loads(Path(name).read_text()))


def len_key(key):
    w,h,d=map(int,key.split('_'));return w*h+d


if __name__=='__main__':unittest.main()
