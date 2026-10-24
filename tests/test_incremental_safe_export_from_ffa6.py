import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build_incremental_safe_export_from_ffa6 as wrapper


class Ffa6ParentTests(unittest.TestCase):
    def test_exact_version2_parent_gate_and_isolated_globals(self):
        original = wrapper.base.PARENT_REF, wrapper.base.PARENT_SHA
        build,source = wrapper.adapted_builder()
        self.assertEqual(source.count("completion['version']==2"),1)
        self.assertEqual((wrapper.base.PARENT_REF,wrapper.base.PARENT_SHA),original)
        self.assertEqual(build.__globals__['RUNTIME'],wrapper.base.RUNTIME)
        self.assertEqual(build.__globals__['COMPRESSED_MANIFEST_RUNTIME'],wrapper.base.COMPRESSED_MANIFEST_RUNTIME)
        class PastParentGate(Exception): pass
        build.__globals__['validate_proofs'] = lambda *args:(b'parent',{}, {})
        build.__globals__['PARENT_SHA'] = hashlib.sha256(b'parent').hexdigest()
        build.__globals__['runtime_namespace'] = lambda:(_ for _ in ()).throw(PastParentGate())
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            completion = dict(output_sha256=hashlib.sha256(b'parent').hexdigest(),
                ref=wrapper.PARENT_REF.rsplit('/',1)[0],version=2,output_file='submission.csv',status='complete',is_private=True)
            args = SimpleNamespace(out=tmp/'new',parent=None,parent_report=None,parent_transport=None,
                target=None,target_report=None,target_transport=None,parent_export_job=tmp)
            (tmp/'completion-proof.json').write_text(json.dumps(completion))
            with self.assertRaises(PastParentGate): build(args)
            completion['version'] = 1
            (tmp/'completion-proof.json').write_text(json.dumps(completion))
            with self.assertRaisesRegex(ValueError,'verified private parent'): build(args)

    def test_initial_metadata_attaches_competition_and_exact_parent(self):
        slug='sos54352/squares-portfolio-b84f2ff20f3e-incremental'
        metadata=wrapper.notebook_metadata(slug)
        self.assertEqual(metadata['competition_sources'],['squares-in-squares'])
        self.assertEqual(metadata['kernel_sources'],[wrapper.PARENT_REF])
        self.assertEqual(metadata['title'].replace(' ','-'),slug.split('/')[-1])
        self.assertTrue(metadata['is_private'])
        self.assertFalse(any(metadata[k]for k in ('enable_gpu','enable_tpu','enable_internet')))


if __name__=='__main__': unittest.main()
