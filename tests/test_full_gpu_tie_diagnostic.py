"""The diagnostic must compile as a complete generated CUDA translation unit."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
sys.path.insert(0,str(ROOT/'tests'))
from test_full_structural_gpu_ties import generated_cuda
from full_structural_gpu_ties import patch_cuda
from diagnose_full_gpu_ties import diagnostic_source


class DiagnosticSourceTests(unittest.TestCase):
    def test_full_generated_source_closes_extern_and_compiles(self):
        if shutil.which('g++')is None:self.skipTest('C++ compiler unavailable')
        patched,_=patch_cuda(generated_cuda())
        source=diagnostic_source(patched)
        self.assertNotIn('__global__ void lbfgs',source)
        header='''#include <algorithm>
#include <cmath>
using std::max;using std::min;
#define __device__
#define __global__
#define __shared__
#define __syncthreads() ((void)0)
struct Index{int x;};Index threadIdx{0},blockDim{1},blockIdx{0};
int atomicExch(int*p,int value){int old=*p;*p=value;return old;}
'''
        with tempfile.TemporaryDirectory()as folder:
            path=Path(folder)/'diagnostic.cpp';path.write_text(header+source)
            result=subprocess.run(['g++','-std=c++17','-fsyntax-only',str(path)],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
