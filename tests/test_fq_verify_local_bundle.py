"""Saved certification audits reject changed geometry, traces and certificates."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_verify_local_bundle as audit


class LocalBundleAuditTests(unittest.TestCase):
    def test_changed_geometry_is_rejected(self):
        pose = np.array([[.5, .5, 0.]])
        sha = audit.geometry_sha(pose)
        self.assertEqual(audit.check_pose('1_1_0', pose, sha), 0.)
        altered = pose.copy(); altered[0, 2] = .03
        with self.assertRaisesRegex(ValueError, 'geometry hash'):
            audit.check_pose('1_1_0', altered, sha)

    def test_changed_log_or_invalid_certificate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); (run/'trials').mkdir()
            log = run/'trials/1_1_0-example-123.log'
            text = 'soft eps 0.15 hold 1\nsoft eps 0.0000 hold 1\n'
            log.write_text(text)
            item = {
                'key': '1_1_0', 'mode': 'example', 'seed': 123, 'geometry_sha256': 'bound-geometry',
                'certificate': {'valid': True, 'raw_reason': 'ok', 'roundtrip_reason': 'ok',
                                'metric_sha256': audit.fq.OFFICIAL_SHA256},
                'rigid_return_trace': {'valid': True, 'expected_steps': 2,
                    'reported_aspect_epsilons': [.15, 0.],
                    'log_sha256': hashlib.sha256(text.encode()).hexdigest()},
            }
            audit.check_saved_proof(run, item, 'bound-geometry')
            log.write_text(text.replace('0.0000', '0.0001'))
            with self.assertRaisesRegex(ValueError, 'log hash'):
                audit.check_saved_proof(run, item, 'bound-geometry')
            log.write_text(text)
            item['certificate']['valid'] = False
            with self.assertRaisesRegex(ValueError, 'certificate'):
                audit.check_saved_proof(run, item, 'bound-geometry')


if __name__ == '__main__':
    unittest.main()
