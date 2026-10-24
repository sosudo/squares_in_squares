"""The optional worker adaptation must relax only the row lower-bound gate."""
import ast
from pathlib import Path
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from ftmc_refill_gate import make_worker


SOURCE = '''def worker(row_counts, scores, w, h, d):
    attempts=0
    for b in range(len(scores)):
        if attempts>=4:break
        if row_counts.reshape(-1,2)[b].max()<w*h+d-4:continue
        if not np.isfinite(scores[b]).all()or scores[b,1]>.01:continue
        attempts+=1
    return attempts
'''


class RefillGateTests(unittest.TestCase):
    def module(self, source=SOURCE):
        namespace = {'np': np}
        exec(compile(source, '<test-fallback-gates>', 'exec'), namespace)
        return types.SimpleNamespace(worker=namespace['worker'])

    def test_lower_row_capacity_no_longer_blocks_bounded_2d_attempts(self):
        module = self.module()
        original, _ = make_worker(module, False, SOURCE)
        changed, _ = make_worker(module, True, SOURCE)
        rows = np.full(24, 80)
        scores = np.zeros((12, 2))
        self.assertEqual(original(rows, scores, 10, 10, 5), 0)
        self.assertEqual(changed(rows, scores, 10, 10, 5), 4)
        scores[:, 1] = .02
        self.assertEqual(changed(rows, scores, 10, 10, 5), 0)
        scores[:2, 1] = 0.
        scores[0, 0] = np.nan
        self.assertEqual(changed(rows, scores, 10, 10, 5), 1)

    def test_disabled_returns_same_function_and_unknown_gate_is_rejected(self):
        module = self.module()
        function, _ = make_worker(module, False, SOURCE)
        self.assertIs(function, module.worker)
        with self.assertRaises(ValueError):
            make_worker(module, True, SOURCE.replace('d-4', 'd-5'))

    def test_real_public_worker_contains_exactly_the_reviewed_gate(self):
        path = Path(__file__).resolve().parents[1]/'vendor/lightning_ftmc/gpu_ftmc_refill.py'
        whole = path.read_text()
        node = next(n for n in ast.parse(whole).body if isinstance(n, ast.FunctionDef) and n.name == 'worker')
        source = ast.get_source_segment(whole, node)
        namespace = {}
        exec(compile(source, str(path), 'exec'), namespace)
        module = types.SimpleNamespace(worker=namespace['worker'])
        _, audit = make_worker(module, True, source)
        self.assertEqual(audit['maximum_milp_attempts_per_batch'], 4)
        self.assertEqual(audit['per_attempt_alarm_seconds'], 1.25)


if __name__ == '__main__':
    unittest.main()
