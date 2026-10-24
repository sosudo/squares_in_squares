import contextlib,hashlib,io,json,os,shutil,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
import fq_rectangular_persistent_pilot as p
import numpy as np

class OwnedShutdown(unittest.TestCase):
    def test_registered_setsid_descendants_stop_before_hash(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);writer=root/'writer.py';parent=root/'parent.py'
            writer.write_text("import os,time\nfrom pathlib import Path\np=Path(__file__).with_name('ticks')\nwhile True:\n with p.open('a')as f:f.write(str(os.getpid())+'\\n');f.flush()\n time.sleep(.01)\n")
            parent.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,str(Path(__file__).with_name('writer.py'))],start_new_session=True)\nPath(__file__).with_name('child.pid').write_text(str(p.pid))\ntime.sleep(30)\n")
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
            proc=subprocess.Popen([sys.executable,str(parent)],start_new_session=True);known={}
            try:
                end=time.monotonic()+3
                while time.monotonic()<end and not(root/'ticks').exists():p.register_descendants(proc.pid,known);time.sleep(.01)
                self.assertTrue((root/'ticks').exists());p.register_descendants(proc.pid,known)
                child=int((root/'child.pid').read_text());self.assertIn(child,known)
                # Parent may already exit/reparent its separately sessioned child;
                # the registered PID/start time still scopes cleanup correctly.
                proc.kill();proc.wait();report=p.stop_owned_tree(proc,known)
                self.assertIn(child,report['killed_pids'])
                before=(root/'ticks').read_bytes();time.sleep(.05)
                self.assertEqual((root/'ticks').read_bytes(),before)
                self.assertIsNone(unrelated.poll())
                table=p._process_table();self.assertTrue(child not in table or table[child][2]=='Z')
            finally:
                p.stop_owned_tree(proc,known)
                unrelated.kill();unrelated.wait()

    def test_protocol_budget(self):
        self.assertEqual(sum((p.PREFLIGHT_SECONDS,p.SEARCH_PHASE_SECONDS,p.RECOVERY_SECONDS,p.FINISH_SECONDS))*2,6786)
        self.assertLess(6786,7100)
        self.assertEqual(sorted(sum((list(q)for q in p.QUEUES),[])),sorted(p.searcher.FAMILIES))

    def test_actual_phase_deadline_reaps_setsid_writer(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);script=root/'phase.py'
            code="import time\nfrom pathlib import Path\np=Path('ticks')\nwhile True:\n with p.open('a')as f:f.write('x');f.flush()\n time.sleep(.01)\n"
            script.write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',"+repr(code)+"],start_new_session=True)\ntime.sleep(30)\n")
            with patch.object(p,'__file__',str(script)):
                result=p.run_phase(root,'search',.3,time.monotonic()+1.,0)
            self.assertTrue(result['forced']);self.assertEqual(result['status'],'bounded_partial')
            self.assertTrue(result['cleanup']['all_gone_or_zombie'])
            before=(root/'ticks').read_bytes();time.sleep(.05);self.assertEqual(before,(root/'ticks').read_bytes())

    def test_live_transport_and_partial_line_relay(self):
        import base64,zlib
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);(root/'finish').mkdir();data=b'exact-array-fixture\x00\xff'
            (root/'finish/certified.npz').write_bytes(data)
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                p.emit_family_payload(root,dict(key='5_17_7',protocol_sha256='p',source_input_archive_sha256='i'),
                    dict(certified=1,best_f_upper='.8',strict_component_improvements=0))
            packet=json.loads(output.getvalue().splitlines()[0]);item=packet['files']['finish/certified.npz']
            self.assertEqual(zlib.decompress(base64.b85decode(item['data'])),data)
            self.assertEqual(item['sha256'],hashlib.sha256(data).hexdigest())
            folder=root/'family-5_17_7';folder.mkdir();log=folder/'search.log';offsets={};buffers={}
            log.write_text('{"stage":"partial"');out=io.StringIO()
            with contextlib.redirect_stdout(out):p.relay_json_logs(root,offsets,buffers)
            self.assertEqual(out.getvalue(),'')
            with log.open('a')as f:f.write('}\n')
            with contextlib.redirect_stdout(out):p.relay_json_logs(root,offsets,buffers)
            self.assertEqual(json.loads(out.getvalue()),{'stage':'partial'})

if __name__=='__main__':unittest.main()
