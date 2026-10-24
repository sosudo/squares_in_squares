"""Native optimizer failures must not discard other certified trial results."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import fq_active_pilot as fq


class TrialFailureTests(unittest.TestCase):
    def fake_binary(self, directory, report='{}', coordinates=None):
        path = Path(directory)/'fake-fq'
        path.write_text('#!'+sys.executable+'\n'
            'import pathlib, shutil, sys\n'
            "src=sys.argv[sys.argv.index('--in')+1]\n"
            "dst=sys.argv[sys.argv.index('--out')+1]\n"+
            ('shutil.copyfile(src,dst)\n' if coordinates is None else
             'pathlib.Path(dst).write_text('+repr(coordinates)+')\n')+
            'print('+repr(report)+')\n')
        path.chmod(0o700)
        return path

    def run_trial(self, directory, binary):
        pose = np.array([[.5,.5,0.]])
        return fq.trial(('1_1_0', pose, 'polish', str(binary), str(directory),
                         19, 5., time.monotonic()+10.))

    def test_malformed_or_missing_report_rejected_without_crash(self):
        for report in ['{"energy":-nan}', '']:
            with self.subTest(report=report), tempfile.TemporaryDirectory() as tmp:
                record, donor = self.run_trial(tmp, self.fake_binary(tmp, report))
                self.assertEqual(record['status'], 'invalid-optimizer-report')
                self.assertIsNone(donor)
                self.assertTrue((Path(tmp)/'1_1_0-polish-19.log').is_file())

    def test_nonfinite_coordinates_rejected_without_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            record, donor = self.run_trial(tmp, self.fake_binary(tmp, coordinates='1 1\nnan .5 0\n'))
            self.assertEqual(record['status'], 'invalid-optimizer-coordinates')
            self.assertIsNone(donor)

    def test_failed_worker_does_not_discard_other_certified_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp)
            binary=self.fake_binary(tmp)
            pose=np.array([[.5,.5,0.]])
            bank=tmp/'bank.npz'
            # First key promises two squares but contains only one; its worker
            # raises before executing the native solver. The next trial is valid.
            np.savez_compressed(bank, **{'1_1_1':pose, '1_1_0':pose})
            priorities=tmp/'priorities.json'
            priorities.write_text(json.dumps({'1_1_1':2,'1_1_0':1}))
            out=tmp/'results'
            run=subprocess.run([sys.executable,str(ROOT/'experiments/fq_active_pilot.py'),
                '--binary',str(binary),'--bank',str(bank),'--priorities',str(priorities),
                '--out',str(out),'--workers','1','--keys','2','--seconds','20',
                '--trial-seconds','5','--modes','polish'],capture_output=True,text=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stderr)
            records=json.loads((out/'results.json').read_text())
            self.assertEqual({r['status'] for r in records},{'worker-error','certified'})
            good=next(r for r in records if r['status']=='certified')
            self.assertTrue(good['certificate']['valid'])
            with np.load(out/'donors.npz',allow_pickle=False) as data:
                self.assertEqual(len(data.files),1)
                self.assertTrue(data.files[0].startswith('1_1_0__fq_'))


if __name__=='__main__':
    unittest.main()
