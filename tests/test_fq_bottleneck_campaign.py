"""Contact-region tests exercise geometry and the connected-region guarantee."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_bottleneck_campaign as target


def grid():
    return np.array([[x+.5, y+.5, 0.] for x in range(8) for y in range(7)])


def check_exact_contact_gap_matches_axis_aligned_square_distances():
    pose = np.array([[0., 0., 0.], [1., 0., 0.], [1.1, 0., 0.], [1., 1., 0.]])
    gap, distance = target.contact_geometry(pose)
    np.testing.assert_allclose(gap, gap.T)
    np.testing.assert_allclose(gap[0], [-1., 0., .1, 0.], atol=1e-14)
    np.testing.assert_allclose(distance[0], [0., 1., 1.1, np.sqrt(2)])


def check_region_is_deterministic_connected_and_does_not_modify_source():
    pose = grid(); original = pose.copy()
    for amplitude, count in [(.3, 24), (.6, 40)]:
        frozen, record = target.contact_neighborhood(pose, 7192, amplitude)
        again, other = target.contact_neighborhood(pose, 7192, amplitude)
        np.testing.assert_array_equal(frozen, again)
        np.testing.assert_array_equal(pose, original)
        assert record == other
        assert record['connected_free_count'] == count
        assert record['fallback_nearest_count'] == 0
        free = record['free_indices']
        assert len(set(free)) == count
        assert set(free).isdisjoint(frozen)
        assert set(free) | set(frozen) == set(range(len(pose)))
        gap, distance = target.contact_geometry(pose)
        connected = {free[0]}
        for node in free[1:]:
            assert any(gap[node, previous] <= .035 and distance[node, previous] <= 1.6
                       for previous in connected)
            connected.add(node)


class ContactNeighborhoodTests(unittest.TestCase):
    def test_axis_gap(self):
        check_exact_contact_gap_matches_axis_aligned_square_distances()

    def test_connected_region(self):
        check_region_is_deterministic_connected_and_does_not_modify_source()

    def test_rotated_support_and_rigid_rotation_invariance(self):
        pose = np.array([[0., 0., 0.], [1.3, 0., np.pi/4], [.7, 1.4, -.2]])
        gap, distance = target.contact_geometry(pose)
        self.assertAlmostEqual(gap[0, 1], 1.3-.5-np.sqrt(.5), places=13)
        rotation = .371
        matrix = np.array([[np.cos(rotation), -np.sin(rotation)],
                           [np.sin(rotation), np.cos(rotation)]])
        transformed = pose.copy()
        transformed[:, :2] = pose[:, :2] @ matrix.T
        transformed[:, 2] += rotation
        rotated_gap, rotated_distance = target.contact_geometry(transformed)
        np.testing.assert_allclose(rotated_gap, gap, atol=1e-14)
        np.testing.assert_allclose(rotated_distance, distance, atol=1e-14)


if __name__ == '__main__':
    unittest.main()
