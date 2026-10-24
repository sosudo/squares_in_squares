import math
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import junction_cavity_mis as cavity


class JunctionGeometryTests(unittest.TestCase):
    def test_expanded_minkowski_vertices_separate_arbitrary_angles(self):
        for outside_angle in (0., -.2, math.pi/4):
            fixed = np.array([3., 3., outside_angle])
            for angle in (0., .37, math.pi/4):
                vertices = cavity.obstacle(fixed, angle, cavity.CONTACT_CLEARANCE)
                candidates = np.column_stack([vertices, np.full(len(vertices), angle)])
                self.assertTrue(cavity.valid_against_outside(candidates, fixed[None, :], 10.).all())

    def test_contact_recovery_full_gate_and_duplicate_negative(self):
        report = cavity.controls()
        self.assertTrue(report['new_contact_recovery']['valid'])
        self.assertTrue(report['duplicate_negative'])

    def test_wall_and_collision_rejection(self):
        fixed = np.array([[3., 3., .2]])
        poses = np.array([[3., 3., -.1], [.1, 3., 0.], [6., 6., .5]])
        self.assertEqual(cavity.valid_against_outside(poses, fixed, 10.).tolist(), [False, False, True])


if __name__ == '__main__':
    unittest.main()
