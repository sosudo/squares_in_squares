import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from ftmc_sampling_cap import cap_weights
from ftmc_overflow_repair import minimum_fractional_side, select_records


class SamplingRepairReviewTests(unittest.TestCase):
    def test_sampling_cap_preserves_internal_ratios_and_input(self):
        original = np.array([100., 200., 1., 1.])
        result = cap_weights(original, ['control0', 'control1', 'active0', 'active1'],
                             {'control0', 'control1'}, cap=.1)
        self.assertAlmostEqual(result[:2].sum(), .1)
        self.assertAlmostEqual(result[1] / result[0], 2.)
        self.assertAlmostEqual(result[2], .45)
        self.assertAlmostEqual(result.sum(), 1.)
        np.testing.assert_array_equal(original, [100., 200., 1., 1.])
        small = cap_weights([.01, 1.], ['control0', 'active'], {'control0'}, cap=.1)
        np.testing.assert_allclose(small, np.array([.01, 1.])/1.01)

    def test_area_bound_and_diverse_core_selection(self):
        for w, h, count in [(3, 14, 47), (5, 6, 36), (10, 10, 103)]:
            f = minimum_fractional_side(w, h, count)
            self.assertAlmostEqual((w+f)*(h+f), count)
        self.assertEqual(minimum_fractional_side(5, 6, 20), 0.)
        def record(identity, key, priority, **changes):
            result = {'id': identity, 'source_key': key, 'w': 3, 'h': 4,
                      'requested_count': 14, 'reported_capacity': 16,
                      'loose_fractional_side': .9, 'core_residual': .001,
                      'potential_targets': [{'gain_at_loose_box': priority,
                          'gain_after_hypothetical_04_shrink': priority}]}
            result.update(changes)
            return result
        records = {r['id']: r for r in [
            record('a0', 'a', 10.), record('a1', 'a', 9.),
            record('b0', 'b', 1.), record('nonfinite_gate', 'c', 50., core_residual=.1),
            record('impossible_area', 'd', 60., loose_fractional_side=0.)]}
        self.assertEqual([r['id'] for r in select_records(records, 2)], ['a0', 'b0'])
        self.assertEqual([r['id'] for r in select_records(records, 4)], ['a0', 'b0', 'a1'])


if __name__ == '__main__':
    unittest.main()
