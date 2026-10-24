"""Source and exact-fixture admission controls; no local optimizer or CUDA."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'tests')]
from test_full_structural_gpu_ties import generated_cuda
from full_structural_gpu_ties import patch_cuda
from fq_mixed_precision_adapter import float_source,observational_source,FP64_SHA
from fq_mixed_precision_diagnostic import load_fixtures


class PortAdmissionTests(unittest.TestCase):
    def test_exact_source_port_thresholds_guards_and_untouched_timed_body(self):
        original,_=patch_cuda(generated_cuda());before=hashlib.sha256(original.encode()).hexdigest()
        port,audit=float_source(original)
        self.assertEqual(before,FP64_SHA)
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),before)
        for constant in ('2e-11','1e-24','1e-30','1e-4'):
            self.assertIn(constant+'f',port)
        self.assertIn('double radial_dx=(double)q[3*j]-(double)x',port)
        self.assertIn('floor(((double)q[3*i]+3.0)/1.5)',port)
        observed=observational_source(port)
        body=port[port.index('__global__ void lbfgs('):port.rfind('\n}')]
        self.assertIn(body,observed)
        with self.assertRaises(ValueError):float_source(original.replace('2e-11','2e-10'))

    def test_full_generated_float_and_observational_source_compiles(self):
        if shutil.which('g++') is None:self.skipTest('C++ compiler unavailable')
        original,_=patch_cuda(generated_cuda());port,_=float_source(original)
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
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'port.cpp';path.write_text(header+observational_source(port))
            result=subprocess.run(['g++','-std=c++17','-ffp-contract=off','-fsyntax-only',str(path)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_actual_frozen_side_vectors_verified_before_explicit_expansion(self):
        folder=ROOT/'artifacts/fq-mixed-precision-inputs-v3'
        if not folder.exists():folder=ROOT/'artifacts/fq-mixed-precision-inputs-v2'
        if not folder.exists():self.skipTest('Actual frozen fixture not present')
        config=json.loads((folder/'mixed-config.json').read_text());rows,_=load_fixtures(config,folder)
        self.assertEqual(len(rows),4)
        for row in rows:
            self.assertEqual(row['poses'].shape,(32,row['n'],3))
            self.assertEqual(row['original_sides'].shape,(32,))
            self.assertEqual(row['boxes'].shape,(32,2))
            self.assertTrue(np.array_equal(row['boxes'][:,0],row['original_sides']))
            self.assertTrue(np.array_equal(row['boxes'][:,1],row['original_sides']))
            self.assertEqual(hashlib.sha256(row['original_sides'].tobytes()).hexdigest(),row['boxes_sha256'])
            self.assertFalse(row['poses'].flags.writeable)
        config['batches'][0]['boxes_sha256']='0'*64
        with self.assertRaises(AssertionError):load_fixtures(config,folder)


if __name__=='__main__':unittest.main()
