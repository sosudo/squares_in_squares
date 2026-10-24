import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monitor_targeted_ftmc import SSEDecoder,compact_events,exclusive_lock,OUTPUT_FILES,terminal_downloads,terminal_outcome,remaining_window,download_outputs,NOTEBOOK,VERSION,SOURCE_SHA256


class TargetedMonitorTests(unittest.TestCase):
    def test_nested_sse_json_survives_fragmented_stdout_chunks(self):
        decoder=SSEDecoder();first={'stream_name':'stdout','data':'{"stage":"workers","elapsed":12,'}
        second={'stream_name':'stdout','data':'"devices":{"0":{"batches":3}}}\n'}
        self.assertEqual(decoder.feed('data: '+json.dumps(first)),[])
        events=decoder.feed('data: '+json.dumps(second))
        self.assertEqual(events[0]['elapsed'],12)
        self.assertEqual(compact_events(events)['latest_heartbeat']['devices']['0']['batches'],3)

    def test_compaction_drops_unknown_fields_and_sensitive_text(self):
        events=[{'stage':'workers','elapsed':1,'url':'https://private/?secret=abc',
                 'devices':{'0':{'batches':2,'unexpected':'secret-token','seconds':float('nan')}}}]
        result=compact_events(events)
        self.assertNotIn('secret',json.dumps(result));self.assertIsNone(result['latest_heartbeat']['devices']['0']['seconds'])

    def test_second_monitor_is_refused_by_exclusive_lock(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'lock'
            with exclusive_lock(path):
                with self.assertRaises(RuntimeError):
                    with exclusive_lock(path):pass
            with exclusive_lock(path):pass

    def test_output_requests_are_exact_unique_safe_names(self):
        self.assertEqual(len(OUTPUT_FILES),len(set(OUTPUT_FILES)))
        for name in OUTPUT_FILES:
            self.assertNotIn('*',name);self.assertNotIn('..',Path(name).parts)
            self.assertFalse(Path(name).is_absolute())

    def test_missing_outputs_cannot_be_reported_as_success(self):
        self.assertEqual(terminal_outcome('COMPLETE',{'complete':False}),('outputs_incomplete',2))
        self.assertEqual(terminal_outcome('COMPLETE',{'complete':True}),('complete',0))

    def test_only_bounded_missing_output_retries(self):
        calls=[]
        def downloader(*args):calls.append(1);return {'complete':len(calls)>=2}
        result=terminal_downloads(None,None,time.monotonic()+100,downloader,lambda seconds:None)
        self.assertTrue(result['complete']);self.assertEqual(result['attempts'],2)
        calls.clear()
        result=terminal_downloads(None,None,time.monotonic()+100,
            lambda *args:{'complete':False},lambda seconds:None)
        self.assertFalse(result['complete']);self.assertEqual(result['attempts'],3)

    def test_restart_preserves_original_overall_deadline(self):
        origin=datetime(2026,10,24,8,50,tzinfo=timezone.utc)
        plan={'notebook':NOTEBOOK,'version':VERSION,'source_sha256':SOURCE_SHA256,
              'started_at_utc':origin.isoformat(),'deadline_utc':(origin+timedelta(seconds=4200)).isoformat()}
        self.assertEqual(remaining_window(plan,4200,origin+timedelta(seconds=600)),3600)

    def test_cached_download_receipt_requires_exact_source_hash(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);state=root/'state';state.mkdir()
            (state/'downloads.json').write_text(json.dumps({'notebook':NOTEBOOK,'version':VERSION,
                                                         'source_sha256':'0'*64,'files':{}}))
            with self.assertRaises(ValueError):download_outputs(root/'out',state,time.monotonic()+10)


if __name__=='__main__':unittest.main()
