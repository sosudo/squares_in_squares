"""Compile the actual CUDA objective as a one-thread CPU directional control."""
import ast
import hashlib
import io
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import full_structural_gpu_ties as ties


def generated_cuda():
    tree=ast.parse((ROOT/'vendor/lightning_ftmc/gpu_topology.py').read_text())
    original=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name)and t.id=='CUDA'for t in n.targets))
    namespace={'square':types.SimpleNamespace(CUDA=original)}
    for node in ast.parse((ROOT/'vendor/lightning_ftmc/gpu_rect_optimizer.py').read_text()).body:
        if isinstance(node,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='src'for t in node.targets):
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<pinned CUDA generator>','exec'),namespace)
    return namespace['src']


class ActualObjectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=generated_cuda();cls.patched,cls.audit=ties.patch_cuda(cls.original)
        if shutil.which('g++')is None:raise unittest.SkipTest('C++ compiler unavailable')
        cls.temp=tempfile.TemporaryDirectory();folder=Path(cls.temp.name)
        start=cls.original.index('__device__ double objective(')
        stop=cls.original.index('__global__ void eval',start)
        old=cls.original[start:stop].replace('double objective(','double objective_original(',1)
        start=cls.patched.index('__device__ double objective(')
        stop=cls.patched.index('__global__ void eval',start)
        new=cls.patched[start:stop].replace('double objective(','double objective_symmetric(',1)
        sign=re.search(r'__device__ double sg\(double x\)\{[^}]+\}',cls.original).group()
        header='''#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <vector>
using std::max;using std::min;
#define __device__
#define __syncthreads() ((void)0)
struct Index {int x;};Index threadIdx{0},blockDim{1};
int atomicExch(int*p,int value){int old=*p;*p=value;return old;}
'''
        main='''int main(int argc,char**argv){
 int n;double W,H,tau;std::cin>>n>>W>>H>>tau;
 std::vector<double>q(3*n),g(3*n),cs(2*n),r(512);for(double&v:q)std::cin>>v;
 int nc=(int)std::ceil((max(W,H)+6)/1.5)+1;std::vector<int>head(nc*nc),next(n);double mp=0;
 double E=(argv[1][0]=='o'?objective_original:objective_symmetric)(q.data(),g.data(),n,W,H,tau,nc,head.data(),next.data(),cs.data(),r.data(),&mp);
 std::cout<<std::setprecision(17)<<E<<" "<<mp;for(double v:g)std::cout<<" "<<v;std::cout<<"\\n";
}
'''
        source=folder/'objective.cpp';source.write_text(header+sign+'\n'+old+'\n'+new+'\n'+main)
        cls.binary=folder/'objective'
        subprocess.run(['g++','-std=c++17','-O2','-ffp-contract=off',str(source),'-o',str(cls.binary)],
                       check=True,capture_output=True,timeout=20)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'temp'):cls.temp.cleanup()

    def evaluate(self,mode,p,boxes,tau=0.):
        out=[];grad=[]
        for q,box in zip(p,boxes):
            text=f'{len(q)} {box[0]:.17g} {box[1]:.17g} {tau:.17g}\n'
            text+='\n'.join(' '.join(f'{x:.17g}'for x in row)for row in q)+'\n'
            result=subprocess.run([str(self.binary),mode],input=text,text=True,capture_output=True,
                                  check=True,timeout=2)
            values=np.fromstring(result.stdout,sep=' ');self.assertEqual(len(values),2+3*len(q))
            out.append(values[:2]);grad.append(values[2:].reshape(len(q),3))
        return np.array(out),np.array(grad)

    def test_one_pinned_patch_and_fail_closed_source_identity(self):
        self.assertEqual(hashlib.sha256(self.original.encode()).hexdigest(),ties.EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.audit['replacement_count'],1)
        self.assertFalse(self.audit['energy_changed'])
        self.assertEqual(ties.audit_patched(self.patched)['patched_sha256'],self.audit['patched_sha256'])
        for bad in(self.original+'\n',self.patched):
            with self.assertRaises(ValueError):ties.patch_cuda(bad)

    def test_actual_patched_objective_passes_coupled_directional_protocol(self):
        result=ties.directional_checks(lambda p,b,tau=0.:self.evaluate('symmetric',p,b,tau))
        self.assertTrue(result['passed']);self.assertEqual(len(result['coherent_controls']),8)
        self.assertEqual(len(result['corner_controls']),4)
        # The formerly shipped objective fails the actual same physics control.
        with self.assertRaises(AssertionError):
            ties.directional_checks(lambda p,b,tau=0.:self.evaluate('original',p,b,tau))

    def test_exact_energy_and_untied_gradients_are_unchanged(self):
        for tau in(0.,.02):
            q=np.array([[[2.,2.,.13],[2.9,2.2,.47]]]);box=np.array([[10.,10.]])
            before=self.evaluate('original',q,box,tau);after=self.evaluate('symmetric',q,box,tau)
            np.testing.assert_array_equal(before[0],after[0]);np.testing.assert_array_equal(before[1],after[1])
            for angle,dy in((0.,.8),(.31,.2),(0.,.9)):
                q=ties._pair(angle,dy)[None]
                np.testing.assert_array_equal(self.evaluate('original',q,box,tau)[0],
                                              self.evaluate('symmetric',q,box,tau)[0])


if __name__=='__main__':unittest.main()
