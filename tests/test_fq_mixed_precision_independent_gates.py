"""Failure isolation for the real diagnostic driver, without CUDA or optimization."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
import fq_mixed_precision_adapter as adapter
import fq_mixed_precision_controls as controls
import fq_mixed_precision_diagnostic as driver


class IndependentGateTests(unittest.TestCase):
    def test_fp32_failure_preserves_fp64_evidence_and_stops_all_gpu_calls(self):
        for failure_at in ('constructor', 'control'):
            with self.subTest(failure_at=failure_at), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                out = root / 'out'
                source = root / 'source.cu'
                source.write_text('mock source; no CUDA execution')
                fixture_path = root / 'fixture.npz'
                fixture_path.write_bytes(b'mock fixture; loader replaced explicitly')
                config = dict(
                    work_seconds=240, protocol=dict(
                        arms={k: [list(v) for v in values] for k, values in driver.ARMS.items()},
                        repeats=3, order='ABC/BCA/CAB', phase2_fresh_optimizer_state=True,
                        original_fp64_boxes_in_phase2=True),
                    compiler_options=list(adapter.OPTIONS), native_finish=False,
                    search_campaign=False, corrected_fp64_cuda_path=str(source),
                    corrected_fp64_cuda_sha256=driver.digest(source),
                    inputs_sha256=driver.digest(fixture_path), runtime_priority=['mock'],
                    occupancy=dict(enabled=True, steps=2000, batch_sizes=[32, 64, 128],
                                   fixture_key='n803_early'))
                config_path = root / 'config.json'
                config_path.write_text(json.dumps(config))
                fixtures = []
                for n, epoch in ((803, 'early'), (803, 'late'), (861, 'early'), (861, 'late')):
                    # The loader is mocked: tiny arrays exercise scheduling/persistence,
                    # not the independently tested full-count numerical controls.
                    poses = np.zeros((32, 3, 3), dtype=np.float64)
                    sides = np.full(32, 30., dtype=np.float64)
                    boxes = np.column_stack((sides, sides))
                    fixtures.append(dict(key=f'n{n}_{epoch}', n=n, epoch=epoch,
                        poses=poses, original_sides=sides, boxes=boxes, source_packet={},
                        pose_sha256=hashlib.sha256(poses.tobytes()).hexdigest(),
                        boxes_sha256=hashlib.sha256(sides.tobytes()).hexdigest(),
                        expanded_boxes_sha256=hashlib.sha256(boxes.tobytes()).hexdigest()))

                state = dict(poisoned=False, calls=[], failure_snapshot=None)

                def gpu_call(name, result=None):
                    if state['poisoned']:
                        raise AssertionError('GPU call after FP32 failure: ' + name)
                    state['calls'].append(name)
                    return result

                def fail():
                    snapshot = json.loads((out / 'benchmark-report.json').read_text())
                    self.assertEqual([r['batch'] for r in snapshot['occupancy']], [32, 64, 128])
                    self.assertTrue(json.loads((out / 'fp64-preflight.json').read_text())['passed'])
                    state['failure_snapshot'] = snapshot
                    state['poisoned'] = True
                    raise RuntimeError('simulated FP32 context failure')

                class Event:
                    def __init__(self): gpu_call('event_create')
                    def record(self): gpu_call('event_record')
                    def synchronize(self): gpu_call('event_synchronize')

                class Solver:
                    def __init__(self, cp, source, precision):
                        gpu_call('construct_' + precision)
                        if precision == 'fp32' and failure_at == 'constructor': fail()
                        self.precision = precision
                        self.source = self.compiled_source = source
                        self.audit = dict(precision=precision)
                        self.module = SimpleNamespace(get_function=lambda name: gpu_call('compile_' + name))

                    def buffer_inventory(self): return {'mock': self.precision}

                    def energy(self, poses, boxes):
                        gpu_call('energy_' + self.precision)
                        return np.zeros((len(poses), 2)), np.zeros_like(poses)

                    def quench(self, poses, boxes, steps):
                        gpu_call('quench_' + self.precision)
                        return np.array(poses, copy=True), np.zeros((len(poses), 3))

                cp = SimpleNamespace(
                    float64=np.float64,
                    asnumpy=lambda a: gpu_call('asnumpy', np.asarray(a)),
                    get_default_memory_pool=lambda: gpu_call('memory_pool', SimpleNamespace(
                        used_bytes=lambda: gpu_call('memory_used', 0),
                        total_bytes=lambda: gpu_call('memory_total', 0))),
                    cuda=SimpleNamespace(
                        Device=lambda index: SimpleNamespace(use=lambda: gpu_call('device_use')),
                        Event=Event,
                        get_current_stream=lambda: gpu_call('get_stream', SimpleNamespace(
                            synchronize=lambda: gpu_call('stream_synchronize'))),
                        get_elapsed_time=lambda a, b: gpu_call('elapsed_time', .1),
                        runtime=SimpleNamespace(memGetInfo=lambda: gpu_call('mem_info', (1000, 2000)))))
                torch = SimpleNamespace(set_num_threads=lambda n: None, set_num_interop_threads=lambda n: None,
                    cuda=SimpleNamespace(set_device=lambda n: gpu_call('torch_device'),
                        is_available=lambda: gpu_call('cuda_available', True),
                        get_device_name=lambda n: gpu_call('device_name', 'mock T4'),
                        reset_peak_memory_stats=lambda: gpu_call('reset_peak_memory_stats'),
                        max_memory_allocated=lambda: gpu_call('max_memory_allocated', 0),
                        max_memory_reserved=lambda: gpu_call('max_memory_reserved', 0),
                        synchronize=lambda: gpu_call('torch_synchronize')))

                def fp64_control(cp, torch, solver, rows, retain):
                    gpu_call('fp64_control')
                    retain('fp64-control-proof', dict(poses=rows[0]['poses']), dict(mock=True))
                    return dict(passed=True, mock_only=True)

                def fp32_control(*args, **kwargs):
                    gpu_call('fp32_control')
                    fail()

                def physical(torch, q, boxes):
                    gpu_call('physical_metrics')
                    return dict(energy=np.zeros(len(q)))

                with patch.dict(sys.modules, {'cupy': cp, 'torch': torch}), \
                        patch.object(adapter, 'Solver', Solver), \
                        patch.object(adapter, 'FP64_SHA', driver.digest(source)), \
                        patch.object(driver, 'load_fixtures', return_value=(fixtures, fixture_path)), \
                        patch.object(controls, 'run_fp64', side_effect=fp64_control), \
                        patch.object(controls, 'run', side_effect=fp32_control), \
                        patch.object(controls, 'physical_metrics', side_effect=physical):
                    began = time.monotonic()
                    driver.run(config_path, out, began + 280, began)

                report = json.loads((out / 'benchmark-report.json').read_text())
                self.assertEqual(report['status'], 'fp32_not_passed_fp64_occupancy_preserved')
                self.assertTrue(report['fp64_controls_passed'])
                self.assertFalse(report['fp32_controls_passed'])
                self.assertEqual(report['completed_primary_pipelines'], 0)
                self.assertEqual(report['primary'], [])
                self.assertEqual(len(report['omitted']), 36)
                self.assertEqual({r['reason'] for r in report['omitted']},
                                 {'fp32_controls_not_passed_no_further_cuda'})
                self.assertEqual(report['occupancy'], state['failure_snapshot']['occupancy'])
                self.assertEqual(state['calls'].count('quench_fp64'), 3)
                self.assertEqual(state['calls'].count('physical_metrics'), 3)
                self.assertNotIn('quench_fp32', state['calls'])
                index = json.loads((out / 'array-index.json').read_text())
                self.assertEqual(len(index), 8)  # four fixtures, one control, three occupancy arrays
                for record in index:
                    self.assertEqual(driver.digest(record['path']), record['sha256'])
                self.assertEqual(driver.digest(out / 'array-index.json'), report['array_index_sha256'])


if __name__ == '__main__': unittest.main()
