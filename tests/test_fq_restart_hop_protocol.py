"""Paired randomness/reset/commit controls; CPU only, no numerical optimizer."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

try:
    import torch
except ImportError:
    torch = None
if torch is not None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
    import fq_restart_hop_pilot as pilot


@unittest.skipIf(torch is None, 'Optional Torch CPU protocol control')
class RestartProtocolTests(unittest.TestCase):
    def test_design_pairs_same_starts_boxes_temperatures_amplitudes(self):
        for n in (453, 693):
            rows = pilot.design(n, '29.8', 'exact_source')
            self.assertEqual(len(rows), 32)
            for i in range(16):
                a, b = rows[i], rows[i+16]
                self.assertEqual((a['arm'], b['arm']), ('control', 'reset'))
                self.assertEqual({k:v for k,v in a.items() if k not in ('chain','arm')},
                                 {k:v for k,v in b.items() if k not in ('chain','arm')})
            for arm in ('control', 'reset'):
                selected = [r for r in rows if r['arm'] == arm]
                self.assertEqual(sum(r['temperature'] == .3 for r in selected), 8)
                self.assertEqual(sum(r['temperature'] == 1. for r in selected), 4)
                self.assertEqual(sum(r['temperature'] == 3. for r in selected), 4)

    def test_variable_mutation_draw_counts_cannot_shift_acceptance_or_next_round(self):
        streams = pilot.random_streams(123, 4)
        for i in range(16):
            self.assertTrue(np.array_equal(streams[i].normal(size=100), streams[i+16].normal(size=100)))
        before = pilot.acceptance_uniforms(123, 4)
        streams[0].normal(size=10000)
        self.assertTrue(np.array_equal(before, pilot.acceptance_uniforms(123, 4)))
        self.assertTrue(np.array_equal(before[:16], before[16:]))
        self.assertFalse(np.array_equal(before, pilot.acceptance_uniforms(123, 5)))
        next_streams = pilot.random_streams(123, 5)
        self.assertTrue(np.array_equal(next_streams[0].random(100), next_streams[16].random(100)))

    def test_only_hot_treatment_resets_and_cooling_is_then_persistent(self):
        rows = pilot.design(453, 22., 'source')
        eligible = np.array([r['arm']=='reset' and r['temperature']>.3 for r in rows])
        for rounds in (0, 1, 15, 17):
            self.assertFalse(pilot.reset_mask(rows, rounds, False, False, False, -1)['mask'].any())
        self.assertFalse(pilot.reset_mask(rows, 16, False, True, False, -1)['mask'].any())
        self.assertTrue(np.array_equal(pilot.reset_mask(rows, 16, False, False, False, -1)['mask'], eligible))
        self.assertFalse(pilot.reset_mask(rows, 16, False, False, False, 16)['mask'].any())
        self.assertTrue(np.array_equal(pilot.reset_mask(rows, 19, True, False, False, -1)['mask'], eligible))
        self.assertFalse(pilot.reset_mask(rows, 32, True, False, True, -1)['mask'].any())
        base = np.array([.3, 1., 3.])
        self.assertTrue(np.array_equal(pilot.temperature_schedule(base, 600., 449.99)[0], base))
        self.assertTrue(np.array_equal(pilot.temperature_schedule(base, 600., 450.)[0], base*.1))

    def test_largest_seven_pose_packet_fits_reserved_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd(); os.chdir(tmp)
            try:
                store = pilot.RestartPacketStore('packets', 32, 693, 2, 32*1024**2)
                poses = np.zeros((32, 693, 3), dtype=np.float64)
                names = ('current_before_reset', 'current_before', 'proposal_input', 'best_before',
                         'proposal_quenched', 'current_after', 'best_after')
                arrays = {name: poses.copy() for name in names}
                index = store.begin({name:arrays[name] for name in names[:4]}, dict(test=True))
                entry = store.complete(index, arrays, dict(test=True))
                self.assertLessEqual(entry['bytes'], store.reserve//2)
                with np.load(entry['path'], allow_pickle=False) as z:
                    hashes = json.loads(z['metadata_json'].tobytes())['array_sha256']
                    for name in names:
                        self.assertEqual(hashlib.sha256(z[name].tobytes()).hexdigest(), hashes[name])
            finally:
                os.chdir(previous)

    def test_actual_generated_loop_retains_and_commits_own_best_resets(self):
        # Run the actual generated controller with a synthetic CPU energy oracle
        # and identity quench. This tests protocol ordering, not GPU physics.
        clock = [0.]; calls = [0]
        class TorchCpu:
            cuda = SimpleNamespace(is_available=lambda:True, get_device_name=lambda *a:'test T4')
            def __getattr__(self, name): return getattr(torch, name)
            @staticmethod
            def device(*args): return torch.device('cpu')
            @staticmethod
            def set_num_threads(*args): pass
            @staticmethod
            def set_num_interop_threads(*args): pass
        def energy(q, sides):
            return dict(energy=q[:,0,0].clone(), per_square=torch.ones(q.shape[:2], dtype=q.dtype))
        def mutate(q, per_square, rng, amplitude):
            q = q.copy(); q[0,0] += 1
            return q, dict(operator='test_translation', changed_count=1, selected_count=1)
        def quench(q, sides):
            result = q.clone(); clock[0] += 10.; calls[0] += 1
            if calls[0] == 1:
                result[:,0,0] = 9.+torch.arange(32, dtype=torch.float64)/100
            return result, dict(test_identity_quench=True)
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd(); os.chdir(tmp)
            try:
                pose = np.array([[10., .5, 0.], [1.5, .5, 0.]])
                np.savez('pilot-inputs.npz', source=pose)
                fixture = dict(n=2, inputs_sha256=pilot.hop.digest('pilot-inputs.npz'),
                    exploratory_sources=['source'], arrays={'source':dict(shape=[2,3], dtype=pose.dtype.str,
                    sha256=hashlib.sha256(pose.tobytes()).hexdigest())})
                for path, value in [('pilot-config.json', fixture),
                    ('case-config.json', dict(n=2, reference_side=20., source_key='source')),
                    ('hop-config.json', dict(search_seconds=600, seed=1, max_packets=100, max_bytes=64*1024**2)),
                    ('preflight.json', dict(passed=True, backend='restart_fused_fp64'))]:
                    Path(path).write_text(json.dumps(value))
                namespace = dict(vars(pilot.hop))
                namespace.update(torch=TorchCpu(), time=SimpleNamespace(monotonic=lambda:clock[0],
                    sleep=lambda dt:clock.__setitem__(0, clock[0]+dt)), physical_energy=energy,
                    mutate=mutate, fused_quench=quench, PacketStore=pilot.RestartPacketStore,
                    chain_design=pilot.chain_design, reset_mask=pilot.reset_mask,
                    random_streams=pilot.random_streams, temperature_schedule=pilot.temperature_schedule,
                    acceptance_uniforms=lambda *a:np.full(32, np.exp(-100.)))
                exec(compile(pilot.generated_search_source(), '<actual loop CPU protocol control>', 'exec'), namespace)
                with redirect_stdout(io.StringIO()): namespace['search_main'](600.)
                entries = json.loads(Path('raw-index.json').read_text())['packets']
                periodic = []; crossings = []
                for entry in entries:
                    with np.load(entry['path'], allow_pickle=False) as z:
                        event = json.loads(z['metadata_json'].tobytes())['event']
                        pre = np.array(event['before_reset']['mask']); post = np.array(event['after_reset']['mask'])
                        self.assertTrue(np.array_equal(z['current_before'], np.where(
                            pre[:,None,None], z['best_before'], z['current_before_reset'])))
                        mh = np.where(z['accepted'][:,None,None], z['proposal_quenched'], z['current_before'])
                        self.assertTrue(np.array_equal(z['current_after'], np.where(
                            post[:,None,None], z['best_after'], mh)))
                        self.assertTrue(np.array_equal(z['next_energy'], z['current_after'][:,0,0]))
                        if event['before_reset']['periodic']: periodic.append(event['round'])
                        if event['after_reset']['cooling']: crossings.append(event['round'])
                        if event['temperature_phase']=='cool': self.assertFalse(event['before_reset']['periodic'])
                self.assertEqual(periodic, [16,32])
                self.assertEqual(len(crossings), 1)
                self.assertEqual(len(entries), 60)
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
