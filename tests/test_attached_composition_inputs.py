import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from attached_composition_inputs import resolve_inputs, validate_manifest


class AttachedCompositionTests(unittest.TestCase):
    def manifest(self, payload=b'certified CSV'):
        return {'schema_version': 1,
                'baseline': {'kernel': 'owner/export/3', 'file': 'submission.csv',
                             'sha256': hashlib.sha256(payload).hexdigest()},
                'gadgets': {'guarded': {'kernel': 'owner/worker/1', 'file': 'artifacts/gadgets.npz',
                                        'sha256': hashlib.sha256(b'checkpoint').hexdigest()}},
                'groups': {'control': [], 'guarded': ['guarded']}}

    def test_resolves_hashes_across_mount_layouts_and_keeps_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'export').mkdir(); (root/'new-layout'/'worker'/'artifacts').mkdir(parents=True)
            (root/'export'/'submission.csv').write_bytes(b'certified CSV')
            # A different notebook with the same filename must not be selected.
            (root/'submission.csv').write_bytes(b'unrelated CSV')
            (root/'new-layout'/'worker'/'artifacts'/'gadgets.npz').write_bytes(b'checkpoint')
            resolved = resolve_inputs(self.manifest(), root)
            self.assertEqual(resolved['inputs']['baseline']['path'], str(root/'export'/'submission.csv'))
            self.assertEqual(resolved['groups'], {'control': [], 'guarded': ['guarded']})

    def test_changed_bytes_reject_before_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'submission.csv').write_bytes(b'tampered CSV')
            with self.assertRaisesRegex(ValueError, 'No attachment matches'):
                resolve_inputs(self.manifest(), root)

    def test_requires_pinned_versions_and_known_donors(self):
        manifest = self.manifest(); manifest['baseline']['kernel'] = 'owner/export'
        with self.assertRaisesRegex(ValueError, 'expected numeric version'):
            validate_manifest(manifest)
        manifest = self.manifest(); manifest['groups']['bad'] = ['missing']
        with self.assertRaisesRegex(ValueError, 'unknown donor'):
            validate_manifest(manifest)

    def test_mixes_verified_notebook_and_embedded_donors(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'mount').mkdir();(root/'bundle').mkdir()
            (root/'mount'/'submission.csv').write_bytes(b'certified CSV')
            (root/'bundle'/'refill.npz').write_bytes(b'checkpoint')
            manifest=self.manifest()
            record=manifest['gadgets']['guarded'];record.pop('kernel');record['embedded_path']='refill.npz'
            resolved=resolve_inputs(manifest,root/'mount',root/'bundle')
            self.assertIsNone(resolved['inputs']['guarded']['kernel'])
            self.assertEqual(resolved['inputs']['guarded']['sha256'],record['sha256'])
            (root/'bundle'/'refill.npz').write_bytes(b'changed donor')
            with self.assertRaisesRegex(ValueError,'Embedded donor filename/hash mismatch'):
                resolve_inputs(manifest,root/'mount',root/'bundle')


if __name__ == '__main__':
    unittest.main()
