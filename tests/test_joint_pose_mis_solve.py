from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from joint_pose_mis_solve import greedy,independent,strengthening_cliques,solve_mis


class JointSolverControls(unittest.TestCase):
    def test_greedy_respects_a_true_source_seed_and_all_conflicts(self):
        graph=[{1,2},{0,2},{0,1},set()]
        result=greedy(graph,initial=[1])
        self.assertTrue(independent(graph,result));self.assertIn(1,result)
        self.assertEqual(len(result),2)

    def test_every_strengthening_clique_is_an_actual_graph_clique(self):
        graph=[{1,2},{0,2},{0,1,3},{2}]
        for clique in strengthening_cliques(graph,[[0,1,2],[3]]):
            self.assertTrue(all(j in graph[i]for k,i in enumerate(clique)for j in clique[k+1:]))

    def test_real_milp_cardinality_and_upper_bound_are_distinct_from_geometry(self):
        chosen,report=solve_mis(4,np.array([[0,1],[0,2],[1,2]]),[[0,1,2]],4,2.)
        self.assertEqual(len(chosen),2)
        self.assertEqual(report['selected_count'],2)
        self.assertTrue(report['finite_graph_optimal'])
        self.assertAlmostEqual(report['reported_cardinality_upper'],2.)
