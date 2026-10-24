"""Cache identity, source-relative eligibility and real-time debt accounting."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from ftmc_refill_budget import GeneralRefillBudget


class Clock:
    def __init__(self):
        self.now = 0.
    def __call__(self):
        return self.now
    def advance(self, seconds):
        self.now += seconds


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.gpu_calls = []
        self.source = np.array([[i % 10+.5, i//10+.5, .2 if i < 20 else 0.] for i in range(100)])
        def rows(core, w, h, loose, total, soft):
            self.gpu_calls.append((core.copy(), w, h, loose, total, soft))
            return None, np.array([90, 92], dtype=np.int32)
        self.policy = GeneralRefillBudget(SimpleNamespace(cp=SimpleNamespace(asnumpy=np.asarray)),
                                         rows, clock=self.clock)

    def test_reference_cache_is_independent_of_permission_and_binds_geometry(self):
        p = self.policy
        self.assertFalse(p.budget_available())
        self.assertEqual(p.reference_capacity(10, 10, 0, self.source, .8), 92)
        self.assertEqual(p.reference_capacity(10, 10, 0, self.source.copy(), .8), 92)
        self.assertEqual(len(self.gpu_calls), 1)
        self.assertEqual(len(self.gpu_calls[0][0][0]), 20)
        changed = self.source.copy(); changed[0, 0] = np.nextafter(changed[0, 0], np.inf)
        p.reference_capacity(10, 10, 0, changed, .8)
        p.reference_capacity(10, 10, 0, changed, .81)
        p.reference_capacity(5, 20, 0, changed, .81)
        self.assertEqual(len(self.gpu_calls), 4)
        self.assertEqual(p.stats['reference_cache_hits'], 1)
        self.assertEqual(p.stats['reference_deficit_by_key']['10_10_0'], 8)
        self.assertEqual(p.stats['refill_seconds'], 0.)

    def test_measured_deficit_accepts_feasible_source_that_fixed_gate_would_skip(self):
        self.clock.advance(10.)
        p = self.policy
        self.assertFalse(p.allow_refill(89, 10, 10, 0, self.source, .8))
        self.assertTrue(p.allow_refill(90, 10, 10, 0, self.source, .8))
        self.assertTrue(p.allow_refill(92, 10, 10, 0, self.source, .8))
        self.assertLess(92, 100-4)
        self.assertEqual(p.stats['last_decision']['threshold'], 90)
        self.assertFalse(p.allow_refill(float('nan'), 10, 10, 0, self.source, .8))
        self.assertEqual(p.stats['refill_calls'], 0)

    def test_actual_call_and_timeout_time_are_charged_without_stale_reservations(self):
        p = self.policy
        self.clock.advance(2.7)
        self.assertFalse(p.allow_refill(92, 10, 10, 0, self.source, .8))
        self.clock.advance(.1)
        self.assertTrue(p.allow_refill(92, 10, 10, 0, self.source, .8))
        # Eligibility alone spends nothing: a subsequent residual rejection
        # must not reserve a token forever.
        self.assertTrue(p.allow_refill(92, 10, 10, 0, self.source, .8))
        packing = np.zeros((100, 3))
        def success():
            self.clock.advance(.5)
            return packing, {'original': True}
        wrapped = p.wrap_refill(success)
        q, report = wrapped()
        self.assertIs(q, packing); self.assertEqual(report, {'original': True})
        self.assertAlmostEqual(p.stats['refill_seconds'], .5)
        self.assertLessEqual(p.snapshot()['observed_refill_fraction'], .18)
        self.assertIsNone(wrapped()[0])
        self.assertEqual(p.stats['refill_calls'], 1)
        self.clock.advance(2.3)
        def timed_out():
            self.clock.advance(.5)
            raise TimeoutError('simulated bounded call')
        with self.assertRaises(TimeoutError):
            p.wrap_refill(timed_out)()
        self.assertAlmostEqual(p.stats['refill_seconds'], 1.)
        self.assertEqual(p.stats['refill_timeouts'], 1)
        self.assertFalse(p.inflight)
        self.assertLessEqual(p.snapshot()['observed_refill_fraction'], .18)

    def test_late_native_return_records_debt_and_blocks_new_attempts(self):
        p = self.policy
        self.clock.advance(2.8)
        def late():
            self.clock.advance(.9)
            raise TimeoutError('simulated native late return')
        with self.assertRaises(TimeoutError):
            p.wrap_refill(late)()
        self.assertAlmostEqual(p.stats['refill_seconds'], .9)
        self.assertEqual(p.stats['attempt_overruns'], 1)
        self.assertAlmostEqual(p.stats['attempt_overrun_seconds'], .4)
        self.assertGreater(p.snapshot()['current_budget_excess_seconds'], 0.)
        self.assertFalse(p.budget_available())
        self.clock.advance(4.1)
        self.assertTrue(p.budget_available())
        self.assertEqual(p.snapshot()['current_budget_excess_seconds'], 0.)


if __name__ == '__main__':
    unittest.main()
