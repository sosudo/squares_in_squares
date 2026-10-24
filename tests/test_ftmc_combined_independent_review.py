"""Independent CPU checks of combined-worker control flow and crash recovery."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from ftmc_combined_policy import install_combined_policy, transform_worker
from ftmc_combined_export import read_certified_checkpoint, recover_certified_checkpoint
from ftmc_certified_archive import CertifiedArchive, ArchiveIntegrityError

SOURCE = ROOT/'vendor/lightning_ftmc/gpu_ftmc_refill.py'
METRIC = ROOT/'vendor/lightning_ftmc/research/official_metric.py'


def function_node(name):
    return next(x for x in ast.parse(SOURCE.read_text()).body
                if isinstance(x, ast.FunctionDef) and x.name == name)


def compile_public(name, namespace):
    exec(compile(ast.Module(body=[function_node(name)], type_ignores=[]),
                 str(SOURCE), 'exec'), namespace)
    return namespace[name]


def public_worker_source():
    return ast.get_source_segment(SOURCE.read_text(), function_node('worker'))


class CombinedReviewTests(unittest.TestCase):
    def test_single_pass_exact_matches_and_certificate_gate_order(self):
        tree, changes = transform_worker(public_worker_source())
        self.assertEqual(len(changes), 10)
        self.assertTrue(all(count == 1 for count in changes.values()))
        with self.assertRaisesRegex(ValueError, 'adaptation refused'):
            transform_worker(ast.unparse(tree))
        original_gate = next(x for x in ast.walk(function_node('worker'))
                             if isinstance(x, ast.If) and ast.unparse(x.test) == 'not certify(q)')
        changed_gate = next(x for x in ast.walk(tree)
                            if isinstance(x, ast.If) and ast.unparse(x.test) == 'not certify(q)')
        self.assertEqual(ast.dump(original_gate), ast.dump(changed_gate))
        admission_loop = next(x for x in ast.walk(tree) if isinstance(x, ast.For)
                              and any(isinstance(y, ast.If) and ast.unparse(y.test) == 'not certify(q)'
                                      for y in x.body))
        statements = [ast.unparse(x) for x in admission_loop.body]
        gate = next(i for i, x in enumerate(statements) if x.startswith('if not certify(q):'))
        keep = statements.index('_ftmc_keep(wins, key, signature, q, w, h)')
        self.assertLess(gate, keep)
        self.assertIn('continue', statements[gate])
        self.assertIn('ff = _ftmc_gentle_sides(f0, len(filled), R)', ast.unparse(tree))
        self.assertIn('p = bank[key]', ast.unparse(tree))
        self.assertIn('f0 = excess(p, w, h)', ast.unparse(tree))

    def test_live_globals_and_distinct_device_initial_banks_archive_only(self):
        class Clock:
            value = 0.
            def perf_counter(self):
                self.value += .2
                return self.value

        class CUDA:
            class Device:
                def __init__(self, device): pass
                def use(self): pass
            class Event: pass

        with tempfile.TemporaryDirectory() as directory:
            old = Path.cwd()
            os.chdir(directory)
            self.addCleanup(os.chdir, old)
            Path('artifacts').mkdir()
            Path('research').mkdir()
            Path('research/night_priorities.json').write_text('{"2_1_0": 1}')
            poses = [np.array([[.5,.5,0.],[1.5+f,.5,0.]]) for f in (.03,.1)]
            for device, q in enumerate(poses):
                np.savez(f'artifacts/device{device}_initial_bank.npz', **{'2_1_0': q})
            variant = poses[0].copy()
            variant[1,0] -= .02
            np.savez('artifacts/night_seed_variants.npz', **{'2_1_0__better_archive': variant})
            for device in (0,1):
                writes, checkpoints = [], []
                module = types.ModuleType('review_worker_'+str(device))
                namespace = module.__dict__
                namespace.update(np=np, math=math, json=json, Path=Path,
                    time=Clock(), cp=types.SimpleNamespace(cuda=CUDA),
                    refill_check=lambda: True, gpu_check=lambda: True, row_check=lambda: True,
                    atom_json=lambda *args: self.fail('stale copied globals'),
                    mutations=lambda *args: ([], [], []),
                    fingerprint=lambda q: hashlib.sha256(q.tobytes()).hexdigest())
                namespace['half'] = lambda a: .5*(np.abs(np.cos(a))+np.abs(np.sin(a)))
                for name in ('dimensions','excess'):
                    compile_public(name, namespace)
                compile_public('worker', namespace)
                original_namespace = module.worker.__globals__
                report = install_combined_policy(module,
                    types.SimpleNamespace(keep=lambda *args: None),
                    types.SimpleNamespace(allow_refill=lambda *args: False),
                    lambda bank, wins, path: checkpoints.append({k:q.copy() for k,q in bank.items()}))
                self.assertTrue(report['shared_live_globals'])
                self.assertIs(module.worker.__globals__, original_namespace)
                # Replacing a live module global after adaptation must be observed.
                module.atom_json = lambda *args: writes.append(args)
                with contextlib.redirect_stdout(io.StringIO()):
                    module.worker(device, seconds=1., replicas=64, seed=1)
                self.assertTrue(writes)
                self.assertTrue(checkpoints)
                for bank in checkpoints:
                    np.testing.assert_array_equal(bank['2_1_0'], poses[device])
            os.chdir(old)

    def test_interrupted_aggregate_recovers_only_complete_certified_pairs(self):
        spec = importlib.util.spec_from_file_location('official_metric', METRIC)
        metric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric)
        certify = compile_public('certify', {'Path': Path})
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict(sys.modules, {'official_metric': metric}):
            prefix = Path(directory)/'certified'
            keeper = CertifiedArchive(prefix, metric_path=METRIC)
            for i, separation in enumerate((1.02,1.04)):
                q = np.array([[.5,.5,0.],[.5+separation,.5,0.]])
                self.assertTrue(certify(q), 'actual unchanged raw+pandas gate')
                keeper.keep({}, '2_1_0', str(i), q, 2, 1)
                keeper.finalflush()
                if i == 0:
                    stale_index = Path(str(prefix)+'.json').read_bytes()
            # Simulate kill after aggregate replacement but before index publication.
            Path(str(prefix)+'.json').write_bytes(stale_index)
            with self.assertRaisesRegex(ValueError, 'Aggregate archive bytes changed'):
                read_certified_checkpoint(prefix, METRIC)
            # Orphan arrays are never evidence of certification.
            (keeper.snapshot_dir/('f'*64+'.npy')).write_bytes(b'orphan')
            poses, records, binding = recover_certified_checkpoint(prefix, METRIC)
            self.assertEqual(len(poses), 2)
            self.assertEqual(len(records), 2)
            self.assertTrue(binding['recovered_from_immutable_snapshots'])
            self.assertFalse(binding['independent_metric_rerun'])
            record = next(iter(records.values()))
            (keeper.snapshot_dir/(record['geometry_sha256']+'.npy')).write_bytes(b'corrupt')
            with self.assertRaises(ArchiveIntegrityError):
                recover_certified_checkpoint(prefix, METRIC)

    def test_stale_consistent_aggregate_cannot_hide_new_immutable_snapshot(self):
        spec = importlib.util.spec_from_file_location('official_metric', METRIC)
        metric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric)
        certify = compile_public('certify', {'Path': Path})
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict(sys.modules, {'official_metric': metric}):
            prefix = Path(directory)/'certified'
            keeper = CertifiedArchive(prefix, metric_path=METRIC)
            for i, separation in enumerate((1.02,1.04)):
                q = np.array([[.5,.5,0.],[.5+separation,.5,0.]])
                self.assertTrue(certify(q))
                keeper.keep({}, '2_1_0', str(i), q, 2, 1)
                if i == 0:
                    keeper.finalflush()
            # Old NPZ and old index agree, but a later immutable pair is newer.
            with self.assertRaisesRegex(ValueError, 'newer than the aggregate'):
                read_certified_checkpoint(prefix, METRIC)
            poses, records, binding = recover_certified_checkpoint(prefix, METRIC)
            self.assertEqual(len(poses), 2)
            self.assertEqual(len(records), 2)
            self.assertTrue(binding['recovered_from_immutable_snapshots'])


if __name__ == '__main__':
    unittest.main()
