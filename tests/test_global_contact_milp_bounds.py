"""Independent algebraic/domain controls; no LP, MILP, or geometry optimizer."""
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import global_contact_milp as contact


class ContactDomainBounds(unittest.TestCase):
    def test_projection_extrema_equal_all_sixteen_coordinate_corners(self):
        lower_i = np.array([1.1, 2.7]); upper_i = np.array([1.8, 3.2])
        lower_j = np.array([1.2, 1.3]); upper_j = np.array([2.4, 3.8])
        for theta_i, theta_j in [(0., 0.), (0., math.pi / 4), (.31, -.71)]:
            for axis, _ in contact.axes_and_radii(theta_i, theta_j):
                values = []
                for choices in itertools.product((0, 1), repeat=4):
                    i = np.where(choices[:2], upper_i, lower_i)
                    j = np.where(choices[2:], upper_j, lower_j)
                    values.append(float(axis @ (j - i)))
                low, high = contact.projection_bounds(axis, lower_i, upper_i, lower_j, upper_j)
                self.assertAlmostEqual(low, min(values), places=13)
                self.assertAlmostEqual(high, max(values), places=13)

    def test_every_omitted_pair_has_a_complete_trust_domain_separation_reason(self):
        # Per-square and wall-clipped trust boxes, varied axes, and genuinely
        # omitted distant pairs: test every pair, independent of the KD tree.
        rng = np.random.default_rng(91741)
        p = np.column_stack((rng.uniform(.8, 17.2, (42, 2)),
                             rng.choice([0., .31, -math.pi / 4, math.pi / 2], 42)))
        trust = rng.uniform(0., .7, len(p))
        g = contact.geometry(p, trust, 18., clearance=1e-8)
        modeled = {(r['i'], r['j']) for r in g.pairs}
        omitted = 0
        for i, j in itertools.combinations(range(len(p)), 2):
            if (i, j) in modeled:
                continue
            omitted += 1
            # Minimum Euclidean distance between the two whole coordinate
            # domains: if >sqrt(2), the unit-square circumcircles are disjoint.
            delta = np.maximum(np.maximum(g.lower[i] - g.upper[j],
                                          g.lower[j] - g.upper[i]), 0.)
            circle_separated = float(delta @ delta) > 2.
            axis_separated = any(
                contact.projection_bounds(axis, g.lower[i], g.upper[i],
                                          g.lower[j], g.upper[j])[0]
                >= radius + g.clearance + g.guard
                for axis, radius in contact.axes_and_radii(p[i, 2], p[j, 2]))
            self.assertTrue(circle_separated or axis_separated, (i, j))
        self.assertGreater(omitted, 100)

    def test_big_m_is_inactive_over_every_domain_corner_and_active_means_sat(self):
        p = np.array([[2., 2., 0.], [2.7, 2.6, math.pi / 4],
                      [3.2, 1.8, .31], [3.7, 3., -.2]])
        g = contact.geometry(p, .8, 6., side_lower=2., clearance=1e-8)
        selected = [(r['i'], r['j']) for r in g.pairs]
        model = contact.build(g, selected, mode='milp')
        A = model['A'].tocsr(); first_binary = 2 * len(p) + 1
        checked = 0; disjunctions = 0
        for row, pair in enumerate(model['row_pairs']):
            columns = A.getrow(row).indices
            binary = [c for c in columns if c >= first_binary]
            if pair is None or not binary:
                continue
            if all(float(A[row, c]) == 1. for c in binary):
                self.assertEqual(len(columns), len(binary))
                self.assertEqual(model['row_lower'][row], 1.)
                disjunctions += 1
                continue
            self.assertEqual(len(binary), 1)
            selector = binary[0]; M = -float(A[row, selector])
            i, j = pair
            axis = np.array([A[row, 2 * j], A[row, 2 * j + 1]], dtype=float)
            target = float(model['row_lower'][row] + M)
            for choices in itertools.product((0, 1), repeat=4):
                x = np.zeros(A.shape[1]); x[2 * len(p)] = g.side_upper
                x[2 * i:2 * i + 2] = np.where(choices[:2], g.upper[i], g.lower[i])
                x[2 * j:2 * j + 2] = np.where(choices[2:], g.upper[j], g.lower[j])
                inactive = (A.getrow(row) @ x).item() - model['row_lower'][row]
                self.assertGreaterEqual(inactive, -1e-13)
                x[selector] = 1.
                active = (A.getrow(row) @ x).item() - model['row_lower'][row]
                expected = float(axis @ (x[2 * j:2 * j + 2] - x[2 * i:2 * i + 2])) - target
                self.assertAlmostEqual(active, expected, places=12)
            checked += 1
        self.assertEqual(checked, model['info']['binary_variables'])
        self.assertEqual(disjunctions, model['info']['binary_pairs'])
        self.assertGreater(checked, 1)

    def test_nonfinite_clearance_and_side_lower_are_rejected(self):
        p = np.array([[.5, .5, 0.], [1.5, .5, 0.]])
        for bad in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(field='clearance', value=bad), self.assertRaises(ValueError):
                contact.geometry(p, 0., 2., clearance=bad)
            with self.subTest(field='side_lower', value=bad), self.assertRaises(ValueError):
                contact.geometry(p, 0., 2., side_lower=bad)

    def test_undersized_container_cannot_hide_a_zero_trust_wall_violation(self):
        p = np.array([[.5, .5, 0.], [1.5, .5, 0.]])
        #1.99 still exceeds sqrt(2): this exercises actual rigid wall/trust
        #bounds, independently of the necessary area lower bound.
        with self.assertRaisesRegex(ValueError, 'trust/wall domain'):
            contact.geometry(p, 0., 1.99, clearance=0.)
        with self.assertRaises(ValueError):
            contact.geometry(p, 0., 1.3, clearance=0.)


if __name__ == '__main__':
    unittest.main()
