import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np


spec = importlib.util.spec_from_file_location(
    'ftmc_funnel_metrics', Path(__file__).parents[1] / 'experiments/ftmc_funnel_metrics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_quench_thresholds_and_output_identity(tmp_path):
    q = np.zeros((4, 2, 3))
    q[3, 0, 0] = np.nan
    out = np.array([[0., 1e-6], [0., .005], [0., .02], [0., 0.]])
    result = (q, out)
    def quench(*args, **kwargs):
        return result
    w = SimpleNamespace(explore=quench, precise=quench,
                        rect_lp=lambda p, w, h: p,
                        excess=lambda p, w, h: 0., gaps=lambda p: 1.)
    handle = module.install_metrics(w, tmp_path / 'metrics.json', flush_seconds=0)
    assert w.explore(None, None, steps=500) is result
    assert w.precise(None, None, steps=1100) is result
    state = handle.snapshot()
    assert state['stages']['core_fp32']['rows'] == 4
    assert state['stages']['core_fp32']['finite_rows'] == 3
    assert state['stages']['core_fp32']['eligible_for_next_stage'] == 2
    assert state['stages']['full_fp64']['eligible_for_next_stage'] == 1
    assert np.isnan(q[3, 0, 0]) and np.array_equal(out, result[1])
    assert json.loads((tmp_path / 'metrics.json').read_text())['schema_version'] == 1
    handle.restore()
    assert w.explore is quench


def test_lp_and_official_funnel(tmp_path):
    outputs = [None, np.array([[2., 0., 0.]]), np.array([[np.inf, 0., 0.]])]
    w = SimpleNamespace(explore=lambda *a, **k: None,
                        precise=lambda *a, **k: None,
                        rect_lp=lambda *a, **k: outputs.pop(0),
                        excess=lambda p, w, h: float(p[0, 0]),
                        gaps=lambda p: 1e-8,
                        certify=lambda p: bool(p[0, 0] > 0))
    handle = module.install_metrics(w, tmp_path / 'funnel.json')
    p = np.array([[3., 0., 0.]])
    assert w.rect_lp(p, 1, 1) is None
    q = w.rect_lp(p, 1, 1)
    assert q[0, 0] == 2.
    w.rect_lp(p, 1, 1)
    assert w.certify(p) is True
    assert w.certify(-p) is False
    s = handle.snapshot()
    assert s['rect_lp']['calls'] == 3
    assert s['rect_lp']['returned_none'] == 1
    assert s['rect_lp']['returned_nonfinite'] == 1
    assert s['rect_lp']['strict_bloat_decreases'] == 1
    assert s['rect_lp']['positive_gap'] == 1
    assert s['rect_lp']['bloat_decrease_sum'] == 1.
    assert s['certify']['accepted'] == s['certify']['rejected'] == 1
    handle.restore()


class FunnelMetricsTests(unittest.TestCase):
    def test_thresholds_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            test_quench_thresholds_and_output_identity(Path(directory))

    def test_lp_and_certification(self):
        with tempfile.TemporaryDirectory() as directory:
            test_lp_and_official_funnel(Path(directory))


if __name__ == '__main__':
    unittest.main()
