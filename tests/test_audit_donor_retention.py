from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from audit_donor_retention import include_baseline, parse_type
from extract_broad_active_frontier import geometry_sha


class BaselineCoverageTests(unittest.TestCase):
    def setUp(self):
        # Only inventory shape and type inference are under test here.
        # Geometric validity remains the separate strict certificate's job.
        self.pose = np.array([[0., 0., 0.], [1.5, 0., 0.],
                              [0., 1.5, 0.], [1.5, 1.5, 0.], [.75, .75, 0.]])

    def test_baseline_only_type_and_partner_geometry_are_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'baseline.csv'
            source.write_text('pinned fixture\n')
            geometries, types, raw, canonical = {}, {}, set(), set()
            include_baseline({5: self.pose}, source, geometries, types, raw, canonical)
        g = geometry_sha(self.pose)
        self.assertIn(g, raw)
        self.assertIn((g, '2_2_1'), types)
        self.assertIn(types[g, '2_2_1']['canonical_sha256'], canonical)
        np.testing.assert_array_equal(geometries[g]['p'], self.pose)
        self.assertEqual(types[g, '2_2_1']['source']['format'], 'csv')

    def test_explicit_archive_provenance_is_preserved(self):
        g = geometry_sha(self.pose)
        original = dict(parse_type('2_2_1', self.pose), source={'key': 'original'})
        types = {(g, '2_2_1'): original}
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'baseline.csv'
            source.write_text('pinned fixture\n')
            include_baseline({5: self.pose}, source, {}, types, set(), set())
        self.assertIs(types[g, '2_2_1'], original)
        self.assertEqual(types[g, '2_2_1']['source']['key'], 'original')


if __name__ == '__main__':
    unittest.main()
