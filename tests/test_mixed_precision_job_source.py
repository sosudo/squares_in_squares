"""Exact CUDA reconstruction and rejection of unsupported source changes."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_fq_mixed_precision_job as builder


class ExactCudaPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, files = builder.unpack(builder.PARENT, builder.PARENT_SHA, 'xz85')
        cls.topology = files['public_solver/gpu_topology.py']
        cls.rectangular = files['public_solver/gpu_rect_optimizer.py']

    def test_real_frozen_sources_reproduce_reviewed_corrected_cuda(self):
        source, proof = builder.corrected_source(self.topology, self.rectangular)
        self.assertEqual(hashlib.sha256(source).hexdigest(),
            '8ccc1e355158401881545c054c53cc0e6ed1036aaec24856ca2d37b179247601')
        self.assertEqual(proof['literal_string_assignments'], 11)
        self.assertEqual(proof['replacement_count'], 1)
        self.assertFalse(proof['energy_changed'])

    def test_changed_energy_coefficient_rejected(self):
        old = b'energy+=.25*p*p'
        self.assertEqual(self.topology.count(old), 1)
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            builder.corrected_source(self.topology.replace(old, b'energy+=.5*p*p'), self.rectangular)

    def test_nonliteral_python_is_not_executed(self):
        altered = self.rectangular + b"\nsrc=__import__('not_a_real_module_for_control').run()\n"
        with self.assertRaisesRegex(ValueError, 'Unexpected upstream CUDA construction'):
            builder.corrected_source(self.topology, altered)

    def test_duplicate_cuda_declaration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous upstream CUDA declaration'):
            builder.corrected_source(self.topology+b"\nCUDA='replacement'\n", self.rectangular)


if __name__ == '__main__': unittest.main()
