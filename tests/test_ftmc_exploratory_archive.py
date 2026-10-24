"""Exploratory observers preserve results and bind bounded archives to inputs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from ftmc_exploratory_archive import ExploratoryArchive


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.prefix = Path(self.temporary.name)/'observations'
        self.source = np.array([[.5, .5, .2], [1.5, .5, 0.],
                                [.5, 1.5, 0.], [1.5, 1.5, 0.]])
        self.calls = []
        self.reference_calls = []
        self.outputs = {}

        def original(name):
            def invoke(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self.outputs[name]
            return invoke

        def reference_capacity(*args):
            self.reference_calls.append(args)
            return 4

        self.worker = SimpleNamespace(
            cp=SimpleNamespace(asnumpy=np.asarray),
            fingerprint=lambda q: hashlib.sha256(np.asarray(q).tobytes()).hexdigest()[:16],
            **{name: original(name) for name in ['mutations', 'explore', 'precise', 'refill_batch']})
        self.archive = ExploratoryArchive(self.worker,
            SimpleNamespace(reference_capacity=reference_capacity), self.prefix,
            cores_per_key=2, full_per_key=2, flush_seconds=3600)
        self.originals = {name: getattr(self.worker, name)
                          for name in ['mutations', 'explore', 'precise', 'refill_batch']}

    def context(self):
        self.outputs['mutations'] = ([self.source[:1].copy()], [.8], ['unchanged'])
        self.worker.mutations(self.source, 2, 2, 0, np.random.default_rng(3), 1, 2, [])

    def test_wrappers_preserve_exact_results_and_source_context(self):
        self.archive.install()
        self.context()
        self.assertIs(self.calls[-1][1][0], self.source)
        self.assertEqual(self.archive.context['source_geometry_sha256'],
            hashlib.sha256(np.asarray(self.source, dtype='<f8').tobytes()).hexdigest())
        source_copy = self.source.copy()
        self.source[0, 0] += .125
        np.testing.assert_array_equal(self.archive.context['source_pose'], source_copy)

        cores = np.array([[[.7, .8, .3]], [[.9, .8, .3]]])
        scores = np.array([[.1, .002], [.2, .004]])
        boxes = np.full((2, 2), 2.8)
        self.outputs['explore'] = (cores, scores)
        result = self.worker.explore(cores, boxes, steps=500)
        self.assertIs(result, self.outputs['explore'])
        self.assertIs(result[0], cores)
        self.assertIs(result[1], scores)
        np.testing.assert_array_equal(self.archive.core_outputs, scores)
        self.assertFalse(np.shares_memory(self.archive.core_outputs, scores))

        self.outputs['refill_batch'] = (np.zeros((4, 4, 3)), np.array([4, 3, 2, 2]))
        result = self.worker.refill_batch(cores, 2, 2, .8, 4, soft=.008)
        self.assertIs(result, self.outputs['refill_batch'])
        self.assertIs(self.calls[-1][1][0], cores)
        self.assertEqual(len(self.reference_calls), 1)
        np.testing.assert_array_equal(self.reference_calls[0][3], source_copy)
        for record in self.archive.core_records.values():
            self.assertEqual(record['source_geometry_sha256'], self.archive.geometry_sha(source_copy))
            self.assertEqual(record['status'], 'exploratory_unvalidated')
            self.assertEqual(record['mode'], 2)
            self.assertEqual(record['soft_overlap_tolerance'], .008)
        np.testing.assert_array_equal(cores, np.array([[[.7, .8, .3]], [[.9, .8, .3]]]))
        np.testing.assert_array_equal(scores, [[.1, .002], [.2, .004]])

    def test_core_samples_are_quality_ranked_bounded_and_reject_nonfinite_geometry(self):
        self.archive.install()
        self.context()
        for batch in range(4):
            cores = np.array([[[batch+i/10., .8, .3]] for i in range(5)])
            cores[0, 0, 0] = np.nan
            self.archive.core_outputs = np.array([[.1, .001], [.1, .002+batch*.001],
                                                  [.1, .003], [.1, .02], [np.nan, .001]])
            self.archive.observe_refill(cores, 2, 2, .8, 4, .008,
                                       np.array([[4, 4], [4, 3], [2, 2], [4, 4], [4, 4]]))
            self.assertLessEqual(len(self.archive.core_records), 2)
        self.assertEqual(len(self.archive.core_records), 2)
        self.assertTrue(all(r['reported_capacity'] == 4 for r in self.archive.core_records.values()))
        self.assertEqual(sorted(r['core_residual'] for r in self.archive.core_records.values()),
                         [.002, .003])
        self.assertTrue(all(np.isfinite(q).all() for q in self.archive.core_arrays.values()))

    def test_full_capture_is_bounded_unvalidated_and_copies_arrays(self):
        self.archive.install()
        self.context()
        poses = np.repeat(self.source[None], 6, axis=0)
        poses[:, :, 0] += np.arange(6)[:, None]/100.
        outcomes = np.array([[.1, .001], [.2, .002], [.3, .003],
                             [.4, .0031], [.1, np.nan], [.5, .0005]])
        boxes = np.array([[2.8, 2.7]]*6)
        self.outputs['precise'] = (poses, outcomes)
        result = self.worker.precise(poses, boxes, steps=1100)
        self.assertIs(result, self.outputs['precise'])
        self.assertEqual(len(self.archive.full_records), 2)
        self.assertEqual(self.archive.stats['full_rows_observed'], 6)
        self.assertEqual(self.archive.stats['near_feasible_full_rows'], 4)
        self.assertEqual(sorted(r['full_residual'] for r in self.archive.full_records.values()),
                         [.0005, .001])
        for key, record in self.archive.full_records.items():
            self.assertEqual(record['target_box'], [2.8, 2.7])
            self.assertEqual(record['status'], 'exploratory_unvalidated')
            self.assertEqual(record['source_key'], '2_2_0')
            self.assertEqual(record['geometry_sha256'],
                             self.archive.geometry_sha(self.archive.full_arrays[key]))
            self.assertFalse(np.shares_memory(poses, self.archive.full_arrays[key]))
        saved = {key: value.copy() for key, value in self.archive.full_arrays.items()}
        poses.fill(99.)
        for key, q in saved.items():
            np.testing.assert_array_equal(q, self.archive.full_arrays[key])

    def test_flush_hashes_match_exact_arrays_and_restore_keeps_other_hooks(self):
        self.archive.install()
        self.context()
        poses = self.source[None].copy()
        self.archive.observe_full(poses, np.array([[.01, .001]]), np.array([[2.8, 2.7]]))
        replacement = lambda *a, **kw: None
        self.worker.explore = replacement
        self.archive.restore()
        self.assertIs(self.worker.explore, replacement)
        for name in ['mutations', 'precise', 'refill_batch']:
            self.assertIs(getattr(self.worker, name), self.originals[name])
        report = json.loads(Path(str(self.prefix)+'.json').read_text())
        self.assertEqual(report['status'], 'exploratory_unvalidated')
        for suffix, key in [('_cores.npz', 'core_records'), ('_full.npz', 'full_records')]:
            path = Path(str(self.prefix)+suffix)
            self.assertEqual(report['archive_hashes'][suffix], hashlib.sha256(path.read_bytes()).hexdigest())
            with np.load(path, allow_pickle=False) as saved:
                self.assertEqual(set(saved.files), set(report[key]))
                for identity in saved.files:
                    self.assertEqual(report[key][identity]['geometry_sha256'],
                                     self.archive.geometry_sha(saved[identity]))
        self.assertFalse(list(self.prefix.parent.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
