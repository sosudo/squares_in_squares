"""Bounded runner tests use fake controllers, never Kaggle submission calls."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_submission_loop as runner


class SubmissionLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def parameters(self):
        return {'python': sys.executable, 'controller': self.root / 'fake-controller.py',
            'queue': self.root / 'queue.json', 'state': self.root / 'state.json',
            'lock': self.root / 'runner.lock', 'status': self.root / 'runner-status.json',
            'events': self.root / 'events.jsonl', 'cadence': .01, 'max_seconds': .2, 'timeout': 600.}

    def test_exclusive_runner_lock_prevents_a_second_runner(self):
        calls = []
        with runner.runner_lock(self.root / 'runner.lock'):
            with self.assertRaises(RuntimeError):
                runner.run_loop(**self.parameters(), invoke=lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    def test_timeout_preserves_intent_and_invokes_read_only_reconciliation(self):
        config = self.parameters()
        original = {'pending': {'marker': '[an-existing-ambiguous-intent]'}}
        config['state'].write_text(json.dumps(original))
        stop = threading.Event(); calls = []
        def invoke(command, timeout, event):
            calls.append((command, timeout))
            if '--execute' in command:
                return {'returncode': -15, 'timed_out': True, 'interrupted': False}
            if len(calls) == 3:
                stop.set()
            return {'returncode': 0, 'timed_out': False, 'controller_action': 'pending'}
        with redirect_stdout(io.StringIO()):
            runner.run_loop(**config, stop=stop, invoke=invoke)
        self.assertEqual(len(calls), 3)
        self.assertIn('--reconcile-only', calls[0][0])
        self.assertIn('--execute', calls[1][0])
        self.assertIn('--reconcile-only', calls[2][0])
        self.assertNotIn('--execute', calls[2][0])
        self.assertTrue(all(0 < timeout <= 600 for _, timeout in calls))
        self.assertEqual(json.loads(config['state'].read_text()), original)
        events = [json.loads(line) for line in config['events'].read_text().splitlines()]
        self.assertIn('timeout_reconciliation', [event['event'] for event in events])
        self.assertEqual(events[-1]['event'], 'stopped')
        self.assertTrue(events[-1]['reconciliation_required'])

    def test_real_subprocess_timeout_is_bounded_and_diagnostics_filtered(self):
        command = [sys.executable, '-c',
            "import time; print('https://signed.example/?credential=secret',flush=True); time.sleep(10)"]
        started = time.monotonic()
        result = runner.invoke_controller(command, .05, threading.Event())
        self.assertTrue(result['timed_out'])
        self.assertLess(time.monotonic() - started, 3.)
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('signed.example', json.dumps(result))

    def test_controller_command_pins_paths_and_explicit_execution_mode(self):
        command = runner.controller_command('python', 'controller.py', self.root / 'q', self.root / 's')
        self.assertEqual(command[:4], ['python', 'controller.py', 'check', '--execute'])
        self.assertEqual(command[4:], ['--queue', str(self.root / 'q'), '--state', str(self.root / 's')])
        self.assertIn('--reconcile-only', runner.controller_command('python', 'controller.py', 'q', 's', True))

    def test_default_cli_is_disabled_and_does_not_take_a_lock(self):
        result = subprocess.run([sys.executable, str(Path(runner.__file__).resolve()),
            '--lock', str(self.root / 'never.lock')], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['event'], 'disabled')
        self.assertFalse((self.root / 'never.lock').exists())

    def test_arbitrary_controller_reason_and_exception_text_are_not_logged(self):
        text = json.dumps({'action': 'blocked', 'reason': 'secret https://signed.example/?token=private',
                           'exception': 'sensitive traceback', 'ref': 9})
        result = runner.safe_outcome(text)
        self.assertEqual(result, {'controller_action': 'blocked', 'submission_ref': 9})


if __name__ == '__main__':
    unittest.main()
