"""Actual worker batch preparation must preserve audited source coverage."""
import contextlib
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from full_structural_gpu_moves import geometry_sha
from full_structural_gpu_schedule import BalancedSeedScheduler
from full_structural_gpu_v2_worker import prepare_batch, source_inventory
from compose_gadgets import side


def fixture():
    references, variants, order = {}, {}, {}
    for n, count in ((299, 32), (335, 33), (147, 5)):
        i = np.arange(n, dtype=float)
        p = np.column_stack((i % 17, i // 17 + .03 * np.sin(i), np.zeros(n)))
        p[:12, 2] = .25
        references[n] = p
        # Deliberately nonlexicographic: the worker must use this frozen order.
        order[n] = [f'alternative_{n}_{j:03d}' for j in reversed(range(count))]
        for j, name in enumerate(order[n]):
            q = p.copy()
            q[:, 0] += (j + 1) * .0001
            variants[name] = q
    config = dict(replicas=32, references_sha256='a' * 64,
                  variants_sha256='b' * 64,
                  source_order={str(n): names for n, names in order.items()},
                  reference_sides={str(n): 30. for n in order})
    return config, references, variants, order


@contextlib.contextmanager
def in_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class WorkerScheduleIntegrationTests(unittest.TestCase):
    def test_actual_worker_pairs_exact_inputs_and_preserves_all32_sources(self):
        config, refs, variants, order = fixture()
        schedules = [BalancedSeedScheduler(order), BalancedSeedScheduler(order)]
        rngs = [np.random.default_rng(991), np.random.default_rng(991)]
        all_rows = []
        for batch, n in enumerate((299, 335, 299, 147, 335, 299)):
            left, right = [prepare_batch(config, refs, variants, schedule, rng, n, batch)
                           for schedule, rng in zip(schedules, rngs)]
            inputs, rows, loose, targets = left
            self.assertEqual(rows, right[1])
            for a, b in zip((inputs, loose, targets), (right[0], right[2], right[3])):
                self.assertEqual(a.dtype, b.dtype)
                self.assertEqual(a.shape, b.shape)
                self.assertEqual(a.tobytes(), b.tobytes())
            for index, row in enumerate(rows):
                source = refs[n] if row['is_reference'] else variants[row['source_id']]
                self.assertEqual(row['replica'], index)
                self.assertEqual(row['batch'], batch)
                self.assertEqual(row['mutation']['source_geometry_sha256'], geometry_sha(source))
                self.assertEqual(row['mutation']['input_geometry_sha256'], geometry_sha(inputs[index]))
                self.assertEqual(row['mutation']['mode'], row['mode'])
                self.assertEqual(row['mutation']['amplitude'], row['amplitude'])
                self.assertEqual(row['mutation']['full_count'], n)
                self.assertTrue(row['mutation']['upright_coordinates_preserved'])
                self.assertEqual(row['source_archive_sha256'],
                                 config['references_sha256'] if row['is_reference'] else config['variants_sha256'])
                self.assertEqual(loose[index, 0], side(source) + row['loose_slack'])
                self.assertEqual(targets[index, 0], 30. - row['target_depth'])
            all_rows.extend(rows)
        rows299 = [r for r in all_rows if r['n'] == 299]
        alternatives = [r['source_id'] for r in rows299 if not r['is_reference']]
        self.assertEqual(alternatives, (order[299] * 3)[:72])
        self.assertEqual(len(set(alternatives)), 32)
        self.assertEqual([r['family_start_ordinal'] for r in rows299], list(range(96)))
        self.assertEqual(schedules[0].snapshot(), schedules[1].snapshot())

    def test_source_inventory_rejects_omissions_duplicates_and_changed_archives(self):
        config, refs, variants, order = fixture()
        with tempfile.TemporaryDirectory() as temporary, in_directory(temporary):
            np.savez('prepared_references.npz', **{str(n): p for n, p in refs.items()})
            np.savez('prepared_variants.npz', **variants)
            for kind in ('references', 'variants'):
                config[kind + '_sha256'] = hashlib.sha256(Path('prepared_' + kind + '.npz').read_bytes()).hexdigest()
            actual_refs, actual_variants, actual_order = source_inventory(config)
            self.assertEqual(actual_order, order)
            self.assertEqual(set(actual_variants), set(variants))
            for n, p in refs.items():
                self.assertEqual(actual_refs[n].tobytes(), p.tobytes())
            omitted = copy.deepcopy(config)
            omitted['source_order']['299'].pop()
            with self.assertRaises((AssertionError, ValueError)):
                source_inventory(omitted)
            duplicated = copy.deepcopy(config)
            duplicated['source_order']['299'].append(duplicated['source_order']['299'][0])
            with self.assertRaises((AssertionError, ValueError)):
                source_inventory(duplicated)
            changed = dict(variants)
            changed[next(iter(changed))] = changed[next(iter(changed))].copy()
            changed[next(iter(changed))][0, 0] += .001
            np.savez('prepared_variants.npz', **changed)
            with self.assertRaises((AssertionError, ValueError)):
                source_inventory(config)


if __name__ == '__main__':
    unittest.main()
