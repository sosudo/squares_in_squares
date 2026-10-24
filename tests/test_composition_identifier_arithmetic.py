"""Exercise actual patched CUDA identifier expressions with native C++ types.

No GPU is initialized. Device int donor/z arithmetic has the same integer
promotion rules as these native helpers. The separate GPU preflight exercises
the device compiler/runtime before a large donor search.
"""
import ctypes
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from compose_gadgets import compatible_gpu_sources


class CompositionIdentifierArithmeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('c++')
        if not compiler:
            raise unittest.SkipTest('Native C++ compiler unavailable')
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        vendor = ROOT/'vendor/lightning_ftmc'
        cls.vendor_hashes = {name: hashlib.sha256((vendor/name).read_bytes()).hexdigest()
                             for name in ('gpu_fault_composition.py', 'gpu_seam_profiles.py',
                                          'gpu_adaptive_seams.py')}
        runtime, _ = compatible_gpu_sources(vendor)
        cls.sites = []
        for name, expected in [('gpu_fault_composition.py', 2), ('gpu_seam_profiles.py', 1),
                               ('gpu_adaptive_seams.py', 1)]:
            expressions = re.findall(r'\bjob\s*=\s*([^;,\n]+)', (runtime/name).read_text())
            if len(expressions) != expected:
                raise AssertionError((name, expressions))
            cls.sites.extend((name, expression) for expression in expressions)
        wrappers = []
        for i, (_, expression) in enumerate(cls.sites):
            wrappers.append('extern "C" void calc_'+str(i)+'(int donor,int z,uint64_t q,'
                'uint64_t* job,uint64_t* encoded){*job='+expression+';*encoded=(q<<32)|*job;}')
        # -fwrapv makes the old signed expression a deterministic counterexample,
        # without relying on an optimizing compiler's treatment of undefined overflow.
        wrappers.append('extern "C" uint64_t old_signed(int donor,int z)'
                        '{return donor*(31*31*63)+z;}')
        source = Path(cls.directory.name)/'identifiers.cpp'
        library = source.with_suffix('.so')
        source.write_text('#include <cstdint>\n'+'\n'.join(wrappers)+'\n')
        subprocess.run([compiler, '-std=c++17', '-O2', '-fwrapv', '-shared', '-fPIC',
                        str(source), '-o', str(library)], check=True, capture_output=True, timeout=15)
        cls.library = ctypes.CDLL(str(library))
        for i in range(len(cls.sites)):
            fn = getattr(cls.library, 'calc_'+str(i))
            fn.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                           ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)]
            fn.restype = None
        cls.library.old_signed.argtypes = [ctypes.c_int, ctypes.c_int]
        cls.library.old_signed.restype = ctypes.c_uint64

    def test_all_four_actual_expressions_preserve_job_and_bloat_bits(self):
        stride = 31*31*63
        last_donor, last_z = divmod(2**32-1, stride)
        cases = [(35470, 0), (35470, stride-1), (35471, 0), (60000, stride-1),
                 (last_donor, last_z)]
        q = 802428781
        for i, (filename, expression) in enumerate(self.sites):
            fn = getattr(self.library, 'calc_'+str(i))
            for donor, z in cases:
                with self.subTest(file=filename, expression=expression, donor=donor, z=z):
                    job, encoded = ctypes.c_uint64(), ctypes.c_uint64()
                    fn(donor, z, q, ctypes.byref(job), ctypes.byref(encoded))
                    expected = donor*stride+z
                    self.assertLessEqual(expected, 2**32-1)
                    self.assertEqual(job.value, expected)
                    self.assertEqual(encoded.value >> 32, q)
                    self.assertEqual(encoded.value & (2**32-1), expected)

    def test_old_signed_intermediate_poisoned_high_bits(self):
        old = self.library.old_signed(35471, 0)
        self.assertNotEqual(old, 35471*(31*31*63))
        self.assertEqual(old >> 32, 2**32-1)
        q = 802428781
        self.assertNotEqual(((q << 32) | old) >> 32, q)

    def test_public_vendor_sources_stay_unchanged(self):
        vendor = ROOT/'vendor/lightning_ftmc'
        for filename, expected in self.vendor_hashes.items():
            self.assertEqual(hashlib.sha256((vendor/filename).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
