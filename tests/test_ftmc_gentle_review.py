"""Independent review of the frozen gentle-target AST adaptation."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('gentle_review_module', ROOT/'experiments/ftmc_gentle_targets.py')
gentle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gentle)


def observe_targets(ff):
    return ff


def original_fixture_worker(f0, filled_fs, filled):
    R = 16
    ff = np.repeat(np.array(filled_fs), R)
    return observe_targets(ff)


ORIGINAL_FIXTURE = original_fixture_worker


class GentleReviewTests(unittest.TestCase):
    def test_shape_sign_and_per_refill_replication(self):
        for count in (1, 2, 7, 12):
            actual = gentle.gentle_fractional_sides(.87, count, 16)
            self.assertEqual(actual.shape, (16*count,))
            for row in actual.reshape(count, 16):
                np.testing.assert_allclose(row[:8], [.872, .8705, .87, .86999, .86995, .8698, .8695, .869])
                np.testing.assert_array_equal(row[:8], row[8:])
        with self.assertRaises(ValueError):
            gentle.gentle_fractional_sides(.87, 2, 8)

    def test_disabled_identity_and_unmodified_control_targets(self):
        worker = SimpleNamespace(worker=ORIGINAL_FIXTURE)
        audit = gentle.install_gentle_targets(worker, enabled=False)
        self.assertIs(worker.worker, ORIGINAL_FIXTURE)
        self.assertEqual(audit['modification'], 'none')
        np.testing.assert_array_equal(worker.worker(.9, [.8, .7], [1, 2]), np.repeat([.8, .7], 16))

    def test_live_incumbent_and_later_observer_hooks(self):
        worker = SimpleNamespace(worker=ORIGINAL_FIXTURE)
        audit = gentle.install_gentle_targets(worker, enabled=True)
        self.assertTrue(audit['enabled'])
        self.assertIs(worker.worker.__globals__, ORIGINAL_FIXTURE.__globals__)
        # Filled mutation targets are deliberately unrelated: actual live f0
        # must determine both calls, including a changed incumbent on call two.
        first = worker.worker(.9, [.4, .3], [1, 2])
        second = worker.worker(.81, [.4, .3], [1, 2])
        np.testing.assert_allclose(first-second, .09)
        global observe_targets
        previous = observe_targets
        observed = []
        try:
            def later_hook(ff):
                observed.append(ff.copy())
                return ff
            observe_targets = later_hook
            result = worker.worker(.82, [.1], [1])
            self.assertEqual(len(observed), 1)
            np.testing.assert_array_equal(observed[0], result)
        finally:
            observe_targets = previous


if __name__ == '__main__':
    unittest.main()
