import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_rectangular_persistent_job as builder

class RectangularFixtureTests(unittest.TestCase):
    fixture=ROOT/'artifacts/rectangular-persistent-inputs-v2'

    def test_real_input_binding(self):
        config,proof=builder.validate_fixture(self.fixture)
        self.assertEqual(set(config['families']),set(builder.FAMILIES))
        self.assertEqual(len(proof['array_hashes']),32)
        for family in config['families'].values():
            self.assertEqual(len(family['seeds']),4)
            self.assertGreater(float(family['reference_f_lower']),0)

    def run_loader(self,temp,alter=False,collision=False):
        mount=Path(temp)/'input';work=Path(temp)/'working'
        shutil.copytree(self.fixture,mount/'fixture');work.mkdir()
        files={str(p.relative_to(self.fixture)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
               for p in self.fixture.rglob('*')if p.is_file()}
        shadow=mount/'00-shadow';shadow.mkdir();shutil.copyfile(self.fixture/'rectangular-inputs.npz',shadow/'rectangular-inputs.npz')
        config=json.loads((self.fixture/'rectangular-input-config.json').read_text())
        if alter:
            path=mount/'fixture/certificates/5_17_7__seed0.json';path.write_bytes(path.read_bytes()+b' ')
        if collision:(work/'rectangular-input-config.json').write_text('existing source')
        def mapped_path(value):return mount if str(value)=='/kaggle/input'else Path(value)
        namespace=dict(Path=mapped_path,hashlib=hashlib,json=json,root=work,
                       CONFIG=dict(inputs_sha256=config['inputs_sha256'],fixture_files=files,
                                   fixture_transport=dict(ref='private-owner/immutable-fixture/1')))
        exec(compile(builder.FIXTURE_LOADER,'exact-fixture-loader','exec'),namespace)
        for name,row in files.items():self.assertEqual(hashlib.sha256((work/name).read_bytes()).hexdigest(),row['sha256'])

    def test_exact_fixture_mount_replay(self):
        with tempfile.TemporaryDirectory()as temp:self.run_loader(temp)

    def test_tamper_and_source_collision_rejected(self):
        for mode in ('alter','collision'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory()as temp:
                with self.assertRaises((AssertionError,ValueError)):self.run_loader(temp,**{mode:True})


class OwnedProcessTreeTests(unittest.TestCase):
    def test_new_session_descendant_is_stopped(self):
        import os,signal,subprocess,time
        namespace=dict(os=os,signal=signal,Path=Path,time=time)
        exec(compile(builder.TREE_STOPPER,'exact-outer-tree-stopper','exec'),namespace)
        child_code="import os,time,pathlib; pathlib.Path(os.environ['RECT_CHILD_PID_PATH']).write_text(str(os.getpid())); time.sleep(60)"
        parent_code="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1]],start_new_session=True); time.sleep(60)"
        with tempfile.TemporaryDirectory()as temp:
            pidfile=Path(temp)/'child.pid';env=dict(os.environ,RECT_CHILD_PID_PATH=str(pidfile))
            parent=subprocess.Popen([sys.executable,'-c',parent_code,child_code],env=env,start_new_session=True)
            try:
                deadline=time.monotonic()+3
                while not pidfile.exists()and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(pidfile.exists());child=int(pidfile.read_text())
                self.assertNotEqual(os.getpgid(parent.pid),os.getpgid(child))
                namespace['stop_owned_tree'](parent)
                self.assertIsNotNone(parent.poll())
                stat=Path(f'/proc/{child}/stat')
                if stat.exists():self.assertEqual(stat.read_text().split(') ',1)[1][0],'Z')
            finally:
                if parent.poll()is None:namespace['stop_owned_tree'](parent)


class LiveRelayTests(unittest.TestCase):
    def test_child_line_arrives_before_exit_and_matches_saved_log(self):
        import subprocess
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);(root/'experiments').mkdir()
            (root/'experiments/fq_rectangular_persistent_pilot.py').write_text("import time\nprint('first-stage',flush=True)\ntime.sleep(.3)\nprint('last-stage',flush=True)\n")
            harness="import os,sys,signal,time,subprocess\nfrom pathlib import Path\nstarted=time.monotonic();env=dict(os.environ)\n"+builder.TREE_STOPPER+builder.STREAM_WORKER
            path=root/'harness.py';path.write_text(harness)
            process=subprocess.Popen([sys.executable,str(path)],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertEqual(process.stdout.readline(),'first-stage\n')
                self.assertIsNone(process.poll())
                stdout,stderr=process.communicate(timeout=3)
                self.assertEqual(process.returncode,0,stderr)
                self.assertEqual(stdout,'last-stage\n')
                self.assertEqual((root/'worker.log').read_text(),'first-stage\nlast-stage\n')
            finally:
                if process.poll()is None:process.kill();process.wait(timeout=2)

if __name__=='__main__':unittest.main()
