"""Preserve fully gated stages despite search rejection and later interruption."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_remote_cpu_search as remote


class RemoteRetentionTests(unittest.TestCase):
    def fake_native(self,command,**kwargs):
        output=Path(command[command.index('--out')+1])
        output.write_text('5 3\n.5 .5 0\n1.5 .5 0\n2.5 .5 0\n.5 1.5 0\n1.5 1.5 0\n')
        return subprocess.CompletedProcess(command,0,json.dumps({'s':3,'viol':0}), '')

    def call(self,root,cap=5):
        trials=root/'trials';trials.mkdir();binary=root/'fq';binary.write_bytes(b'control-binary')
        side=2+math.sqrt(.5)
        pose=np.array([[.5,.5,0],[side-.5,.5,0],[.5,side-.5,0],[side-.5,side-.5,0],[side/2,side/2,math.pi/4]])
        remote.fq.MODES['test_remote']=[]
        return remote.strict_trial(('2_2_1',pose,'test_remote',str(binary),str(trials),1,cap,time.monotonic()+10))

    def test_certified_wider_pose_retained_before_search_rejection(self):
        with tempfile.TemporaryDirectory()as folder,mock.patch.object(remote,'grouped_run',self.fake_native):
            root=Path(folder);record,donor=self.call(root)
            self.assertEqual(record['status'],'certified_outside_search_band');self.assertIsNone(donor)
            self.assertTrue(record['certificate']['valid'])
            result=remote.collect(root)
            self.assertEqual(result['certified_variants'],1)
            self.assertEqual(result['complete_stage_records'],1)

    def test_orphan_archive_ignored_and_corrupt_complete_pair_rejected(self):
        with tempfile.TemporaryDirectory()as folder,mock.patch.object(remote,'grouped_run',self.fake_native):
            root=Path(folder);self.call(root)
            (root/'strict-stages/orphan.npz').write_bytes(b'interrupted write')
            self.assertEqual(remote.collect(root)['ignored_orphan_archives'],1)
            proof=next((root/'strict-stages').glob('*.json'));record=json.loads(proof.read_text())
            record['geometry_sha256']='0'*64;proof.chmod(0o600);proof.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'geometry differs'):remote.collect(root)

    def test_certificate_time_included_in_stage_deadline(self):
        with tempfile.TemporaryDirectory()as folder,mock.patch.object(remote,'grouped_run',self.fake_native):
            with mock.patch.object(remote,'full_certificate',side_effect=lambda p:time.sleep(4)):
                started=time.monotonic();record,donor=self.call(Path(folder),cap=1.1)
                self.assertEqual(record['status'],'whole-stage-timeout');self.assertIsNone(donor)
                self.assertLess(time.monotonic()-started,2)
                self.assertFalse((Path(folder)/'strict-stages').exists())


if __name__=='__main__':unittest.main()
