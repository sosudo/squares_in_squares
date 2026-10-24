import hashlib,json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from birth_gpu_pilot import publish_stage,stop_groups

class RetentionControls(unittest.TestCase):
    def test_completed_stage_survives_next_stage_cutoff(self):
        with tempfile.TemporaryDirectory()as directory:
            folder=Path(directory);p=np.arange(30,dtype=np.float64).reshape(2,5,3)/10
            sizes=np.array([.2,.3]);sides=np.array([4.,4.])
            record=publish_stage(folder,0,0,p,sizes,sides,dict(fresh_optimizer_history=True))
            try:raise TimeoutError('simulated next-stage cutoff')
            except TimeoutError:pass
            packet=folder/record['raw_packet']
            self.assertEqual(hashlib.sha256(packet.read_bytes()).hexdigest(),record['raw_packet_sha256'])
            with np.load(packet,allow_pickle=False)as z:
                self.assertTrue(np.array_equal(z['poses'],p));self.assertTrue(np.array_equal(z['birth_sizes'],sizes))
            meta=json.loads(packet.with_suffix('.json').read_text())
            self.assertFalse(meta['eligible_for_finish']);self.assertFalse(meta['verified'])
            full=publish_stage(folder,0,1,p,np.ones(2),sides,{})
            self.assertTrue(full['eligible_for_finish']);self.assertFalse(full['verified'])

    def test_registered_arm_group_kills_native_descendant(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'child.pid'
            code='import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(20)'
            process=subprocess.Popen([sys.executable,'-c',code,str(path)],start_new_session=True,
                                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                end=time.monotonic()+2.
                while not path.exists()and time.monotonic()<end:time.sleep(.01)
                self.assertTrue(path.exists());pid=int(path.read_text())
                records=stop_groups([process]);self.assertTrue(records[0]['forced']);self.assertIsNotNone(process.poll())
                stat=Path(f'/proc/{pid}/stat')
                if stat.exists():self.assertEqual(stat.read_text().split(')')[1].split()[0],'Z')
            finally:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=2.)

if __name__=='__main__':unittest.main()
