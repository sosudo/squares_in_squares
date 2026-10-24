"""Actual fork/initializer propagation control, with a mocked native binary."""
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
sys.path.insert(0, str(ROOT/'scripts'))
import fq_selective_polish_campaign as subject


class ProcessConfigurationTests(unittest.TestCase):
    def test_actual_fork_initializer_reaches_unchanged_worker(self):
        q = np.array([[.5, .5, 0.], [1.5, .5, 0.]])
        original_flags = subject.base.RIGID_FLAGS.copy()

        def fake_native(command, **kwargs):
            target = Path(command[command.index('--out')+1])
            target.write_text('2 2\n.5 .5 0\n1.5 .5 0\n')
            body = dict(timeout=kwargs['timeout'], FQ_TR=os.environ.get('FQ_TR'),
                FQ_LPT=os.environ.get('FQ_LPT'), caps=[subject.base.NATIVE_SECONDS, subject.base.CERTIFICATE_SECONDS])
            return subprocess.CompletedProcess(command, 0, (json.dumps(body)+'\n').encode(), b'control-only native stub')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('trials', 'raw-returned', 'decoded', 'retained'):
                (root/name).mkdir()
            job = (2, q, '2', dict(category='fresh_feasible_no_alm_tail_followup'),
                1, 'unused-native', str(root), time.monotonic()+60)
            with patch.object(subject.base.subprocess, 'run', fake_native), \
                 patch.object(subject.base, 'decode', lambda *_: q.copy()), \
                 patch.object(subject.base, 'full_certificate', lambda _: dict(valid=True, independent_raw=dict(side_upper='2'))):
                with ProcessPoolExecutor(max_workers=2, mp_context=mp.get_context('fork'),
                        initializer=subject.configure_worker) as pool:
                    record, result = pool.submit(subject.base.worker, job).result(timeout=10)
            self.assertEqual(record['status'], 'certified')
            self.assertIsNotNone(result)
            command = record['command']
            self.assertEqual(command[command.index('--no-alm'):], subject.FLAGS)
            self.assertEqual(record['fq']['caps'], [40., 8.])
            self.assertEqual(record['fq']['timeout'], 40.)
            self.assertEqual((record['fq']['FQ_TR'], record['fq']['FQ_LPT']), ('1', '1'))
            self.assertEqual(subject.base.RIGID_FLAGS, original_flags)


if __name__ == '__main__':
    unittest.main()
