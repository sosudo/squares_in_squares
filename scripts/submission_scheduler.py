"""One-shot, conservative controller for hourly improving Kaggle submissions.

Default mode only checks. No daemon is installed or started. Queue entries bind
immutable private notebook outputs to exact CSV and raw/float-validation hashes.
An explicit --execute performs at most one submission. Ambiguous requests stay
blocked until submission history identifies their unique SHA marker.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

COMPETITION = 'squares-in-squares'
METRIC = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
HOUR = 3600
DAILY_LIMIT = 10
SCORE_TOLERANCE = Decimal('0.0000000001')
AUTHORIZATION_POLICY = Path(__file__).resolve().parents[1] / 'artifacts/submissions/authorization-policy.json'
MAX_AUTHORIZED_SCORE = Decimal('22.3')


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.incoming')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path)}


def read_binding(bound, json_data=False):
    path = Path(bound['path'])
    if digest(path) != bound['sha256']:
        raise ValueError('An immutable queued artifact changed: ' + path.name)
    return json.loads(path.read_text()) if json_data else path


def numeric_score(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError('Invalid competition score')
    return number


def safe_error_diagnostics(error):
    """Extract only numeric HTTP/API codes; never retain messages or URLs."""
    result = {}
    response = getattr(error, 'response', None)
    if response is None:
        return result
    status = getattr(response, 'status_code', None)
    if type(status) is int and 100 <= status <= 599:
        result['status_code'] = status
    try:
        payload = response.json()
    except Exception:
        return result
    if isinstance(payload, dict):
        for key in ('code', 'errorCode', 'error_code'):
            code = payload.get(key)
            if type(code) is int and -(2 ** 31) <= code < 2 ** 31:
                result['error_code'] = code
                break
    return result


def load_authorization_policy(path=None):
    """Require the persisted authorization, failing closed if absent or invalid."""
    path = Path(path or AUTHORIZATION_POLICY)
    data = json.loads(path.read_text())
    ceiling = numeric_score(data['submission_score_must_be_strictly_below'])
    if ceiling <= 0 or ceiling > MAX_AUTHORIZED_SCORE:
        raise ValueError('Authorization cannot permit submissions at or above22.3')
    if data.get('strict_improvement_required') is not True:
        raise ValueError('Strict improvement authorization must remain enabled')
    interval = data.get('minimum_interval_seconds')
    if type(interval) is not int or interval < HOUR:
        raise ValueError('Authorization must retain the minimum hourly interval')
    return {'score_ceiling': str(ceiling), 'minimum_interval_seconds': interval,
            'sha256': digest(path), 'source': str(path.resolve())}


def checked_policy(policy):
    ceiling = numeric_score(policy['score_ceiling'])
    if not (0 < ceiling <= MAX_AUTHORIZED_SCORE):
        raise ValueError('Invalid strict authorization score ceiling')
    if type(policy['minimum_interval_seconds']) is not int or policy['minimum_interval_seconds'] < HOUR:
        raise ValueError('Invalid authorized submission interval')
    return policy


def full_transport_coverage(summary):
    """Allow full fresh evaluation or complete hash-certified delta reuse."""
    coverage = summary.get('roundtrip_case_coverage')
    if coverage is None:
        return type(summary.get('roundtrip_evaluated')) is int and summary['roundtrip_evaluated'] == 1000
    if type(coverage) is not int or coverage != 1000:
        return False
    reuse = summary.get('roundtrip_reuse', {})
    evaluated = summary.get('roundtrip_evaluated', reuse.get('evaluated'))
    reused = summary.get('roundtrip_reused', reuse.get('reused'))
    if type(evaluated) is not int or type(reused) is not int or min(evaluated, reused) < 0:
        return False
    if evaluated + reused != coverage:
        return False
    return all(reuse.get(key, expected) == expected for key, expected in
               (('evaluated', evaluated), ('reused', reused)))


def validate_candidate(candidate):
    """Verify all local bindings and both complete official validation outcomes."""
    read_binding(candidate['csv'])
    read_binding(candidate['roundtrip_csv'])
    raw = read_binding(candidate['raw_report'], True)
    rounded = read_binding(candidate['roundtrip_report'], True)
    transport = read_binding(candidate['transport_report'], True)
    for report, sha in ((raw, candidate['csv']['sha256']),
                        (rounded, candidate['roundtrip_csv']['sha256'])):
        if not (report.get('valid') is True and report.get('invalid_count') == 0
                and report.get('puzzles') == 1000 and report.get('rows') == 500500
                and report.get('metric_sha256') == METRIC and report.get('sha256') == sha):
            raise ValueError('Queue requires a complete matching official v17 report')
    score = numeric_score(raw['score']); roundtrip_score = numeric_score(rounded['score'])
    if abs(score - roundtrip_score) > SCORE_TOLERANCE:
        raise ValueError('Raw and float-roundtrip official scores disagree')
    if not (transport.get('safe_sha256') == candidate['csv']['sha256']
            and transport.get('roundtrip_sha256') == candidate['roundtrip_csv']['sha256']
            and transport.get('metric_sha256') == METRIC
            and transport.get('safe_invalid_count') == 0
            and transport.get('roundtrip_invalid_count') == 0
            and full_transport_coverage(transport)
            and abs(numeric_score(transport['safe_score']) - score) <= SCORE_TOLERANCE
            and abs(numeric_score(transport['roundtrip_score']) - roundtrip_score) <= SCORE_TOLERANCE):
        raise ValueError('Transport summary does not bind the same validated CSVs')
    for key, bound in (('safe_official_report_sha256', candidate['raw_report']['sha256']),
                       ('roundtrip_official_report_sha256', candidate['roundtrip_report']['sha256'])):
        if key in transport and transport[key] != bound:
            raise ValueError('Transport summary official-report hash mismatch')
    notebook = candidate['notebook']
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+', notebook['ref']):
        raise ValueError('Notebook must be an owner/slug reference')
    if type(notebook['version']) is not int or notebook['version'] < 1:
        raise ValueError('Notebook version must be a positive immutable version number')
    filename = PurePosixPath(notebook['output_file'])
    if filename.is_absolute() or '..' in filename.parts or not filename.name.endswith('.csv'):
        raise ValueError('Unsafe notebook output filename')
    proof = candidate['completion']
    if not (proof.get('status') == 'complete' and proof.get('is_private') is True
            and proof.get('ref') == notebook['ref'] and proof.get('version') == notebook['version']
            and proof.get('output_file') == notebook['output_file']
            and proof.get('output_sha256') == candidate['csv']['sha256']):
        raise ValueError('Queue lacks matching completed private notebook output proof')
    if candidate.get('id') != candidate['csv']['sha256'] or numeric_score(candidate['score']) != score:
        raise ValueError('Queue identity or score does not match its validated CSV')
    # Authorization and selection use the worse of the two validated transports.
    return max(score, roundtrip_score)


def make_candidate(csv_path, raw_report, roundtrip_csv, roundtrip_report, transport_report,
                   notebook, completion):
    candidate = {'id': digest(csv_path), 'csv': binding(csv_path), 'raw_report': binding(raw_report),
        'roundtrip_csv': binding(roundtrip_csv), 'roundtrip_report': binding(roundtrip_report),
        'transport_report': binding(transport_report), 'notebook': notebook, 'completion': completion,
        'score': str(json.loads(Path(raw_report).read_text())['score'])}
    validate_candidate(candidate)
    return candidate


def freeze_candidate(candidate, directory):
    """Retain content-addressed copies so later experiments cannot alter a queue."""
    candidate = deepcopy(candidate)
    directory = Path(directory) / candidate['id']; directory.mkdir(parents=True, exist_ok=True)
    names = {'csv': 'candidate.csv', 'raw_report': 'raw-official.json',
             'roundtrip_csv': 'float-roundtrip.csv', 'roundtrip_report': 'float-official.json',
             'transport_report': 'transport-validation.json'}
    for key, name in names.items():
        source = read_binding(candidate[key]); target = directory / name
        if target.exists():
            if digest(target) != candidate[key]['sha256']:
                raise ValueError('Immutable queue snapshot was changed')
        else:
            temporary = target.with_suffix(target.suffix + '.incoming')
            shutil.copyfile(source, temporary)
            if digest(temporary) != candidate[key]['sha256']:
                raise ValueError('Artifact changed while freezing queue snapshot')
            temporary.replace(target); target.chmod(0o444)
        candidate[key]['path'] = str(target.resolve())
    validate_candidate(candidate)
    return candidate


def new_state():
    return {'schema_version': 1, 'competition': COMPETITION, 'submitted': {}, 'pending': None}


def marker(candidate):
    return '[squares-sha256:' + candidate['id'] + ']'


def accept(state, candidate, record, now):
    if state.get('pending') and state['pending']['candidate']['id'] != candidate['id']:
        raise ValueError('A different ambiguous submission intent must not be cleared')
    for sha, entry in state.get('submitted', {}).items():
        if int(entry['ref']) == int(record['ref']) and sha != candidate['id']:
            raise ValueError('Submission reference is already bound to another CSV hash')
    policy = deepcopy(state['pending'].get('authorization_policy')) if state.get('pending') else None
    state['submitted'][candidate['id']] = {
        'ref': int(record['ref']), 'submitted_at': utc(record.get('date') or now).isoformat(),
        'validated_score': candidate['score'], 'status': record.get('status', 'pending'),
        'public_score': record.get('public_score'), 'notebook': candidate['notebook'],
        'sha256': candidate['id'], 'marker': marker(candidate)}
    if policy:
        state['submitted'][candidate['id']]['authorization_policy'] = policy
    state['pending'] = None


def adopt_existing(state, candidate, row, now):
    pending = state.get('pending')
    if pending and (pending['candidate']['id'] != candidate['id']
                    or pending['marker'] not in row.get('description', '')):
        raise ValueError('Adoption must resolve the same ambiguous intent by its history marker')
    if row['status'] == 'error':
        raise ValueError('Cannot adopt an errored submission as a successful baseline')
    if row.get('public_score') and abs(numeric_score(row['public_score']) - numeric_score(candidate['score'])) > SCORE_TOLERANCE:
        raise ValueError('Existing submission score differs from candidate validation')
    accept(state, candidate, row, now)


def save_state(path, state):
    atomic_json(path, state)
    for sha, entry in state['submitted'].items():
        receipt = Path(path).parent / 'scheduler-receipts' / (str(entry['ref']) + '.json')
        if not receipt.exists():
            atomic_json(receipt, entry)
        elif json.loads(receipt.read_text())['sha256'] != sha:
            raise ValueError('Existing immutable receipt refers to another CSV hash')


def reconcile(state, history, now):
    """Resolve an acknowledged or ambiguous submission without creating another."""
    pending = state.get('pending')
    if pending:
        matches = [r for r in history if pending['marker'] in r.get('description', '')]
        if len(matches) > 1:
            raise ValueError('Duplicate remote SHA markers require manual review')
        if matches:
            accept(state, pending['candidate'], matches[0], now)
    by_ref = {int(r['ref']): r for r in history}
    for entry in state.get('submitted', {}).values():
        row = by_ref.get(int(entry['ref']))
        if row:
            entry['status'] = row['status']; entry['public_score'] = row.get('public_score')
            entry['submitted_at'] = utc(row['date']).isoformat()
            if row['status'] == 'complete' and row.get('public_score') not in (None, ''):
                if abs(numeric_score(row['public_score']) - numeric_score(entry['validated_score'])) > SCORE_TOLERANCE:
                    state['review_required'] = 'Kaggle score differs from the validated submitted score'


def plan(candidates, state, snapshot, now, policy=None, validated_scores=None):
    """Eligibility decision; immutable reports and unknown inputs fail closed."""
    policy = checked_policy(policy if policy is not None else load_authorization_policy())
    validated_scores = (validated_scores if validated_scores is not None
                        else {c['id']: validate_candidate(c) for c in candidates})
    now = utc(now); history = snapshot['history']; limits = snapshot['limits']
    if state.get('review_required'):
        return {'action': 'blocked', 'reason': state['review_required']}
    if state.get('pending'):
        return {'action': 'blocked', 'reason': 'Ambiguous submission awaits history reconciliation; do not retry'}
    authorized = [c for c in candidates if validated_scores[c['id']] < numeric_score(policy['score_ceiling'])]
    if not authorized:
        return {'action': 'blocked', 'reason': 'No validated candidate strictly below the authorized score ceiling',
                'score_must_be_strictly_below': policy['score_ceiling']}
    if any(r['status'] == 'pending' for r in history):
        return {'action': 'wait', 'reason': 'An accepted Kaggle submission is still scoring'}
    if any(e.get('status') == 'pending' for e in state.get('submitted', {}).values()):
        return {'action': 'wait', 'reason': 'A tracked accepted submission has no final history outcome'}
    today = now.date()
    daily = sum(utc(r['date']).date() == today for r in history)
    tracked_daily = sum(utc(r['submitted_at']).date() == today for r in state.get('submitted', {}).values())
    if (limits.get('num_allowed_now', 0) <= 0 or limits.get('num_today', DAILY_LIMIT) >= DAILY_LIMIT
            or max(daily, tracked_daily) >= DAILY_LIMIT):
        return {'action': 'wait', 'reason': 'Live Kaggle daily submission allowance exhausted', 'limits': limits}
    dates = [utc(r['date']) for r in history]
    dates += [utc(r['submitted_at']) for r in state.get('submitted', {}).values()]
    interval = policy['minimum_interval_seconds']
    if dates and now < max(dates) + timedelta(seconds=interval):
        return {'action': 'wait', 'reason': 'Hourly interval has not elapsed',
                'not_before': (max(dates) + timedelta(seconds=interval)).isoformat()}
    submitted = state.get('submitted', {})
    scores = [numeric_score(e['validated_score']) for e in submitted.values()
              if e.get('status') != 'error']
    for row in history:
        if row['status'] == 'complete':
            if row.get('public_score') in (None, ''):
                return {'action': 'blocked', 'reason': 'A completed submission has no observable score'}
            # Never ignore the actual Kaggle result, including for tracked refs.
            # Demand a gain beyond one display unit to avoid treating a slight
            # local/public discrepancy as a real leaderboard improvement.
            scores.append(numeric_score(row['public_score']) - SCORE_TOLERANCE)
    best = min(scores) if scores else Decimal('Infinity')
    eligible = []
    for candidate in authorized:
        if candidate['id'] in submitted:
            continue
        if any(marker(candidate) in row.get('description', '') for row in history):
            continue
        if validated_scores[candidate['id']] < best:
            eligible.append(candidate)
    if not eligible:
        return {'action': 'wait', 'reason': 'No new strictly better validated score',
                'best_submitted_score_bound': str(best)}
    winner = min(eligible, key=lambda c: validated_scores[c['id']])
    return {'action': 'ready', 'candidate_id': winner['id'], 'score': str(validated_scores[winner['id']]),
            'best_submitted_score_bound': str(best), 'limits': limits}


def controller(candidates, state, gateway, now, execute=False, persist=lambda state: None, policy=None):
    """Check or submit once; write intent before invoking the mutating API."""
    state = deepcopy(state)
    current_policy = checked_policy(policy if policy is not None else load_authorization_policy())
    validated_scores = {candidate['id']: validate_candidate(candidate) for candidate in candidates}
    snapshot = gateway.snapshot()
    reconcile(state, snapshot['history'], now)
    decision = plan(candidates, state, snapshot, now, current_policy, validated_scores)
    if not execute or decision['action'] != 'ready':
        if execute:
            persist(state)
        return decision, state
    candidate = next(c for c in candidates if c['id'] == decision['candidate_id'])
    gateway.verify_notebook(candidate['notebook'], candidate['id'])
    # A download may take time; recheck history/quota immediately before mutation.
    current_policy = checked_policy(policy if policy is not None else load_authorization_policy())
    snapshot = gateway.snapshot(); reconcile(state, snapshot['history'], now)
    decision = plan(candidates, state, snapshot, now, current_policy, validated_scores)
    if decision.get('candidate_id') != candidate['id'] or decision['action'] != 'ready':
        persist(state); return decision, state
    state['pending'] = {'candidate': candidate, 'marker': marker(candidate),
                        'request_started_at': utc(now).isoformat(),
                        'authorization_policy': deepcopy(current_policy)}
    persist(state)
    description = marker(candidate) + ' validated score ' + candidate['score']
    try:
        response = gateway.submit_notebook(candidate['notebook'], description)
        if type(response.get('ref')) is not int or response['ref'] <= 0:
            raise RuntimeError('Submission acknowledgment has no positive reference')
    except Exception as exc:
        # Never log exception strings: SDK errors may contain credentials or URLs.
        diagnostics = safe_error_diagnostics(exc)
        state['pending']['error_type'] = type(exc).__name__
        state['pending'].update(diagnostics); persist(state)
        try:
            reconcile(state, gateway.snapshot()['history'], now)
        except Exception:
            pass
        persist(state)
        if state.get('pending'):
            return {'action': 'ambiguous', 'reason': 'Check submission history; automatic retry disabled',
                    'error_type': type(exc).__name__, **diagnostics}, state
        entry = state['submitted'][candidate['id']]
        return {'action': 'reconciled', 'ref': entry['ref'], 'candidate_id': candidate['id']}, state
    accept(state, candidate, {'ref': response['ref'], 'date': utc(now).isoformat(),
                             'status': 'pending'}, now)
    persist(state)
    return {'action': 'submitted', 'ref': response['ref'], 'candidate_id': candidate['id'],
            'score': candidate['score'], 'status': 'pending'}, state


class KaggleGateway:
    """Official SDK adapter; network diagnostics never expose URLs or secrets."""
    def __enter__(self):
        from kagglesdk.kaggle_client import KaggleClient
        import kagglesdk.kaggle_env as env
        token = os.getenv('KAGGLE_API_TOKEN')
        if not token:
            path = Path(os.getenv('KAGGLE_TOKEN_FILE', '/tmp/squares-kaggle-auth/token'))
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise ValueError('Kaggle token file must be private (mode0600)')
            token = path.read_text().strip()
        if os.getenv('KAGGLE_USE_WWW_API', '1') == '1':
            env._env_to_endpoint[env.KaggleEnv.PROD] = 'https://www.kaggle.com/api'
        self.client = KaggleClient(api_token=token).__enter__()
        return self

    def __exit__(self, *args):
        self.client.__exit__(*args)

    def snapshot(self):
        from kagglesdk.competitions.types.competition_api_service import (
            ApiListSubmissionsRequest, ApiGetSubmissionLimitsRequest)
        api = self.client.competitions.competition_api_client
        request = ApiGetSubmissionLimitsRequest(); request.competition_name = COMPETITION
        quota = api.get_submission_limits(request)
        history = []; token = ''
        for _ in range(100):
            request = ApiListSubmissionsRequest(); request.competition_name = COMPETITION
            request.page_size = 100
            if token:
                request.page_token = token
            response = api.list_submissions(request)
            for row in response.submissions or []:
                history.append({'ref': row.ref, 'date': utc(row.date).isoformat(),
                    'description': row.description or '', 'status': row.status.name.lower(),
                    'public_score': row.public_score or None})
            token = response.next_page_token
            if not token:
                break
        if token:
            raise ValueError('Submission history pagination incomplete; stop')
        return {'history': history, 'limits': {'num_today': quota.num_today,
                'num_total': quota.num_total, 'num_allowed_now': quota.num_allowed_now}}

    def verify_notebook(self, notebook, expected_sha):
        from kagglesdk.kernels.types.kernels_api_service import (
            ApiGetKernelRequest, ApiGetKernelSessionStatusRequest, ApiDownloadKernelOutputRequest)
        from urllib.parse import urlsplit
        import requests
        owner, slug = notebook['ref'].split('/')
        api = self.client.kernels.kernels_api_client
        request = ApiGetKernelRequest(); request.user_name = owner; request.kernel_slug = slug
        request.version_label = 'v' + str(notebook['version'])
        metadata = api.get_kernel(request).metadata
        if metadata.current_version_number != notebook['version'] or not metadata.is_private:
            raise ValueError('Notebook must be the exact private saved version')
        competition_sources = getattr(metadata, 'competition_data_sources', None)
        if not isinstance(competition_sources, list) or COMPETITION not in competition_sources:
            raise ValueError('Notebook must attach the exact squares-in-squares competition')
        status_request = ApiGetKernelSessionStatusRequest(); status_request.user_name = owner
        status_request.kernel_slug = slug; status_request.version_label = request.version_label
        if api.get_kernel_session_status(status_request).status.name != 'COMPLETE':
            raise ValueError('The exact notebook version has not completed successfully')
        request = ApiDownloadKernelOutputRequest(); request.owner_slug = owner; request.kernel_slug = slug
        request.version_number = notebook['version']; request.file_path = notebook['output_file']
        redirect = api.download_kernel_output(request)
        if urlsplit(redirect.url).scheme != 'https':
            raise ValueError('Notebook output URL must use verified HTTPS')
        digestor = hashlib.sha256()
        with requests.get(redirect.url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(1024 * 1024):
                digestor.update(chunk)
        if digestor.hexdigest() != expected_sha:
            raise ValueError('Remote immutable notebook output differs from validated CSV')
        return {'ref': notebook['ref'], 'version': notebook['version'],
            'output_file': notebook['output_file'], 'output_sha256': expected_sha,
            'status': 'complete', 'is_private': True,
            'competition_sources': list(competition_sources),
            'verified_at': datetime.now(timezone.utc).isoformat()}

    def submit_notebook(self, notebook, description):
        from kagglesdk.competitions.types.competition_api_service import ApiCreateCodeSubmissionRequest
        request = ApiCreateCodeSubmissionRequest(); request.competition_name = COMPETITION
        request.kernel_owner, request.kernel_slug = notebook['ref'].split('/')
        request.kernel_version = notebook['version']; request.file_name = notebook['output_file']
        request.submission_description = description
        response = self.client.competitions.competition_api_client.create_code_submission(request)
        return {'ref': response.ref}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['check', 'enqueue', 'adopt'], default='check')
    parser.add_argument('--queue', type=Path, default=Path('artifacts/submissions/queue.json'))
    parser.add_argument('--state', type=Path, default=Path('artifacts/submissions/scheduler-state.json'))
    parser.add_argument('--execute', action='store_true', help='Explicitly allow at most one submission')
    parser.add_argument('--reconcile-only', action='store_true',
                        help='Read live history and persist reconciliation without submitting')
    parser.add_argument('--csv', type=Path); parser.add_argument('--raw-report', type=Path)
    parser.add_argument('--roundtrip-csv', type=Path); parser.add_argument('--roundtrip-report', type=Path)
    parser.add_argument('--transport-report', type=Path); parser.add_argument('--notebook')
    parser.add_argument('--version', type=int); parser.add_argument('--output-file', default='submission.csv')
    parser.add_argument('--candidate-id'); parser.add_argument('--submission-ref', type=int)
    args = parser.parse_args(); now = datetime.now(timezone.utc)
    if args.execute and args.command != 'check':
        parser.error('--execute applies only to check')
    if args.reconcile_only and (args.execute or args.command != 'check'):
        parser.error('--reconcile-only applies only to check and excludes --execute')
    if args.execute:
        load_authorization_policy()  # Required before even opening an API client.
    queue = json.loads(args.queue.read_text()) if args.queue.exists() else {'schema_version': 1, 'candidates': []}
    if args.command == 'check' and not queue['candidates'] and not args.reconcile_only:
        print(json.dumps({'action': 'empty', 'reason': 'No queued candidate; no API request made'})); return
    needs_write = args.execute or args.reconcile_only or args.command != 'check'
    args.state.parent.mkdir(parents=True, exist_ok=True)
    lock = args.state.with_suffix('.lock').open('a') if needs_write else nullcontext()
    with lock as handle:
        if needs_write:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Reload after acquiring the lock; concurrent enqueue/adopt calls
            # must not overwrite a queue read before another writer finished.
            queue = (json.loads(args.queue.read_text()) if args.queue.exists()
                     else {'schema_version': 1, 'candidates': []})
        state = json.loads(args.state.read_text()) if args.state.exists() else new_state()
        with KaggleGateway() as gateway:
            if args.command == 'enqueue':
                required = [args.csv, args.raw_report, args.roundtrip_csv, args.roundtrip_report,
                            args.transport_report, args.notebook, args.version]
                if not all(required):
                    parser.error('enqueue requires CSV, raw/roundtrip/transport reports and notebook/version')
                notebook = {'ref': args.notebook, 'version': args.version, 'output_file': args.output_file}
                proof = gateway.verify_notebook(notebook, digest(args.csv))
                candidate = make_candidate(args.csv, args.raw_report, args.roundtrip_csv,
                    args.roundtrip_report, args.transport_report, notebook, proof)
                if any(c['id'] == candidate['id'] for c in queue['candidates']):
                    raise ValueError('CSV hash is already queued')
                candidate = freeze_candidate(candidate, args.state.parent / 'queue-artifacts')
                queue['candidates'].append(candidate); atomic_json(args.queue, queue)
                print(json.dumps({'action': 'queued', 'candidate_id': candidate['id'], 'score': candidate['score']}))
            elif args.command == 'adopt':
                candidate = next(c for c in queue['candidates'] if c['id'] == args.candidate_id)
                validate_candidate(candidate); history = gateway.snapshot()['history']
                row = next(r for r in history if int(r['ref']) == args.submission_ref)
                adopt_existing(state, candidate, row, now); save_state(args.state, state)
                print(json.dumps({'action': 'adopted', 'ref': row['ref'], 'status': row['status']}))
            else:
                def persist(value):
                    save_state(args.state, value)
                if args.reconcile_only:
                    reconcile(state, gateway.snapshot()['history'], now)
                    persist(state)
                    print(json.dumps({'action': 'pending' if state.get('pending') else 'reconciled',
                                      'pending_intent': bool(state.get('pending'))}))
                    return
                result, _ = controller(queue['candidates'], state, gateway, now, args.execute, persist)
                print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never interpolate SDK/HTTP exception bodies, keys or signed URLs.
        print(json.dumps({'action': 'blocked', 'error_type': type(error).__name__,
                          'reason': 'Controller stopped; inspect local validation/state and live submission history.',
                          **safe_error_diagnostics(error)}))
        raise SystemExit(1)
