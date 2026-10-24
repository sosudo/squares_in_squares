"""Committed-state lineage and bounded finish retention, without optimization."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import fq_restart_hop_finish as finish


class RestartFinishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root/'fq'
        self.binary.write_bytes(b'nonexecutable test fixture; never run')
        self.pin = patch.object(finish, 'BINARY_SHA', finish._sha(self.binary))
        self.pin.start(); self.addCleanup(self.pin.stop)
        self.design = [dict(chain=i, arm=arm, delta=delta, n=3,
                            source_key='source', side=3.-delta)
                       for i, (arm, delta) in enumerate(
                           [(arm, delta) for delta in finish.DELTAS
                            for arm in finish.ARMS for _ in range(2)])]
        self.best = np.arange(8*3*3, dtype=float).reshape(8, 3, 3)/100
        self.arrays = dict(current_after=self.best+1, best_after=self.best,
                          sides=np.array([r['side'] for r in self.design]),
                          next_energy=np.full(8, 99.),
                          best_energy_after=np.array([2., 1., 1., 1., 4., 3., 2., 1.]))
        self.case = dict(n=3, source_key='source', reference_side='3.0',
                         binary_path=str(self.binary), baseline_sha256='frozen-test-baseline')

    def write_committed(self, *, metadata=True, wrong_hash=False, mismatch=False):
        (self.root/'chain-design.json').write_text(json.dumps(self.design))
        values = dict(self.arrays)
        if metadata:
            hashes = {name: hashlib.sha256(q.tobytes()).hexdigest()
                      for name, q in values.items()}
            if wrong_hash: hashes['best_after'] = 'wrong'
            info = dict(status='completed', design=self.design, array_sha256=hashes)
            values['metadata_json'] = np.frombuffer(json.dumps(info).encode(), dtype=np.uint8)
        packet = self.root/'packet.npz'; np.savez(packet, **values)
        final = dict(self.arrays)
        if mismatch: final['best_after'] = self.best+0.01
        np.savez(self.root/'final-current-best.npz', **final)
        (self.root/'raw-index.json').write_text(json.dumps(dict(packets=[dict(
            path='packet.npz', sha256=finish._sha(packet), status='completed')])))

    def test_fixed_slots_select_committed_best_and_interleave_equal_budgets(self):
        self.write_committed(); selected = []
        def no_native(out, slot, pose, case, binary, deadline):
            selected.append((dict(slot), pose.copy()))
            return dict(slot, status='mocked_no_optimizer'), None
        with patch.object(finish, '_finish_slot', side_effect=no_native):
            summary = finish.finish_case(self.root, self.case, time.monotonic()+20)
        self.assertEqual([row[0]['chain'] for row in selected], [1, 2, 5, 7])
        self.assertEqual([row[0]['arm'] for row in selected], ['control', 'reset']*2)
        for slot, pose in selected:
            self.assertTrue(np.array_equal(pose, self.best[slot['chain']]))
            self.assertFalse(np.array_equal(pose, self.arrays['current_after'][slot['chain']]))
        self.assertEqual(summary['certified'], 0)
        self.assertEqual(summary['per_arm']['control']['selected_slots'], 2)
        self.assertEqual(summary['per_arm']['reset']['selected_slots'], 2)

    def test_changed_committed_array_hash_is_rejected_before_native(self):
        self.write_committed(wrong_hash=True)
        with patch.object(finish, '_finish_slot') as native:
            with self.assertRaises(ValueError):
                finish.finish_case(self.root, self.case, time.monotonic()+20)
            native.assert_not_called()

    def test_missing_commit_metadata_is_rejected_before_native(self):
        self.write_committed(metadata=False)
        with patch.object(finish, '_finish_slot') as native:
            with self.assertRaises((ValueError, KeyError)):
                finish.finish_case(self.root, self.case, time.monotonic()+20)
            native.assert_not_called()

    def test_final_best_must_equal_last_completed_packet(self):
        self.write_committed(mismatch=True)
        with patch.object(finish, '_finish_slot') as native:
            with self.assertRaisesRegex(ValueError, 'differs_from_last_committed'):
                finish.finish_case(self.root, self.case, time.monotonic()+20)
            native.assert_not_called()

    def test_deadline_keeps_exact_selected_state_without_native(self):
        slot = dict(slot=0, arm='control', delta=.002, chain=1)
        with patch.object(finish, '_recorded_native') as native:
            record, pose = finish._finish_slot(self.root, slot, self.best[1], self.case,
                                              self.binary, time.monotonic()-1)
        native.assert_not_called(); self.assertIsNone(pose)
        self.assertEqual(record['status'], 'deadline_before_native')
        self.assertTrue(np.array_equal(np.load(record['selected_archive'])['pose'], self.best[1]))

    def test_certificate_timeout_preserves_native_text_raw_and_selected(self):
        slot = dict(slot=0, arm='control', delta=.002, chain=1)
        returned = np.array([[.5, .5, 0.], [1.5, .5, 0.], [.5, 1.5, 0.]])
        def fake_native(command, base, timeout):
            self.assertLessEqual(timeout, 12.)
            base.with_suffix('.out').write_text('3 2\n.5 .5 0\n1.5 .5 0\n.5 1.5 0\n')
            base.with_suffix('.stdout').write_text('retained stdout')
            base.with_suffix('.stderr').write_text('retained stderr')
            return dict(native_status='returned', returncode=0)
        def timeout_after_retention(pose):
            records = list(self.root.glob('*.record.json'))
            record = json.loads(records[0].read_text())
            self.assertEqual(record['status'], 'saved_native_before_certificate')
            self.assertTrue(Path(record['native_output_path']).exists())
            self.assertTrue(Path(record['raw_returned']['path']).exists())
            raise finish.CertificateDeadline()
        with patch.object(finish, '_recorded_native', side_effect=fake_native), \
             patch.object(finish.fq, 'decode', return_value=returned), \
             patch.object(finish, 'full_certificate', side_effect=timeout_after_retention):
            record, pose = finish._finish_slot(self.root, slot, self.best[1], self.case,
                                              self.binary, time.monotonic()+20)
        self.assertEqual(record['status'], 'saved_return_certificate_timeout')
        self.assertIsNone(pose)
        self.assertTrue(np.array_equal(np.load(record['selected_archive'])['pose'], self.best[1]))
        self.assertTrue(np.array_equal(np.load(record['raw_returned']['path'])['pose'], returned))


if __name__ == '__main__':
    unittest.main()
