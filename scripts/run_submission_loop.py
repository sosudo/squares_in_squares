"""Bounded periodic wrapper around the conservative one-shot controller.

Disabled unless --enable-submissions is explicitly supplied. No system timer or
daemon is installed. Controller intent/receipts remain authoritative; timeout
cleanup never removes or clears them. Logs contain only selected scalar fields,
never subprocess exception strings, stderr, credentials or signed URLs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ACTIONS = {'empty', 'ready', 'wait', 'blocked', 'submitted', 'ambiguous',
                   'reconciled', 'pending'}


@contextmanager
def runner_lock(path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another submission runner holds the exclusive lock') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def controller_command(python, controller, queue, state, reconcile=False):
    return [str(python), str(controller), 'check',
            '--reconcile-only' if reconcile else '--execute',
            '--queue', str(Path(queue).resolve()), '--state', str(Path(state).resolve())]


def safe_outcome(stdout):
    """Ignore arbitrary subprocess output; retain only known scalar result types."""
    result = {}
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(value, dict) or value.get('action') not in ALLOWED_ACTIONS:
            continue
        selected = {'controller_action': value['action']}
        if type(value.get('ref')) is int:
            selected['submission_ref'] = value['ref']
        if isinstance(value.get('candidate_id'), str) and re.fullmatch('[0-9a-f]{64}', value['candidate_id']):
            selected['candidate_id'] = value['candidate_id']
        if isinstance(value.get('not_before'), str):
            try:
                parsed = datetime.fromisoformat(value['not_before'].replace('Z', '+00:00'))
                selected['not_before'] = parsed.isoformat()
            except ValueError:
                pass
        if type(value.get('pending_intent')) is bool:
            selected['pending_intent'] = value['pending_intent']
        result = selected
    return result


def terminate_owned(process):
    """Stop only the process group created for this controller invocation."""
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        return process.communicate(timeout=2.)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()


def invoke_controller(command, timeout, stop):
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = interrupted = False
    while True:
        remaining = timeout - (time.monotonic() - started)
        if stop.is_set() or remaining <= 0:
            interrupted = stop.is_set(); timed_out = not interrupted
            stdout, _ = terminate_owned(process)
            break
        try:
            stdout, _ = process.communicate(timeout=min(.5, remaining))
            break
        except subprocess.TimeoutExpired:
            continue
    return {'returncode': process.returncode, 'timed_out': timed_out,
            'interrupted': interrupted, 'seconds': time.monotonic() - started,
            **safe_outcome(stdout)}


def pending_intent(state):
    try:
        path = Path(state)
        return bool(json.loads(path.read_text()).get('pending')) if path.exists() else False
    except (OSError, ValueError):
        return None


def record(status_path, event_path, value):
    value = {'time_utc': datetime.now(timezone.utc).isoformat(), **value}
    status_path = Path(status_path); status_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = status_path.with_suffix(status_path.suffix + '.incoming')
    temporary.write_text(json.dumps(value, indent=2) + '\n'); temporary.replace(status_path)
    Path(event_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(event_path).open('a') as stream:
        stream.write(json.dumps(value) + '\n'); stream.flush()
    print(json.dumps(value), flush=True)


def run_loop(*, python, controller, queue, state, lock, status, events,
             cadence=60., max_seconds=43200., timeout=600., stop=None,
             invoke=invoke_controller, log=record):
    """Run bounded ticks. Used only after explicit CLI enabling or by tests."""
    for value in (cadence, max_seconds, timeout):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Cadence, maximum runtime and timeout must be finite and positive')
    stop = stop or threading.Event()
    with runner_lock(lock):
        started = time.monotonic(); deadline = started + max_seconds
        base = {'runner_pid': os.getpid(), 'max_seconds': max_seconds,
                'cadence_seconds': cadence, 'controller_timeout_seconds': timeout}
        log(status, events, {**base, 'event': 'started'})
        ticks = 0; timed_out = False
        try:
            # Always reconcile previous interrupted/ambiguous work before the
            # first potentially mutating controller tick.
            remaining = deadline - time.monotonic()
            if remaining > 0 and not stop.is_set():
                result = invoke(controller_command(python, controller, queue, state, True),
                                min(timeout, 60., remaining), stop)
                log(status, events, {**base, 'event': 'startup_reconciliation', **result,
                                    'pending_intent': pending_intent(state)})
            while not stop.is_set() and time.monotonic() < deadline:
                tick_started = time.monotonic()
                if tick_started >= deadline:
                    break
                ticks += 1
                result = invoke(controller_command(python, controller, queue, state),
                                min(timeout, deadline - tick_started), stop)
                timed_out = bool(result.get('timed_out'))
                log(status, events, {**base, 'event': 'controller_tick', 'tick': ticks, **result,
                                    'pending_intent': pending_intent(state),
                                    'reconciliation_required': timed_out or pending_intent(state) is not False})
                # A timeout can happen after Kaggle accepted a request. Persist
                # the outcome and use a read-only reconciliation, never clear
                # the pending intent or blindly repeat the failed request.
                remaining = deadline - time.monotonic()
                if timed_out and remaining > 0 and not stop.is_set():
                    reconciled = invoke(controller_command(python, controller, queue, state, True),
                                        min(timeout, 60., remaining), stop)
                    if (reconciled.get('returncode') == 0 and not reconciled.get('timed_out')
                            and pending_intent(state) is False):
                        timed_out = False
                    log(status, events, {**base, 'event': 'timeout_reconciliation', 'tick': ticks,
                        **reconciled, 'pending_intent': pending_intent(state),
                        'reconciliation_required': pending_intent(state) is not False})
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    stop.wait(min(remaining, max(0., cadence - (time.monotonic() - tick_started))))
        finally:
            log(status, events, {**base, 'event': 'stopped', 'ticks': ticks,
                'seconds': time.monotonic() - started, 'stop_signal': stop.is_set(),
                'pending_intent': pending_intent(state),
                'reconciliation_required': timed_out or pending_intent(state) is not False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-submissions', action='store_true')
    parser.add_argument('--hours', type=float, default=12.)
    parser.add_argument('--cadence', type=float, default=60.)
    parser.add_argument('--timeout', type=float, default=600.)
    parser.add_argument('--python', type=Path,
        default=ROOT / '.venv/bin/python' if (ROOT / '.venv/bin/python').exists() else Path(sys.executable))
    parser.add_argument('--queue', type=Path, default=ROOT / 'artifacts/submissions/queue.json')
    parser.add_argument('--state', type=Path, default=ROOT / 'artifacts/submissions/scheduler-state.json')
    parser.add_argument('--lock', type=Path, default=ROOT / 'artifacts/submissions/runner.lock')
    parser.add_argument('--status', type=Path, default=ROOT / 'artifacts/submissions/runner-status.json')
    parser.add_argument('--events', type=Path, default=ROOT / 'artifacts/submissions/runner-events.jsonl')
    args = parser.parse_args()
    if not args.enable_submissions:
        print(json.dumps({'event': 'disabled', 'requires': '--enable-submissions',
            'hours': args.hours, 'cadence_seconds': args.cadence, 'timeout_seconds': args.timeout}))
        return
    stop = threading.Event()
    def handle_stop(signum, frame):
        stop.set()
    signal.signal(signal.SIGTERM, handle_stop); signal.signal(signal.SIGINT, handle_stop)
    run_loop(python=args.python, controller=ROOT / 'scripts/submission_scheduler.py',
        queue=args.queue, state=args.state, lock=args.lock, status=args.status, events=args.events,
        cadence=args.cadence, max_seconds=args.hours * 3600, timeout=args.timeout, stop=stop)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print exception text or captured subprocess stderr.
        print(json.dumps({'event': 'runner_blocked', 'error_type': type(error).__name__}))
        raise SystemExit(1)
