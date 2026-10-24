"""Independent half-plane reference for active-chain separator support geometry."""
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from ftmc_profile_guard import clipped_support


def halfplane_support(square, offset, degrees):
    """Enumerate feasible intersections of eight boundary lines, without clipping."""
    x, y, angle = square
    centre = np.array([x, y]) - offset
    u = np.array([math.cos(angle), math.sin(angle)])
    v = np.array([-math.sin(angle), math.cos(angle)])
    normals = np.array([u, -u, v, -v, [1., 0.], [-1., 0.], [0., 1.], [0., -1.]])
    limits = np.r_[normals[:4] @ centre + .5, 1.00000002, 2e-8, 1.00000002, 2e-8]
    vertices = []
    for i, j in itertools.combinations(range(8), 2):
        matrix = normals[[i, j]]
        if abs(np.linalg.det(matrix)) < 1e-12:
            continue
        point = np.linalg.solve(matrix, limits[[i, j]])
        if np.all(normals @ point <= limits + 1e-12):
            vertices.append(point)
    if not vertices:
        return 2., -2.
    normal = np.array([math.cos(math.radians(degrees)), -math.sin(math.radians(degrees))])
    projected = np.array(vertices) @ normal
    return float(projected.min()), float(projected.max())


class ProfileGeometryReview(unittest.TestCase):
    def test_clipped_support_matches_independent_halfplanes(self):
        rng = np.random.default_rng(77341)
        for _ in range(300):
            offset = rng.integers(-20, 20, 2)
            square = np.r_[offset + rng.uniform(-1.2, 2.2, 2), rng.uniform(-math.pi, math.pi)]
            degrees = float(rng.choice([0, 30, 45, 60, 90]))
            actual = clipped_support(square, offset, degrees)
            expected = halfplane_support(square, offset, degrees)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-11)

    def test_support_sign_and_edge_contacts(self):
        for centre in [(.5, .5), (-.5, -.5), (1.5, 1.5), (-.5, 1.5), (1.5, -.5)]:
            for angle in [0., math.pi/4, math.pi/2]:
                for degrees in [30., 45., 60.]:
                    square = np.r_[centre, angle]
                    np.testing.assert_allclose(clipped_support(square, (0,0), degrees),
                                               halfplane_support(square, (0,0), degrees),
                                               rtol=0, atol=2e-11)


if __name__ == '__main__':
    unittest.main()
