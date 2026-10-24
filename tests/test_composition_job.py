"""Exercise the actual job supervisor's timeout without allocating a GPU."""
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
from build_composition_job import RUNTIME


class CompositionJobTests(unittest.TestCase):
    def test_hung_child_is_killed_and_marked_unsuccessful(self):
        body = b'import time\ntime.sleep(30)\n'
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('pipeline/driver.py', body)
        config = {'embedded_sha256': {'pipeline/driver.py': hashlib.sha256(body).hexdigest()},
                  'embedded_gadgets': [], 'runtime_gadgets': [], 'wall_seconds': .05}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'supervisor.py'
            source = ('CONFIG = '+repr(config)+'\nPAYLOAD = '+
                      repr(base64.b64encode(archive.getvalue()).decode())+'\n'+RUNTIME)
            # This test runs in an ordinary local directory, not a Kaggle session.
            source = source.replace("working=Path('/kaggle/working')if Path('/kaggle/working').is_dir()else Path.cwd()",
                                    'working=Path.cwd()')
            path.write_text(source)
            result = subprocess.run([sys.executable, str(path)], cwd=directory,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            summary = json.loads((Path(directory)/'composition_job_summary.json').read_text())
            self.assertTrue(summary['timed_out'])
            self.assertFalse(summary['success'])
            self.assertLess(summary['wall_seconds'], 3)


if __name__ == '__main__':
    unittest.main()
