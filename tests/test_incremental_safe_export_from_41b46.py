import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build_incremental_safe_export_from_41b46 as wrapper


class ParentWrapperTests(unittest.TestCase):
    def test_exact_parent_guard_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'parent'; p.write_bytes(b'exact\r\n')
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(wrapper.checked_bytes(p, digest), b'exact\r\n')
            p.write_bytes(b'exact\n')
            with self.assertRaises(ValueError): wrapper.checked_bytes(p, digest)

    def test_complete_notice_inheritance_required(self):
        parent = {'additional_source_provenance': {'notice': 'credit\r\n'},
                  'additional_source_provenance_sha256': 'bound'}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'additional.json'
            additional = {'inherited_parent_additional_provenance': parent['additional_source_provenance'],
                          'inherited_parent_additional_provenance_sha256': 'bound'}
            p.write_text(json.dumps(additional))
            with patch.object(wrapper, 'checked_bytes', return_value=json.dumps(parent).encode()):
                wrapper.verify_parent_and_inheritance(p)
                additional['inherited_parent_additional_provenance']['notice'] = 'credit\n'
                p.write_text(json.dumps(additional))
                with self.assertRaises(ValueError): wrapper.verify_parent_and_inheritance(p)

    def test_only_parent_constants_change_and_restore_on_failure(self):
        old = wrapper.base.PARENT_REF, wrapper.base.PARENT_SHA
        args = SimpleNamespace(additional_provenance=Path('unused'))
        def fail(actual):
            self.assertIs(actual, args)
            self.assertEqual((wrapper.base.PARENT_REF, wrapper.base.PARENT_SHA),
                             (wrapper.PARENT_REF, wrapper.PARENT_SHA))
            self.assertEqual(actual.parent_export_job, wrapper.ROOT/wrapper.PARENT_JOB)
            raise RuntimeError('Deliberate build failure')
        with patch.object(wrapper, 'verify_parent_and_inheritance'), patch.object(wrapper.base, 'build', side_effect=fail):
            with self.assertRaises(RuntimeError): wrapper.build(args)
        self.assertEqual((wrapper.base.PARENT_REF, wrapper.base.PARENT_SHA), old)


if __name__ == '__main__': unittest.main()
