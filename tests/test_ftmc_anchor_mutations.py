"""Geometric and isolation properties of the optional FTMC anchor initializer."""
import copy
from pathlib import Path
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
from ftmc_anchor_mutations import bounds, incumbent_anchor, make_mutations, reanchor


class AnchorTests(unittest.TestCase):
    def setUp(self):
        # A compact tilted motif anchored near the lower-left corner of a much
        # larger box, with upright squares establishing the full box bounds.
        self.core = np.array([[1., 1., .3], [2.4, 1.2, .31],
                              [1.2, 2.5, .29], [2.6, 2.7, .3]])
        self.source = np.vstack((self.core, [.5, .5, 0.], [8.5, 8.5, 0.]))

    def test_centering_roundtrip_restores_original_core(self):
        box, anchor = incumbent_anchor(self.source, 8, 8)
        centered, _ = reanchor(self.core, box, [.5, .5])
        restored, _ = reanchor(centered, box, anchor)
        np.testing.assert_allclose(restored, self.core, rtol=0, atol=2e-15)
        self.assertGreater(np.linalg.norm(centered[:, :2]-self.core[:, :2]), 2.)

    def test_wall_policies_preserve_rigid_geometry_and_fit(self):
        box, _ = incumbent_anchor(self.source, 8, 8)
        original = self.core.copy()
        for anchor in ([0., 0.], [1., 0.], [0., 1.], [1., 1.]):
            q, _ = reanchor(self.core, box, anchor)
            np.testing.assert_array_equal(q[:, 2], original[:, 2])
            np.testing.assert_allclose(q[:, None, :2]-q[None, :, :2],
                                       original[:, None, :2]-original[None, :, :2],
                                       rtol=0, atol=2e-15)
            low, high = bounds(q)
            self.assertTrue(np.all(low >= -2e-15))
            self.assertTrue(np.all(high <= box+2e-15))
        np.testing.assert_array_equal(self.core, original)

    def test_adapter_retains_targets_rng_and_source_objects(self):
        box, _ = incumbent_anchor(self.source, 8, 8)
        centered, _ = reanchor(self.core, box, [.5, .5])
        seeds = [centered.copy() for _ in range(8)]
        targets = [.8]*8
        recipes = [{'mode': 0} for _ in range(8)]
        def original(p, w, h, d, rng, B, mode, archive):
            rng.normal()
            return seeds, targets, recipes
        worker = types.SimpleNamespace(mutations=original)
        disabled, _ = make_mutations(worker, enabled=False)
        self.assertIs(disabled, original)
        adapted, _ = make_mutations(worker, enabled=True, policy='mixed_walls')
        rng0 = np.random.default_rng(4)
        rng1 = np.random.default_rng(4)
        source_copy = self.source.copy()
        original(self.source, 8, 8, 0, rng0, 8, 0, [])
        output, output_targets, metadata = adapted(self.source, 8, 8, 0, rng1, 8, 0, [])
        self.assertEqual(rng0.bit_generator.state, rng1.bit_generator.state)
        self.assertIs(output_targets, targets)
        self.assertEqual(recipes, [{'mode': 0}]*8)
        np.testing.assert_array_equal(self.source, source_copy)
        for q in seeds:
            np.testing.assert_array_equal(q, centered)
        for q in output[:4]:
            np.testing.assert_allclose(q, self.core, rtol=0, atol=2e-15)
        self.assertEqual([r['anchor_fraction'] for r in metadata[4:]],
                         [[0., 0.], [1., 0.], [0., 1.], [1., 1.]])


if __name__ == '__main__':
    unittest.main()
