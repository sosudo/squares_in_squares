import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np


spec = importlib.util.spec_from_file_location(
    'overflow_capture', Path(__file__).parents[1] / 'experiments/ftmc_overflow_capture.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OverflowReviewTests(unittest.TestCase):
    def fixture(self):
        cores = np.array([[[.5+i*.03, .5, .3], [1.5, 1.5, .3]] for i in range(3)])
        out = np.array([[0., .005], [0., .02], [0., .03]])
        counts = np.array([5, 7, 4, 5, 6, 6])
        packed = np.zeros((6, 5, 3))
        mutation_result = ([cores[0]], [.2], [{'example': True}])
        quench_result = (cores, out)
        refill_result = (packed, counts)
        worker = SimpleNamespace(
            mutations=lambda *a, **k: mutation_result,
            explore=lambda *a, **k: quench_result,
            refill_batch=lambda *a, **k: refill_result)
        return worker, cores, counts, mutation_result, quench_result, refill_result

    def test_family_mapping_and_exact_return_identity(self):
        worker, cores, counts, mutations, quenched, refilled = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            handle = module.install_capture(worker, Path(directory)/'cores', {'6': 2.9, '7': 2.99})
            self.assertIs(worker.mutations(cores[0], 2, 2, 1, None, 3, 4, []), mutations)
            self.assertIs(worker.explore(cores, None, steps=500), quenched)
            self.assertIs(worker.refill_batch(cores, 2, 2, .2, 5), refilled)
            self.assertEqual(len(handle.records), 2)
            records = sorted(handle.records.values(), key=lambda x: x['core_residual'])
            self.assertEqual(records[0]['overflow_families'], [1])
            self.assertEqual(records[0]['row_family_capacities'], [5, 7])
            self.assertEqual(records[1]['overflow_families'], [0, 1])
            np.testing.assert_array_equal(handle.cores[records[0]['id']], cores[0])
            self.assertEqual(handle.stats['overflow_cores_residual_at_most_01'], 1)
            self.assertEqual(handle.stats['capacity_at_least_requested'], 5)
            handle.restore()

    def test_no_overflow_and_bounded_exploratory_archive(self):
        worker, cores, counts, *_ = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)/'cores'
            handle = module.install_capture(worker, prefix, {'6': 2.9}, max_records=1, per_key_limit=1)
            worker.mutations(cores[0], 2, 2, 1, None, 3, 0, [])
            worker.explore(cores, None, steps=500)
            handle.observe(cores, 2, 2, .2, 5, .008, np.full(6, 5))
            self.assertEqual(len(handle.records), 0)
            handle.observe(cores, 2, 2, .2, 5, .008, counts)
            self.assertEqual(len(handle.records), 1)
            self.assertEqual(handle.stats['evicted'], 1)
            handle.flush()
            report = json.loads(prefix.with_suffix('.json').read_text())
            self.assertEqual(report['status'], 'exploratory_unvalidated')
            rec = next(iter(report['records'].values()))
            self.assertEqual(rec['status'], 'exploratory_unvalidated')
            # Capacity exceeds even the area bound here; the observer must not
            # turn soft-core exploratory capacity into a feasibility claim.
            self.assertGreater(rec['reported_capacity'], (2+.2)**2)
            self.assertNotIn('officially_valid', rec)


if __name__ == '__main__':
    unittest.main()
