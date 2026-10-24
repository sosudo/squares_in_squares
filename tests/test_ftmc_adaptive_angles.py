import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np
from scipy.spatial import cKDTree


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('adaptive_angles', ROOT / 'experiments/ftmc_adaptive_angles.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cpu_public_functions():
    path = ROOT / 'vendor/lightning_ftmc/gpu_ftmc_refill.py'
    tree = ast.parse(path.read_text())
    wanted = {'dimensions', 'excess', 'cold_core', 'mutations'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    source = ast.get_source_segment(path.read_text(), next(n for n in nodes if n.name == 'mutations'))
    def normalize(p, margin=0.):
        p = np.asarray(p, dtype=float).copy()
        p[:, :2] *= 1 + margin
        half = (abs(np.cos(p[:, 2])) + abs(np.sin(p[:, 2]))) / 2
        p[:, :2] -= (p[:, :2] - half[:, None]).min(axis=0)
        return p
    namespace = {'np': np, 'cKDTree': cKDTree, 'normalize': normalize,
                 'half': lambda a: (abs(np.cos(a)) + abs(np.sin(a))) / 2}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(mutations=namespace['mutations']), source


class AdaptiveAngleTests(unittest.TestCase):
    def test_disabled_and_zero_fraction_exact_parity(self):
        worker, source = cpu_public_functions()
        original = worker.mutations
        disabled, audit = module.make_mutations(worker, False, source_text=source)
        self.assertIs(disabled, original)
        self.assertEqual(audit['modification'], 'none')
        equivalent, _ = module.make_mutations(worker, True, local_fraction=0, source_text=source)
        p = np.array([[x+.5, y+.5, np.radians(18.) if y < 4 else 0.]
                      for y in range(10) for x in range(6)])
        for mode in range(6):
            args = (p, 6, 10, 0)
            a = original(*args, np.random.default_rng(194+mode), 12, mode, [p])
            b = equivalent(*args, np.random.default_rng(194+mode), 12, mode, [p])
            self.assertEqual(a[1:], b[1:])
            self.assertEqual(len(a[0]), len(b[0]))
            for qa, qb in zip(a[0], b[0]):
                np.testing.assert_array_equal(qa, qb)

    def test_active_angles_include_incumbent_and_near_rational(self):
        p = np.zeros((30, 3)); p[:, 2] = np.radians(18.)
        result = module.adaptive_angles(p)
        self.assertEqual(len(result), 32)
        self.assertGreaterEqual(np.sum(abs(module.folded(result-np.radians(18.))) < np.radians(3)), 24)
        self.assertTrue(np.any(abs(result-np.arctan(1/3)) < 1e-12))
        np.testing.assert_array_equal(result[-8:], module.PUBLIC_ANGLES)
        np.testing.assert_array_equal(p[:, 2], np.full(30, np.radians(18.)))

    def test_refuses_unknown_public_assignment(self):
        worker, source = cpu_public_functions()
        with self.assertRaisesRegex(ValueError, 'changed'):
            module.make_mutations(worker, True, source_text=source.replace('26.565051', '25.'))


if __name__ == '__main__':
    unittest.main()
