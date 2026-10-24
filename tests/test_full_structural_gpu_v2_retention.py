"""Deferred certificates must bind exact saved inputs/stages and case counts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from full_structural_gpu_v2_worker import(read_bundle,write_bundle,verify_pending_record,
    verify_certificate_count,finite_values)
from full_structural_gpu_moves import geometry_sha
from compose_gadgets import legalize


class DeferredRetentionTests(unittest.TestCase):
    def fixture(self,folder):
        (folder/'raw').mkdir();path=folder/'raw/batch.npz'
        p=np.array([[.5,.5,0.],[1.5,.5,0.]])
        row={'mutation':{'input_geometry_sha256':geometry_sha(p)},'source_id':'fixture'}
        metadata={'validated':False,'n':2,'rows':[row]}
        write_bundle(path,{'input':p[None]},metadata)
        record={'n':2,'geometry_sha256':geometry_sha(legalize(p)),'raw_batch':str(path),
            'stage':'target0','replica':0,'raw_geometry_sha256':geometry_sha(p),'row':row}
        # Later stages extend the atomic packet without changing earlier bytes.
        write_bundle(path,{'input':p[None],'target0':p[None],'target1':p[None].copy()},metadata)
        return p,legalize(p),record,path,metadata

    def test_final_packet_binding_and_changed_raw_member_fail_closed(self):
        with tempfile.TemporaryDirectory()as directory:
            folder=Path(directory);raw,pose,record,path,metadata=self.fixture(folder)
            record.update(verify_pending_record(record,pose,folder,require_packet_hash=False))
            verify_pending_record(record,pose,folder)
            arrays,_=read_bundle(path);arrays['target0']=arrays['target0'].copy();arrays['target0'][0,0,0]+=.01
            write_bundle(path,arrays,metadata)
            with self.assertRaises(AssertionError):verify_pending_record(record,pose,folder)
            with self.assertRaises(AssertionError):
                verify_pending_record(record,pose,folder,require_packet_hash=False)

    def test_case_counts_and_candidate_identity_are_bound(self):
        with tempfile.TemporaryDirectory()as directory:
            folder=Path(directory);raw,pose,record,path,metadata=self.fixture(folder)
            bad=copy.deepcopy(record);bad['n']=3
            with self.assertRaises(AssertionError):verify_pending_record(bad,pose,folder,require_packet_hash=False)
        verify_certificate_count({'valid':True,'independent_raw':{'n':2},'independent_roundtrip':{'n':2}},2)
        with self.assertRaises(AssertionError):
            verify_certificate_count({'valid':True,'independent_raw':{'n':2},'independent_roundtrip':{'n':3}},2)

    def test_nonfinite_scalars_sanitize_without_changing_raw_arrays(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'raw.npz';p=np.array([[[np.nan,np.inf,0.]]])
            values=finite_values([np.nan,np.inf,-np.inf,1.])
            self.assertEqual(values,[None,None,None,1.])
            write_bundle(path,{'target0':p},{'validated':False,'values':values})
            arrays,metadata=read_bundle(path)
            self.assertEqual(geometry_sha(arrays['target0']),geometry_sha(p))
            self.assertEqual(metadata['values'],values)
            json.dumps(metadata,allow_nan=False)


if __name__=='__main__':unittest.main()
