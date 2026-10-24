"""Fault controls for native-output preservation and separate certificate limits."""
import json
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
import fq_current_rigid_campaign as subject


class WorkerRetentionTests(unittest.TestCase):
    def run_worker(self, certificate, *, native_timeout=False, malformed=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('trials', 'raw-returned', 'decoded', 'retained'):
                (root/name).mkdir()
            q = np.array([[.5, .5, 0.], [1.5, .5, 0.]])
            native_calls = []

            def native(command, **kwargs):
                native_calls.append(kwargs)
                dst = Path(command[command.index('--out')+1])
                dst.write_text('2 2\n.5 .5 0\n' + ('' if malformed else '1.5 .5 0\n'))
                if native_timeout:
                    raise subprocess.TimeoutExpired(command, kwargs['timeout'],
                        output=b'{"native":true}\n', stderr=b'partial native log')
                return subprocess.CompletedProcess(command, 0, b'{"native":true}\n', b'native log')

            def gate(pose):
                # The metric may fail or time out, but exact returned bytes must
                # already be independently recoverable before it is called.
                raw = root/'raw-returned/0001-n2.npz'
                self.assertTrue(raw.exists())
                rec = json.loads((root/'trials/n2-rigid-0001.record.json').read_text())
                self.assertEqual(rec['status'], 'saved_native_return_before_certificate')
                self.assertEqual(rec['raw_returned']['sha256'], subject.digest(raw))
                self.assertTrue((root/'trials/n2-rigid-0001.parent.npz').exists())
                self.assertTrue((root/'trials/n2-rigid-0001.log').exists())
                return certificate(pose)

            entry = dict(category='current_source_rigid_untried')
            with patch.object(subject.subprocess, 'run', native), \
                 patch.object(subject, 'decode', lambda *_: q.copy()), \
                 patch.object(subject, 'full_certificate', gate), \
                 patch.object(subject, 'CERTIFICATE_SECONDS', .03):
                record, returned = subject.worker((2, q, '2', entry, 1,
                    'unused-binary', str(root), time.monotonic()+30))
            files = {str(path.relative_to(root)): path.read_bytes()
                     for path in root.rglob('*') if path.is_file()}
            return record, returned, files, native_calls

    def test_certificate_exception_preserves_native_and_raw(self):
        def failure(_):
            raise ValueError('mock gate error')
        record, q, files, native = self.run_worker(failure)
        self.assertEqual(record['status'], 'saved_return_certificate_error')
        self.assertIsNone(q)
        self.assertIn('raw-returned/0001-n2.npz', files)
        self.assertIn('trials/n2-rigid-0001.out', files)
        self.assertEqual(native[0]['timeout'], subject.NATIVE_SECONDS)

    def test_alarm_escapes_metrics_exception_handler(self):
        def swallowing_metric(_):
            try:
                time.sleep(.2)
            except Exception:
                self.fail('Certificate alarm was swallowed by metric Exception handling')
            self.fail('Certificate alarm did not fire')
        record, q, files, _ = self.run_worker(swallowing_metric)
        self.assertEqual(record['status'], 'saved_return_certificate_timeout')
        self.assertIsNone(q)
        self.assertLess(record['certificate_seconds'], .15)
        self.assertIn('raw-returned/0001-n2.npz', files)

    def test_valid_worse_pose_is_retained_and_native_timeout_logs_survive(self):
        record, q, files, _ = self.run_worker(
            lambda _: dict(valid=True, independent_raw=dict(side_upper='3')),
            native_timeout=True)
        self.assertEqual(record['native_status'], 'timeout')
        self.assertEqual(record['status'], 'certified')
        self.assertEqual(record['side_gain'], '-1')
        self.assertIsNotNone(q)
        self.assertIn(b'partial native log', files['trials/n2-rigid-0001.log'])
        self.assertEqual(len([p for p in files if p.startswith('retained/')]), 2)

    def test_malformed_native_count_cannot_reach_gate(self):
        record, q, files, _ = self.run_worker(
            lambda _: self.fail('Malformed output reached the certificate'), malformed=True)
        self.assertEqual(record['status'], 'malformed_native_output')
        self.assertIsNone(q)
        self.assertFalse(any(p.startswith('raw-returned/') for p in files))
        self.assertIn('trials/n2-rigid-0001.out', files)


if __name__ == '__main__':
    unittest.main()
