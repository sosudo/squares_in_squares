"""CPU-only rectangle/square admission and interrupted-certificate controls."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

try:
    import torch
except ImportError:
    torch = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
if torch is not None:
    import fq_rect_wall_pilot as pilot
    from fq_coherent_clusters import Deadline


@unittest.skipIf(torch is None, 'Optional Torch import dependency unavailable')
class RectangularRecoveryControls(unittest.TestCase):
    @contextmanager
    def fixture(self):
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path('job_manifest.json').write_text(json.dumps({'baseline335': {'side': '18.8228756555792035'}}))
                config = dict(target_side=18.807, certification_seconds=10, certification_max_candidates=1)
                # Synthetic protocol data, never used as geometric witnesses.
                poses = np.zeros((32, 335, 3), dtype=np.float64)
                store = pilot.PacketStore('raw-wall', 32, 335, 4, 32*1024**2)
                with mock.patch.object(pilot, 'load_inputs', return_value=(config, {})):
                    yield store, poses
            finally:
                os.chdir(old)

    def complete(self, store, poses, stage, final):
        box = [18.807, 18.807] if final else [19.2, 18.42204421875]
        boxes = np.tile(box, (32, 1))
        metadata = dict(stage=stage, final_square=final, verified=False)
        number = store.begin(dict(prior_output=poses, stage_input=poses, boxes=boxes), metadata)
        return store.complete(number, dict(prior_output=poses, stage_input=poses,
            stage_output=poses, boxes=boxes, physical_energy=np.ones(32)), metadata)

    def test_nonsquare_and_pending_square_never_reach_admission(self):
        with self.fixture() as (store, poses):
            self.complete(store, poses, 31, False)
            store.begin(dict(prior_output=poses, stage_input=poses,
                boxes=np.full((32, 2), 18.807)), dict(stage=32, final_square=True, verified=False))
            with mock.patch.object(pilot, 'legalize') as rounding, mock.patch.object(pilot, 'bounded_certificate') as gate:
                result = pilot.recover_and_certify()
            rounding.assert_not_called()
            gate.assert_not_called()
            self.assertFalse(result['complete_path'])
            self.assertEqual(result['pending_packets'], 1)
            self.assertEqual(result['candidate_count'], 0)
            with np.load('pending-square-candidates.npz') as archive:
                self.assertEqual(archive.files, [])

    def test_certificate_deadline_preserves_pending_exact_geometry(self):
        with self.fixture() as (store, poses):
            self.complete(store, poses, 32, True)
            with mock.patch.object(pilot, 'legalize', side_effect=lambda q: q.copy()), \
                 mock.patch.object(pilot, 'side', return_value=18.8), \
                 mock.patch.object(pilot, 'bounded_certificate', side_effect=Deadline):
                result = pilot.recover_and_certify()
            self.assertEqual(result['candidate_count'], 1)
            self.assertEqual(result['certification_attempts'], 1)
            self.assertEqual(result['certified_candidates'], [])
            self.assertEqual(result['certification_failures'][0]['error_type'], 'Deadline')
            pending = json.loads(Path('pending-square-candidates.json').read_text())
            self.assertFalse(pending['verified'])
            with np.load('pending-square-candidates.npz') as archive:
                self.assertEqual(len(archive.files), 1)
                np.testing.assert_array_equal(archive[archive.files[0]], poses[0])

    def test_rehashed_archive_with_changed_array_is_rejected(self):
        with self.fixture() as (store, poses):
            entry = self.complete(store, poses, 32, True)
            path = Path(entry['path'])
            with np.load(path) as archive:
                contents = {key: archive[key].copy() for key in archive.files}
            contents['stage_output'][0, -1, 0] = .125
            np.savez(path, **contents)
            index = json.loads(Path('raw-index.json').read_text())
            index['packets'][0]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            index['packets'][0]['bytes'] = path.stat().st_size
            Path('raw-index.json').write_text(json.dumps(index))
            with mock.patch.object(pilot, 'bounded_certificate') as gate:
                with self.assertRaises(AssertionError):
                    pilot.recover_and_certify()
            gate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
