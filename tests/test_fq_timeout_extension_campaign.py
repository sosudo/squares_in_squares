"""Reuse the proven fault controls with frozen original timeout identities."""
import hashlib
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
sys.path.insert(0, str(ROOT/'scripts'))
import test_fq_current_rigid_campaign as base
import fq_timeout_extension_campaign as subject


class TimeoutExtensionControls(base.WorkerRetentionTests):
    def test_certificate_exception_preserves_native_and_raw(self):
        def failure(_):
            raise ValueError('mock gate error')
        record, q, files, calls = self.run_worker(failure)
        self.assertEqual(record['status'], 'saved_return_certificate_error')
        self.assertIsNone(q)
        self.assertIn('raw-returned/0001-n2.npz', files)
        self.assertIn('trials/n2-rigid-0001.out', files)
        self.assertGreater(calls[0]['timeout'], 29.)
        self.assertLessEqual(calls[0]['timeout'], 30.)
        self.assertEqual(calls[0]['env']['FQ_TR'], '1')
        self.assertEqual(calls[0]['env']['FQ_LPT'], '1')

    def run_worker(self, *args, **kwargs):
        original = subject.worker

        def with_frozen_original(job):
            n, pose, canonical, entry, index, binary, root, deadline = job
            text, _ = subject.encode(pose, int(n**.5), int(n**.5))
            entry = dict(entry, original_job=999, original_seed=123456,
                original_input_sha256=hashlib.sha256(text.encode()).hexdigest())
            record, q = original((n, pose, canonical, entry, index, binary, root, deadline))
            self.assertEqual(record['original_job'], 999)
            self.assertEqual(record['original_seed'], 123456)
            self.assertEqual(record['command'][record['command'].index('--seed')+1], '123456')
            self.assertEqual(record['command'][-1], '--v')
            return record, q

        with patch.object(base, 'subject', subject), patch.object(subject, 'worker', with_frozen_original):
            return super().run_worker(*args, **kwargs)


if __name__ == '__main__':
    unittest.main()
