import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'));sys.path.insert(0,str(ROOT/'scripts'))
from ftmc_targeted_mutations import extend_row_capacity,extend_reference_capacity,make_mutations,install_policy
from build_targeted_ftmc_job import PROTOCOLS


def fixture_module():
    namespace={'np':np,'GAP':2e-7,'half':lambda a:.5*(abs(np.cos(a))+abs(np.sin(a)))}
    for path,names in [(ROOT/'vendor/lightning_ftmc/solver.py',{'normalize'}),
        (ROOT/'vendor/lightning_ftmc/gpu_ftmc_refill.py',{'dimensions','excess','cold_core','mutations','worker'})]:
        nodes=[node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef)and node.name in names]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return SimpleNamespace(mutations=namespace['mutations'],worker=namespace['worker'])


class TargetedProtocolTests(unittest.TestCase):
    def test_row_extension_is_counted_and_preserves_other_arrays(self):
        source=(ROOT/'vendor/lightning_ftmc/gpu_upright_rows.py').read_text()
        patched,audit=extend_row_capacity(source)
        self.assertIn('tx[256],ty[256],co[256],si[256]',patched)
        self.assertIn('assert m<=256',patched)
        self.assertIn('positions[64][32]',patched)
        self.assertEqual(audit['additional_shared_bytes'],1024)
        with self.assertRaises(ValueError):extend_row_capacity(patched)

    def test_reference_guard_matches_kernel_capacity(self):
        source=(ROOT/'experiments/ftmc_refill_budget.py').read_text()
        self.assertIn('if len(core) > 256:',extend_reference_capacity(source))

    def test_mutation_cap_accepts256_and_rejects257_without_truncation(self):
        p=np.array([[i%16+.5,i//16+.5,.1]for i in range(256)]+[[20.,20.,0.]]*4)
        bad=p.copy();bad[256,2]=.1
        for config in PROTOCOLS.values():
            worker=fixture_module();fn,audit=make_mutations(worker,config)
            seeds,_,_=fn(p,16,16,4,np.random.default_rng(16),4,1,[p])
            self.assertEqual([len(q)for q in seeds],[256]*4)
            self.assertEqual(fn(bad,16,16,4,np.random.default_rng(17),4,1,[bad]),([],[],[]))
            self.assertEqual(audit['core_cap'],256)

    def test_combined_adaptation_preserves_fixed_n65_mass_and_full_batch(self):
        for config in PROTOCOLS.values():
            worker=fixture_module();dummy=SimpleNamespace(keep=lambda *a:None,allow_refill=lambda *a:True)
            audit=install_policy(worker,dummy,dummy,lambda *a:None,config)
            namespace=worker.worker.__globals__
            weights=namespace['_targeted_weights'](['8_8_1','21_7_15','7_21_15'],
                {'8_8_1':1.,'21_7_15':1.,'7_21_15':1.})
            self.assertAlmostEqual(float(weights.sum()),1.)
            self.assertEqual(weights[0],config['n65_mass'])
            self.assertEqual(namespace['_ftmc_gentle_sides'](.9,2,16).shape,(32,))
            self.assertEqual(audit['changes']['targeted_mode_cycle'],1)
            self.assertTrue(audit['shared_live_globals'])


if __name__=='__main__':unittest.main()
