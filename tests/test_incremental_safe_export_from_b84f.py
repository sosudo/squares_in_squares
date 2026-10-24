"""Isolated unchanged-builder binding and required competition metadata."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build_incremental_safe_export_from_b84f as wrapper


class B84ParentWrapperTests(unittest.TestCase):
    def test_exact_code_object_and_isolated_globals_survive_failed_build(self):
        original = dict(wrapper.base.build.__globals__)
        build = wrapper.isolated_builder()
        self.assertIs(build.__code__, wrapper.base.build.__code__)
        self.assertIsNot(build.__globals__, wrapper.base.build.__globals__)
        self.assertEqual(build.__defaults__, wrapper.base.build.__defaults__)
        self.assertEqual(build.__closure__, wrapper.base.build.__closure__)
        self.assertEqual(build.__globals__['PARENT_REF'], wrapper.PARENT_REF)
        self.assertEqual(build.__globals__['PARENT_SHA'], wrapper.PARENT_SHA)
        self.assertIs(build.__globals__['notebook_metadata'], wrapper.notebook_metadata)
        def fail(*args): raise RuntimeError('Deliberate validation failure')
        build.__globals__['validate_proofs'] = fail
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(out=Path(tmp)/'new', parent='parent', parent_report='report',
                                   parent_transport='transport')
            with self.assertRaises(RuntimeError): build(args)
        self.assertEqual(wrapper.base.build.__globals__, original)

    def test_exact_byte_pin_rejects_changed_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'parent'; path.write_bytes(b'certified\r\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(wrapper.checked_bytes(path, digest), b'certified\r\n')
            path.write_bytes(b'certified\n')
            with self.assertRaises(ValueError): wrapper.checked_bytes(path, digest)

    def test_missing_attachment_or_incomplete_inherited_notices_rejected(self):
        parent = dict(additional_source_provenance={'notice':'full license\r\n'},
                      additional_source_provenance_sha256='bound-parent-notices')
        completion = dict(version=1, ref=wrapper.PARENT_REF.rsplit('/',1)[0],
            output_sha256=wrapper.PARENT_SHA, is_private=True, status='complete',
            competition_sources=['squares-in-squares'], enable_gpu=False,
            enable_tpu=False, enable_internet=False)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root/wrapper.PARENT_JOB; folder.mkdir(parents=True)
            parent_path = folder/'export_manifest.json'; parent_path.write_text(json.dumps(parent))
            completion_path = folder/'completion-proof.json'
            additional = root/'additional.json'
            inherited = dict(inherited_parent_additional_provenance=parent['additional_source_provenance'],
                inherited_parent_additional_provenance_sha256=parent['additional_source_provenance_sha256'])
            additional.write_text(json.dumps(inherited))
            def pins():
                completion_path.write_text(json.dumps(completion))
                return {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in (parent_path,completion_path)}
            with patch.object(wrapper, 'ROOT', root), patch.object(wrapper, 'PINS', pins()):
                wrapper.verify_parent_and_inheritance(additional)
                inherited['inherited_parent_additional_provenance']['notice']='truncated'
                additional.write_text(json.dumps(inherited))
                with self.assertRaises(ValueError): wrapper.verify_parent_and_inheritance(additional)
            completion['competition_sources'] = []
            with patch.object(wrapper, 'ROOT', root), patch.object(wrapper, 'PINS', pins()):
                with self.assertRaisesRegex(ValueError, 'competition-attached'):
                    wrapper.verify_parent_and_inheritance(additional)

    def test_first_launch_attaches_exact_competition_and_parent(self):
        metadata = wrapper.notebook_metadata('owner/new-export')
        self.assertEqual(metadata['competition_sources'], ['squares-in-squares'])
        self.assertEqual(metadata['kernel_sources'], [wrapper.PARENT_REF])
        self.assertTrue(metadata['is_private'])
        self.assertFalse(any(metadata[k] for k in ('enable_gpu','enable_tpu','enable_internet')))


if __name__ == '__main__': unittest.main()
