"""Finite source coverage, box-isolated selection and adapted-source guards."""
from pathlib import Path
import sys
import numpy as np
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_n65_cold_pilot as pilot
import fq_n65_cold_finish as finish


def test_balanced_independent_starts_and_cooling_boundary():
    keys=[f'group_{i:02d}' for i in range(16)]
    rows=pilot.design(8.53553390594,keys)
    assert len(rows)==32
    assert {(r['source_key'],r['delta']) for r in rows}=={(k,d) for k in keys for d in (.0005,.002)}
    draws=np.array([rng.random(4) for rng in pilot.random_streams(pilot.SEED,3)])
    assert len({q.tobytes() for q in draws})==32
    np.testing.assert_array_equal(draws,np.array([r.random(4) for r in pilot.random_streams(pilot.SEED,3)]))
    assert not np.array_equal(pilot.acceptance_uniforms(pilot.SEED,3),draws[:,0])
    hot,phase=pilot.temperature_schedule([.3]*32,300.,199.999)
    assert phase=='hot' and np.all(hot==.3)
    cool,phase=pilot.temperature_schedule([.3]*32,300.,200.)
    assert phase=='cool' and np.all(cool==.03)
    assert not pilot.reset_mask(rows,16,True,False,False,-1)['mask'].any()


def test_eight_distinct_source_groups_and_box_isolated_ranking():
    rows=pilot.design(8.53553390594,[str(i) for i in range(16)])
    poses=np.zeros((32,65,3));sides=np.array([r['side'] for r in rows])
    energies=np.tile(np.arange(16,dtype=float)+1,2)
    slots=finish.select_slots(rows,poses,energies,sides)
    assert [r['chain'] for r in slots]==[0,4,8,12,17,21,25,29]
    assert len({r['design']['source_group'] for r in slots})==8
    # A huge between-box scale disparity must not alter either box's winners.
    energies[16:]*=1e12
    assert [r['chain'] for r in finish.select_slots(rows,poses,energies,sides)]==[r['chain'] for r in slots]
    energies[:4]=np.nan
    partial=finish.select_slots(rows,poses,energies,sides)
    assert partial[0]['chain'] is None and partial[4]['chain']==16


def test_fixed_design_rejects_missing_group_and_exact_native_adapter():
    rows=pilot.design(8.5355,[str(i) for i in range(16)])
    rows[1]=dict(rows[1],source_group=0)
    with unittest.TestCase().assertRaisesRegex(ValueError,'group_box'):
        finish.select_slots(rows,np.zeros((32,65,3)),np.ones(32),np.ones(32)*8.5)
    source=pilot.generated_search_source()
    assert 'gpu.quench' not in source  # the unchanged explicitly adapted function is supplied live
    assert 'search_300s_deadline_minus100s' in source and 'deadline-150.' not in source
    assert 'steps=2000,tau=0.' in __import__('inspect').getsource(pilot.prior.fused_quench)
    final=finish.generated_finish_source()
    assert 'ProcessPoolExecutor(max_workers=4' in final and 'workers=4,max_slots=8' in final
    # Production runs the initializer in a separate worker process. Restore
    # its three legacy-module globals when exercising it in this test process.
    previous={name:getattr(finish.original,name) for name in
              ('DELTAS','NATIVE_SECONDS','CERTIFICATE_SECONDS')}
    with patch.multiple(finish.original,**previous):
        finish._configure_worker()
        assert finish.original.DELTAS==(.0005,.002)
        assert finish.original.NATIVE_SECONDS==60 and finish.original.CERTIFICATE_SECONDS==8
    assert all(getattr(finish.original,name)==value for name,value in previous.items())


class PolicyTests(unittest.TestCase):
    test_balance=staticmethod(test_balanced_independent_starts_and_cooling_boundary)
    test_selection=staticmethod(test_eight_distinct_source_groups_and_box_isolated_ranking)
    test_adapters=staticmethod(test_fixed_design_rejects_missing_group_and_exact_native_adapter)


if __name__=='__main__':unittest.main()
