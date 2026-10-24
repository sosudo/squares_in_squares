"""Regression checks for lost FTMC wins and durable exact-geometry certificates."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import ftmc_certified_archive as retention

METRIC_PATH = ROOT/'vendor/lightning_ftmc/research/official_metric.py'
SOURCE_PATH = ROOT/'vendor/lightning_ftmc/gpu_ftmc_refill.py'


def public_function(name):
    """Exercise the actual public CPU function without importing CUDA modules."""
    tree = ast.parse(SOURCE_PATH.read_text())
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {'np': np, 'hashlib': hashlib, 'Path': Path}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE_PATH), 'exec'), namespace)
    return namespace[name]


def pose(separation=1.1):
    return np.array([[.5, .5, 0.], [.5+separation, .5, 0.]])


class CertifiedArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.prefix = Path(self.directory.name)/'worker0_certified'

    def archive(self, **kwargs):
        return retention.CertifiedArchive(self.prefix, metric_path=METRIC_PATH, **kwargs)

    def index(self):
        return json.loads(Path(str(self.prefix)+'.json').read_text())

    def test_worse_same_fingerprint_cannot_overwrite_strict_best(self):
        keeper = self.archive()
        wins = {}
        best, worse = pose(1.03), pose(1.2)
        self.assertTrue(keeper.keep(wins, '1_1_1', 'coarse', best, 1, 1))
        self.assertFalse(keeper.keep(wins, '1_1_1', 'coarse', worse, 1, 1))
        np.testing.assert_array_equal(wins['1_1_1__coarse'], best)
        self.assertEqual(keeper.best_by_key['1_1_1']['bloat'], retention._bloat(best, 1, 1))
        keeper.finalflush()
        with np.load(str(self.prefix)+'.npz') as all_poses:
            self.assertEqual(len(all_poses.files), 2)
        with np.load(str(self.prefix)+'_best.npz') as best_poses:
            np.testing.assert_array_equal(best_poses['1_1_1'], best)
        self.assertEqual(len(self.index()['records']), 2)

    def test_exact_copy_survives_input_and_source_wins_mutation(self):
        keeper = self.archive()
        q = pose()
        expected = q.copy()
        wins = {}
        keeper.keep(wins, '1_1_1', 's', q, 1, 1)
        q[:, :2] = -99
        wins['1_1_1__s'][:, :2] = 99
        best_info = keeper.best_by_key
        best_info['1_1_1']['shape'][0] = 999
        keeper.finalflush()
        record = next(iter(self.index()['records'].values()))
        self.assertEqual(record['shape'], [2, 3])
        snapshot = keeper.snapshot_dir/record['snapshot']
        np.testing.assert_array_equal(np.load(snapshot), expected)
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), record['geometry_sha256'])
        self.assertEqual(record['official_metric_sha256'], retention.PUBLIC_METRIC_SHA256)
        self.assertEqual(record['status'], 'certified_geometry')
        self.assertIs(record['raw'], True)
        self.assertIs(record['roundtrip'], True)

    def test_forced_content_address_collision_refuses_replacement(self):
        keeper = self.archive()
        with mock.patch.object(retention, '_snapshot_digest', return_value='0'*64):
            keeper.keep({}, '1_1_1', 's', pose(), 1, 1)
            path = keeper.snapshot_dir/('0'*64+'.npy')
            original = path.read_bytes()
            with self.assertRaises(retention.ArchiveIntegrityError):
                keeper.keep({}, '1_1_1', 's', pose(1.2), 1, 1)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(len(list(keeper.snapshot_dir.glob('*.json'))), 1)

    def test_existing_corruption_is_detected_on_keep_and_restart(self):
        keeper = self.archive()
        keeper.keep({}, '1_1_1', 's', pose(), 1, 1)
        snapshot = next(keeper.snapshot_dir.glob('*.npy'))
        snapshot.write_bytes(b'corrupt')
        with self.assertRaises(retention.ArchiveIntegrityError):
            keeper.keep({}, '1_1_1', 's', pose(), 1, 1)
        with self.assertRaises(retention.ArchiveIntegrityError):
            self.archive()

    def test_recovery_uses_immutable_records_before_any_aggregate_flush(self):
        keeper = self.archive()
        keeper.keep({}, '1_1_1', 's', pose(1.2), 1, 1)
        keeper.keep({}, '1_1_1', 's', pose(1.03), 1, 1)
        keeper.keep({}, '1_1_1', 'other', pose(1.15), 1, 1)
        self.assertFalse(Path(str(self.prefix)+'.npz').exists())
        restored = self.archive()
        restored.finalflush()
        self.assertEqual(len(self.index()['records']), 3)
        with np.load(str(self.prefix)+'_best.npz') as best:
            np.testing.assert_array_equal(best['1_1_1'], pose(1.03))
        self.assertEqual(len(restored.best_by_fingerprint), 2)

    def test_public_raw_and_roundtrip_certification_of_unseen_bank(self):
        spec = importlib.util.spec_from_file_location('official_metric', METRIC_PATH)
        metric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric)
        original_certify = public_function('certify')
        certificate_calls = mock.Mock(wraps=original_certify)
        keeper = self.archive(certify=certificate_calls)
        bank = {'1_1_1': pose(1.03)}
        with mock.patch.dict(sys.modules, {'official_metric': metric}):
            keeper.finalflush(bank)
            keeper.finalflush(bank)
        self.assertEqual(certificate_calls.call_count, 1)
        with np.load(str(self.prefix)+'_incumbents.npz') as current:
            np.testing.assert_array_equal(current['1_1_1'], bank['1_1_1'])
        self.assertEqual(len(self.index()['incumbents']), 1)

    def test_unknown_or_failed_bank_is_never_labelled_certified(self):
        keeper = self.archive()
        with self.assertRaisesRegex(ValueError, 'requires original certify'):
            keeper.finalflush({'1_1_1': pose()})
        self.assertEqual(list(keeper.snapshot_dir.glob('*.json')), [])
        keeper = self.archive(certify=lambda q: False)
        with self.assertRaisesRegex(ValueError, 'failed original certification'):
            keeper.finalflush({'1_1_1': pose()})
        self.assertEqual(list(keeper.snapshot_dir.glob('*.json')), [])

    def test_restart_keeps_certified_current_bank_without_recertifying(self):
        keeper = self.archive(certify=lambda q: True)
        keeper.finalflush({'1_1_1': pose(1.03)})
        restored = self.archive()
        restored.finalflush()
        with np.load(str(self.prefix)+'_incumbents.npz') as current:
            np.testing.assert_array_equal(current['1_1_1'], pose(1.03))

    def test_throttle_avoids_zip_work_and_finalflush_saves_live_bank(self):
        callback = mock.Mock(return_value=True)
        keeper = self.archive(certify=callback)
        bank = {'1_1_1': pose(1.2)}
        with mock.patch.object(retention.time, 'monotonic', return_value=10.), \
                mock.patch.object(retention, '_atomic_npz', wraps=retention._atomic_npz) as save:
            self.assertTrue(keeper.flush(bank))
            self.assertEqual(save.call_count, 3)
            bank['1_1_1'] = pose(1.03)
            self.assertFalse(keeper.flush(bank))
            self.assertEqual(save.call_count, 3)
            self.assertTrue(keeper.finalflush())
            self.assertEqual(save.call_count, 6)
        self.assertEqual(callback.call_count, 2)
        with np.load(str(self.prefix)+'_incumbents.npz') as current:
            np.testing.assert_array_equal(current['1_1_1'], bank['1_1_1'])
        with np.load(str(self.prefix)+'_best.npz') as current:
            np.testing.assert_array_equal(current['1_1_1'], bank['1_1_1'])

    def test_better_existing_source_win_and_exact_dtype_are_preserved(self):
        keeper = self.archive()
        original = pose(1.03).astype('<f4')
        wins = {'1_1_1__s': original.copy()}
        keeper.keep(wins, '1_1_1', 's', pose(1.2), 1, 1)
        np.testing.assert_array_equal(wins['1_1_1__s'], original)
        keeper.keep(wins, '1_1_1', 's', original, 1, 1)
        keeper.finalflush()
        with np.load(str(self.prefix)+'_best.npz') as current:
            self.assertEqual(current['1_1_1'].dtype, original.dtype)
            self.assertEqual(current['1_1_1'].tobytes(), original.tobytes())

    def test_pinned_metric_and_bounds_are_checked(self):
        wrong = Path(self.directory.name)/'modified_metric.py'
        wrong.write_bytes(METRIC_PATH.read_bytes()+b'\n')
        with self.assertRaises(retention.ArchiveIntegrityError):
            retention.CertifiedArchive(self.prefix, metric_path=wrong)
        keeper = self.archive()
        with self.assertRaisesRegex(ValueError, 'bounds disagree'):
            keeper.keep({}, '1_1_1', 's', pose(), 2, 1)
        with self.assertRaisesRegex(ValueError, 'bounds disagree'):
            keeper.keep({}, '1_1_0', 's', pose(), 1, 1)


class SearchArchiveTests(unittest.TestCase):
    def test_same_signature_improves_pose_and_worse_cannot_displace_it(self):
        archive = {'1_1_1': [pose(1.2)]}
        q = pose(1.03)
        retention.update_search_archive(archive, '1_1_1', q, 1, 1, 'same',
                                        fingerprint=lambda p: 'same')
        q[:] = -20
        np.testing.assert_array_equal(archive['1_1_1'][0], pose(1.03))
        retention.update_search_archive(archive, '1_1_1', pose(1.15), 1, 1, 'same',
                                        fingerprint=lambda p: 'same')
        self.assertEqual(len(archive['1_1_1']), 1)
        np.testing.assert_array_equal(archive['1_1_1'][0], pose(1.03))

    def test_twelve_unique_signatures_include_the_lowest_bloat(self):
        def fingerprint(p):
            return str(p[0, 0])
        archive = {}
        for value in range(20):
            q = pose(1.01+value*.01)
            q[:, 0] += value
            retention.update_search_archive(archive, '1_1_1', q, 1, 1, fingerprint(q),
                                            fingerprint=fingerprint)
        self.assertEqual(len(archive['1_1_1']), 12)
        self.assertEqual(len({fingerprint(q) for q in archive['1_1_1']}), 12)
        self.assertEqual([q[0, 0] for q in archive['1_1_1']], [i+.5 for i in range(12)])

    def test_cpu_fingerprint_exactly_matches_public_worker(self):
        public_fingerprint = public_function('fingerprint')
        rng = np.random.default_rng(351)
        for n in (1, 2, 73, 103):
            q = rng.normal(size=(n, 3))
            self.assertEqual(retention._fingerprint(q), public_fingerprint(q))
        self.assertEqual(retention._fingerprint(pose()), public_fingerprint(pose()))


if __name__ == '__main__':
    unittest.main()
