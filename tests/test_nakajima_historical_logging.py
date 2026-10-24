"""No-optimizer regression for distinct hardener/polish command logs."""
from pathlib import Path
import sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from nakajima_historical_controls import command,sha


class NativeLoggingTests(unittest.TestCase):
    def test_same_slot_different_phases_keep_both_exact_stdout_streams(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);records=[]
            for phase in ('harden','polish'):
                result=command([sys.executable,'-c','import sys;print(sys.argv[1])',phase],
                               root/('slot-00.'+phase),1.,time.monotonic()+2.)
                self.assertEqual(result['status'],'complete');records.append(result)
                self.assertEqual(Path(result['stdout_path']).read_bytes(),(phase+'\n').encode())
                self.assertEqual(sha(result['stdout_path']),result['stdout_sha256'])
            self.assertNotEqual(records[0]['stdout_path'],records[1]['stdout_path'])
            self.assertEqual(Path(records[0]['stdout_path']).read_bytes(),b'harden\n')


if __name__=='__main__':unittest.main()
