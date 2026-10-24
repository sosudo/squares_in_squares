"""Fail-closed package checks and native subprocess cleanup for CPU readiness."""
import ast
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def load_runtime(root):
    tree=ast.parse((ROOT/'experiments/fq_cpu_readiness_runtime.py').read_text())
    assert isinstance(tree.body[-1],ast.If)
    tree.body.pop()  # Load real helpers without starting the notebook supervisor.
    namespace={}
    with mock.patch.dict(os.environ,{'FQ_CPU_OUTPUT_ROOT':str(root)}):
        exec(compile(tree,'fq_cpu_readiness_runtime.py','exec'),namespace)
    return namespace


class ReadinessTests(unittest.TestCase):
    def test_native_timeout_reaps_child(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);runtime=load_runtime(root);pid=root/'pid'
            command=[sys.executable,'-c',
                'import os,pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)',str(pid)]
            with self.assertRaises(subprocess.TimeoutExpired):runtime['native'](command,timeout=.2)
            self.assertTrue(pid.is_file())
            with self.assertRaises(ProcessLookupError):os.kill(int(pid.read_text()),0)

    def _tamper(self,kind):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);runtime=load_runtime(root);stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w')as archive:archive.writestr('bin/fq',b'not executable')
            raw=stream.getvalue()
            config=dict(binary_sha256='expected',source_commit='pinned',server_timeout_seconds=300,
                payload_bytes=len(raw),payload_sha256=hashlib.sha256(raw).hexdigest(),
                files={'bin/fq':hashlib.sha256(b'not executable').hexdigest()})
            if kind=='archive':config['payload_sha256']='0'*64
            else:config['files']['bin/fq']='0'*64
            runtime.update(CONFIG=config,PAYLOAD=base64.b64encode(lzma.compress(raw)).decode())
            with self.assertRaisesRegex(ValueError,'hash differs'):runtime['worker']()
            report=json.loads((root/'readiness_report.json').read_text())
            self.assertEqual(report['status'],'failed')
            self.assertFalse((root/'fq_portable').exists())
            self.assertFalse((root/'fq_package/bin/fq').exists())

    def test_archive_tamper_is_rejected_before_native_execution(self):self._tamper('archive')
    def test_member_tamper_is_rejected_before_native_execution(self):self._tamper('member')


if __name__=='__main__':unittest.main()
