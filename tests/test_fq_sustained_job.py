"""Exact fixture and policy failures, without optimizer or GPU work."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_fq_sustained_job as builder


class SustainedPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder=Path(self.temporary.name)/'inputs'
        shutil.copytree(ROOT/'artifacts/fq-sustained-inputs-v1',self.folder)
        for path in self.folder.rglob('*'):
            if path.is_file():path.chmod(0o600)

    def test_exact_actual_24_array_input_and_evidence(self):
        config,proof,files=builder.validate_inputs(self.folder)
        self.assertEqual(len(proof['arrays']),24)
        self.assertEqual(len(config['cases']),12)
        self.assertEqual(config['baseline']['sha256'],builder.BASELINE_SHA)
        self.assertTrue(all('provenance/sustained-evidence/'+name in files for name in proof['evidence']))

    def test_changed_input_archive_rejected(self):
        path=self.folder/'sustained-inputs.npz';data=path.read_bytes()
        path.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaisesRegex(ValueError,'input binding'):builder.validate_inputs(self.folder)

    def test_unapproved_precision_and_duration_rejected(self):
        path=self.folder/'sustained-config.json';original=json.loads(path.read_bytes())
        for name,value in [('search_seconds',361),('batch_size',128),('temperature',1.)]:
            changed=dict(original);changed[name]=value;path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'policy'):builder.validate_inputs(self.folder)
        changed=dict(original);changed['batch_decision']=dict(original['batch_decision'],production_precision='float32')
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'occupancy'):builder.validate_inputs(self.folder)

    def test_changed_bound_evidence_rejected(self):
        proof=json.loads((self.folder/'sustained-input-proof.json').read_bytes())
        path=self.folder/'evidence'/next(iter(proof['evidence']))
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'evidence changed'):builder.validate_inputs(self.folder)


if __name__=='__main__':unittest.main()
