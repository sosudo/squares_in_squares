from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from joint_pose_mis import conflict_graph,clique_cover,inside


class JointGraphControls(unittest.TestCase):
    def test_exact_upright_contact_is_not_a_conservative_false_conflict(self):
        q=np.array([[.5,.5,0.],[1.5,.5,0.]])
        graph,info=conflict_graph(q)
        self.assertFalse(graph[0]);self.assertFalse(graph[1])
        self.assertEqual(info['unresolved_conservative_edges'],0)

    def test_tiny_true_upright_overlap_is_resolved_exactly(self):
        q=np.array([[.5,.5,0.],[1.5-1e-14,.5,0.]])
        graph,_=conflict_graph(q)
        self.assertIn(1,graph[0])

    def test_arbitrary_angle_broad_phase_and_full_sat(self):
        q=np.array([[1.,1.,np.pi/4],[2.3,1.,np.pi/4],[2.1,2.1,np.pi/4]])
        graph,_=conflict_graph(q)
        self.assertIn(1,graph[0])
        self.assertNotIn(2,graph[0])

    def test_geometric_clique_cover_is_a_valid_vertex_partition(self):
        graph=[{1,2},{0,2},{0,1},set()]
        cover=clique_cover(graph)
        self.assertEqual(len(cover),2)
        self.assertEqual(sorted(v for clique in cover for v in clique),list(range(4)))

    def test_rotated_wall_filter_resolves_inside_and_outside(self):
        a=.3;e=.5*(np.cos(a)+np.sin(a))
        self.assertTrue(inside(np.array([e+1e-10,1.,a]),3.))
        self.assertFalse(inside(np.array([e-1e-10,1.,a]),3.))
