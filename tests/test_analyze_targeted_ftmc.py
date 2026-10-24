import hashlib
import io
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from analyze_targeted_ftmc import PUBLIC_METRIC_SHA256, verify_record


def fixture():
    q = np.array([[.5, .5, 0.], [1.5, .5, 0.]], dtype='<f8')
    payload = io.BytesIO()
    np.save(payload, q, allow_pickle=False)
    digest = hashlib.sha256(payload.getvalue()).hexdigest()
    name = '1_1_1__'+digest
    record = dict(key='1_1_1', geometry_sha256=digest, npy_sha256=digest,
        snapshot=digest+'.npy', shape=[2, 3], dtype='<f8', w=1, h=1, bloat=1.,
        official_metric_sha256=PUBLIC_METRIC_SHA256, status='certified_geometry',
        certification_contract='unchanged_public_certify_exact_geometry',
        raw=True, roundtrip=True, official_raw_and_pandas=True)
    return name, q, record


class AnalyzeTargetedTests(unittest.TestCase):
    def test_exact_certificate_binds_array_without_geometry_rerun(self):
        name, q, record = fixture()
        self.assertEqual(verify_record(name, q, record), hashlib.sha256(q.tobytes()).hexdigest())


    def test_changed_coordinates_fail_even_with_unchanged_type_and_dimensions(self):
        name, q, record = fixture()
        q[0, 0] += 1e-8
        with self.assertRaisesRegex(ValueError, 'binding failed'):
            verify_record(name, q, record)


    def test_missing_roundtrip_admission_fails_closed(self):
        name, q, record = fixture()
        record['roundtrip'] = False
        with self.assertRaisesRegex(ValueError, 'binding failed'):
            verify_record(name, q, record)
