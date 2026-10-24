"""Pure policy checks; actual CUDA gates remain mandatory before each search."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_sustained_cold_pilot as pilot


class SustainedPolicyTests(unittest.TestCase):
    def test_independent_chain_design_and_schedule(self):
        for batch in (32,64,128):
            with patch.object(pilot,'batch_size',return_value=batch):
                rows=pilot.design(978,'31.7','reference_978',batch)
                self.assertEqual([r['chain'] for r in rows],list(range(batch)))
                self.assertEqual(sum(r['delta']==.0005 for r in rows),batch//2)
                self.assertEqual(sum(r['delta']==.002 for r in rows),batch//2)
                self.assertTrue(all(r['arm']=='cold' and r['temperature']==.3 for r in rows))
                self.assertTrue(all(r['side']==31.7-r['delta'] for r in rows))
                draws=[rng.bytes(32) for rng in pilot.random_streams(100,7)]
                self.assertEqual(len(set(draws)),batch)
                self.assertEqual(draws,[rng.bytes(32) for rng in pilot.random_streams(100,7)])
                self.assertEqual(len(pilot.acceptance_uniforms(100,7)),batch)
                self.assertFalse(pilot.cold.reset_mask(rows,16,True,False,False,-1)['mask'].any())
        self.assertEqual(pilot.temperature_schedule([.3],460,359.99)[1],'hot')
        values,phase=pilot.temperature_schedule([.3],460,360.)
        self.assertEqual(phase,'cool');np.testing.assert_array_equal(values,[.03])

    def test_initialized_epoch_and_finalization_reserve(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(pilot.time,'monotonic',return_value=100.),patch.object(pilot.hop,'atom_json') as write:
            self.assertEqual(pilot.aligned_search_epoch(480.,360.),(100.,460.))
            record=write.call_args.args[1]
            self.assertEqual(record['cooling_start_monotonic'],360.)
            self.assertEqual(record['finalization_reserve_seconds'],20.)
            with self.assertRaises(TimeoutError):pilot.aligned_search_epoch(479.99,360.)
            self.assertEqual(write.call_count,1)

    def test_protected_retention_and_fixed_queue_budget(self):
        store=object.__new__(pilot.BoundedPacketStore)
        store.entries=[];store.max_packets=20;store.used=0;store.reserve=100;store.max_bytes=1000
        with patch.object(pilot,'tree_bytes',return_value=pilot.PROTECTED_SEARCH_BYTES-1):
            self.assertTrue(store.can_begin())
        with patch.object(pilot,'tree_bytes',return_value=pilot.PROTECTED_SEARCH_BYTES):
            self.assertFalse(store.can_begin());self.assertTrue(store.protected_limit_hit)
        self.assertEqual(sorted(n for q in pilot.QUEUES for n in q),sorted(pilot.CASES))
        self.assertTrue(all(len(q)==6 for q in pilot.QUEUES))
        self.assertEqual(6*(45+10+360+20+3+145),3498)
        self.assertEqual(pilot.RAW_BYTES*12,9*1024**3)
        self.assertEqual(pilot.TOTAL_BYTES-pilot.RAW_BYTES*12,3*1024**3)
        with patch.object(pilot.time,'monotonic',return_value=100.),patch.object(pilot.subprocess,'Popen') as spawn:
            result=pilot.run_child(Path('.'),'search',380.,470.,0)
            self.assertEqual(result['status'],'skipped_insufficient_fixed_budget');spawn.assert_not_called()

    def test_generated_source_has_only_reviewed_numeric_backend(self):
        source=pilot.generated_search_source();compile(source,'generated','exec')
        self.assertIn('quenched,quench_record=fused_quench(proposal_tensor,sides)',source)
        self.assertIn("proposal_metrics=host_metrics(physical_energy(quenched,sides))",source)
        self.assertIn('accepted,rule=acceptance(',source)
        self.assertIn('store.complete(packet,arrays,dict(metadata,event=event))',source)
        self.assertIn('absolute_deadline=deadline',source)
        self.assertIn('deadline-tail_guard',source)
        self.assertNotIn('deadline-150.',source)
        self.assertNotIn('quench32',source)
        self.assertEqual(hashlib.sha256(Path(pilot.prior.__file__).read_bytes()).hexdigest(),pilot.PRIOR_SHA)


if __name__=='__main__':unittest.main()
