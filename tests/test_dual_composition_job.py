"""Exercise the real two-worker supervisor without allocating CUDA devices."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_dual_composition_job import RUNTIME


class DualCompositionJobTests(unittest.TestCase):
    def test_timeout_retains_successful_profile_and_reports_partial_coverage(self):
        driver = b'''import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--root');a=p.parse_args()
r=Path(a.root);c=json.loads(Path(a.config).read_text())
if c['bins']==16:time.sleep(30)
(r/'composition_preflight.json').write_text(json.dumps({'passed':True}))
(r/'composition_candidates.json').write_text('{}')
(r/'composition_candidates.report.json').write_text(json.dumps({'groups':{'all_certified_donors':{'details':{'adaptive':{'oriented_done':7,'oriented_planned':9}}}}}))
(r/'inputs').mkdir();(r/'inputs/baseline.csv').write_text('fixture')
'''
        payload = {'pipeline/driver.py': driver,
                   'pipeline/compose_gadgets.py': b'def read_baseline(path):return {}\ndef side(p):return 0\n'}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as stream:
            for name, data in payload.items():
                stream.writestr(name, data)
        config = {'embedded_sha256': {k: hashlib.sha256(v).hexdigest() for k,v in payload.items()},
                  'wall_seconds': 1.5, 'baseline_sha256': 'fixture',
                  'profiles': [{'name':'done','device':0,'bins':32,'degrees':[30,45,60]},
                               {'name':'hung','device':1,'bins':16,'degrees':[30,45,60]}]}
        source = 'CONFIG = '+repr(config)+'\nPAYLOAD = '+repr(base64.b64encode(archive.getvalue()).decode())+'\n'+RUNTIME
        source = source.replace('import cupy as cp',
            'from types import SimpleNamespace\ncp=SimpleNamespace(cuda=SimpleNamespace(runtime=SimpleNamespace(getDeviceCount=lambda:2)))')
        source = source.replace("working=Path('/kaggle/working') if Path('/kaggle/working').is_dir() else Path.cwd()", 'working=Path.cwd()')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'supervisor.py';path.write_text(source)
            result = subprocess.run([sys.executable,str(path)],cwd=directory,capture_output=True,text=True,timeout=6)
            self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
            summary=json.loads((Path(directory)/'dual_composition_summary.json').read_text())
            self.assertFalse(summary['success'])
            self.assertTrue(summary['profiles']['hung']['timed_out'])
            self.assertTrue(summary['profiles']['done']['success'])
            self.assertFalse(summary['profiles']['done']['coverage']['all_certified_donors']['complete'])
            self.assertTrue((Path(directory)/'done/composition_candidates.json').is_file())
            self.assertLess(summary['seconds'], 4)


if __name__=='__main__':unittest.main()
