"""Nontrivial geometry and finite-graph optimizer checks for upright refill."""
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from refill_search import (fill_rect, forbidden_interval, maximum_independent_set,
                           sat_gaps)


class RefillTests(unittest.TestCase):
    def test_milp_and_simplicial_match_exhaustive_graph_optimum(self):
        rng = np.random.default_rng(17)
        for n in range(3, 12):
            graph = [set() for _ in range(n)]
            for i, j in itertools.combinations(range(n), 2):
                if rng.random() < .35:
                    graph[i].add(j); graph[j].add(i)
            chosen, info = maximum_independent_set(graph, 2.)
            expected = max(len(subset) for r in range(n + 1)
                           for subset in itertools.combinations(range(n), r)
                           if all(j not in graph[i] for i, j in itertools.combinations(subset, 2)))
            self.assertEqual(len(chosen), expected)
            self.assertTrue(info['finite_set_optimal'])

    def test_exclusion_interval_matches_sat(self):
        square = np.array([1.7, 2.2, math.atan(2 / 3)])
        for fixed_axis in (0, 1):
            interval = forbidden_interval(2.05, square, fixed_axis, margin=0.)
            self.assertIsNotNone(interval)
            for free, separated in ((interval[0] - 1e-5, True),
                                     (sum(interval) / 2, False),
                                     (interval[1] + 1e-5, True)):
                center = [free, 2.05] if fixed_axis == 1 else [2.05, free]
                self.assertEqual(sat_gaps([center], [square])[0] > 0, separated)

    def test_recovers_four_uprights_around_known_five_square_diamond(self):
        L = 2 + 1 / math.sqrt(2) + 1e-5
        core = np.array([[L / 2, L / 2, math.pi / 4]])
        upright, info = fill_rect(L, L, core, time_limit=2.)
        self.assertEqual(len(upright), 4)
        self.assertGreater(float(sat_gaps(upright[:, :2], core).min()), 0.)
        self.assertTrue(info['finite_set_optimal'])

    def test_empty_rectangle_grid_capacity(self):
        upright, _ = fill_rect(2.2, 3.2, np.empty((0, 3)), time_limit=2.)
        self.assertEqual(len(upright), 6)

    def test_soft_core_overlap_is_explicitly_only_a_search_seed(self):
        L = 2.69
        core = np.array([[L / 2, L / 2, math.pi / 4]])
        strict, _ = fill_rect(L, L, core, time_limit=2.)
        soft, info = fill_rect(L, L, core, time_limit=2., soft=.02)
        self.assertLess(len(strict), 4)
        self.assertEqual(len(soft), 4)
        self.assertTrue(info['requires_repair'])
        self.assertLess(info['upright_core_min_gap'], 0)
        self.assertGreaterEqual(info['upright_core_min_gap'], -.02)


if __name__ == '__main__':
    unittest.main()
