"""Submission safety gates and ambiguous-request recovery without network calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import submission_scheduler as scheduler


NOW = datetime(2026, 10, 24, 8, tzinfo=timezone.utc)
POLICY = {'score_ceiling': '22.24', 'minimum_interval_seconds': 3600, 'sha256': 'unit-test-policy'}


class FakeGateway:
    def __init__(self, history=None, quota=10, ambiguous=False, accepted_on_error=False):
        self.history = deepcopy(history or [])
        self.quota = quota
        self.ambiguous = ambiguous
        self.accepted_on_error = accepted_on_error
        self.submitted = 0
        self.verified = 0
        self.snapshots = 0

    def snapshot(self):
        self.snapshots += 1
        return {'history': deepcopy(self.history),
                'limits': {'num_today': 10 - self.quota, 'num_allowed_now': self.quota}}

    def verify_notebook(self, notebook, sha):
        self.verified += 1

    def submit_notebook(self, notebook, description):
        self.submitted += 1
        if not self.ambiguous or self.accepted_on_error:
            self.history.append({'ref': 123, 'date': NOW.isoformat(), 'status': 'pending',
                                 'description': description, 'public_score': None})
        if self.ambiguous:
            raise TimeoutError('A signed URL or secret must never be logged')
        return {'ref': 123}


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.fixture('new', 22.)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, name, score):
        csv = self.root / (name + '.csv'); csv.write_text('immutable-' + name)
        rounded = self.root / (name + '-float.csv'); rounded.write_text('numeric-' + name)
        def report(path, target):
            path.write_text(json.dumps({'sha256': scheduler.digest(target), 'valid': True,
                'invalid_count': 0, 'puzzles': 1000, 'rows': 500500,
                'metric_sha256': scheduler.METRIC, 'score': score}))
        raw_report = self.root / (name + '-raw.json'); report(raw_report, csv)
        roundtrip_report = self.root / (name + '-float.json'); report(roundtrip_report, rounded)
        transport = self.root / (name + '-transport.json')
        transport.write_text(json.dumps({'safe_sha256': scheduler.digest(csv),
            'roundtrip_sha256': scheduler.digest(rounded), 'metric_sha256': scheduler.METRIC,
            'safe_invalid_count': 0, 'roundtrip_invalid_count': 0, 'roundtrip_evaluated': 1000,
            'same_binary64_score': True, 'safe_score': score, 'roundtrip_score': score}))
        notebook = {'ref': 'owner/immutable-notebook', 'version': 2, 'output_file': 'submission.csv'}
        proof = {**notebook, 'status': 'complete', 'is_private': True,
                 'output_sha256': scheduler.digest(csv), 'verified_at': NOW.isoformat()}
        return scheduler.make_candidate(csv, raw_report, rounded, roundtrip_report,
                                        transport, notebook, proof)

    def state_with_previous(self, score=23., seconds_ago=7200, status='complete'):
        state = scheduler.new_state()
        state['submitted']['previous-sha'] = {'ref': 7, 'sha256': 'previous-sha',
            'validated_score': str(score), 'submitted_at': (NOW - timedelta(seconds=seconds_ago)).isoformat(),
            'status': status, 'notebook': {}, 'marker': '[previous]'}
        return state

    def run_controller(self, gateway=None, state=None, execute=False):
        saved = []
        gateway = gateway or FakeGateway()
        result, final = scheduler.controller([self.candidate], state or scheduler.new_state(),
            gateway, NOW, execute, lambda value: saved.append(deepcopy(value)), policy=POLICY)
        return result, final, saved

    def test_changed_csv_is_rejected_before_any_api_request(self):
        Path(self.candidate['csv']['path']).write_text('changed after certification')
        gateway = FakeGateway()
        with self.assertRaises(ValueError):
            self.run_controller(gateway, execute=True)
        self.assertEqual(gateway.snapshots, 0)
        self.assertEqual(gateway.submitted, 0)

    def test_float_report_must_bind_the_same_transport(self):
        bad = deepcopy(self.candidate)
        bad['roundtrip_csv'] = bad['csv']
        with self.assertRaises(ValueError):
            scheduler.validate_candidate(bad)

    def test_queue_snapshot_survives_later_experiment_overwrites(self):
        frozen = scheduler.freeze_candidate(self.candidate, self.root / 'snapshots')
        Path(self.candidate['csv']['path']).write_text('new experiment at reused filename')
        self.assertEqual(scheduler.validate_candidate(frozen), scheduler.numeric_score(22.))
        self.assertNotEqual(frozen['csv']['path'], self.candidate['csv']['path'])

    def test_complete_cached_transport_coverage_and_float_rounding_are_accepted(self):
        transport_path = Path(self.candidate['transport_report']['path'])
        summary = json.loads(transport_path.read_text())
        rounded_path = Path(self.candidate['roundtrip_report']['path'])
        rounded = json.loads(rounded_path.read_text()); rounded['score'] = 22.000000000000004
        rounded_path.write_text(json.dumps(rounded))
        self.candidate['roundtrip_report'] = scheduler.binding(rounded_path)
        summary.update(roundtrip_score=rounded['score'], roundtrip_case_coverage=1000,
            roundtrip_evaluated=14, roundtrip_reused=986,
            roundtrip_reuse={'evaluated': 14, 'reused': 986}, same_binary64_score=False,
            safe_official_report_sha256=self.candidate['raw_report']['sha256'],
            roundtrip_official_report_sha256=self.candidate['roundtrip_report']['sha256'])
        transport_path.write_text(json.dumps(summary))
        self.candidate['transport_report'] = scheduler.binding(transport_path)
        self.assertEqual(scheduler.validate_candidate(self.candidate), scheduler.numeric_score(rounded['score']))

    def test_incomplete_or_contradictory_cached_transport_coverage_is_rejected(self):
        base = {'roundtrip_case_coverage': 1000, 'roundtrip_evaluated': 14,
                'roundtrip_reused': 986, 'roundtrip_reuse': {'evaluated': 14, 'reused': 986}}
        self.assertTrue(scheduler.full_transport_coverage(base))
        for patch in ({'roundtrip_case_coverage': 999}, {'roundtrip_reused': 985},
                      {'roundtrip_evaluated': -1, 'roundtrip_reused': 1001},
                      {'roundtrip_reuse': {'evaluated': 15, 'reused': 985}}):
            self.assertFalse(scheduler.full_transport_coverage({**base, **patch}))

    def test_pending_remote_submission_blocks_even_after_one_hour(self):
        gateway = FakeGateway([{'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(),
            'status': 'pending', 'description': '', 'public_score': None}])
        result, _, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'wait')
        self.assertEqual(gateway.submitted, 0)

    def test_exact_hour_boundary_and_strict_score_improvement(self):
        result, _, _ = self.run_controller(state=self.state_with_previous(seconds_ago=3599))
        self.assertEqual(result['action'], 'wait')
        result, _, _ = self.run_controller(state=self.state_with_previous(seconds_ago=3600))
        self.assertEqual(result['action'], 'ready')
        result, _, _ = self.run_controller(state=self.state_with_previous(score=22.))
        self.assertEqual(result['action'], 'wait')

    def test_live_quota_exhaustion_prevents_submission(self):
        result, _, _ = self.run_controller(FakeGateway(quota=0), execute=True)
        self.assertEqual(result['action'], 'wait')
        self.assertIn('allowance', result['reason'])

    def test_hard_ten_daily_limit_even_if_live_allowance_disagrees(self):
        history = [{'ref': i, 'date': (NOW - timedelta(hours=2)).isoformat(),
                    'status': 'error', 'description': '', 'public_score': None} for i in range(10)]
        gateway = FakeGateway(history, quota=10)
        result, _, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'wait')
        self.assertEqual(gateway.submitted, 0)

    def test_dry_run_never_submits_or_verifies_outputs_or_persists_state(self):
        gateway = FakeGateway()
        result, _, saved = self.run_controller(gateway)
        self.assertEqual(result['action'], 'ready')
        self.assertEqual((gateway.submitted, gateway.verified, len(saved)), (0, 0, 0))

    def test_intent_is_persisted_before_acknowledged_submission(self):
        gateway = FakeGateway()
        result, state, saved = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'submitted')
        self.assertIsNotNone(saved[0]['pending'])
        self.assertIsNone(state['pending'])
        self.assertIn(self.candidate['id'], state['submitted'])
        self.assertEqual(gateway.verified, 1)
        self.assertEqual(gateway.snapshots, 2)

    def test_lost_acknowledgment_reconciles_history_without_retry(self):
        gateway = FakeGateway(ambiguous=True, accepted_on_error=True)
        result, state, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'reconciled')
        self.assertEqual(gateway.submitted, 1)
        self.assertIsNone(state['pending'])
        self.run_controller(gateway, state, execute=True)
        self.assertEqual(gateway.submitted, 1)

    def test_ambiguous_no_history_match_stays_blocked_next_tick(self):
        gateway = FakeGateway(ambiguous=True)
        result, state, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'ambiguous')
        self.assertIsNotNone(state['pending'])
        result, _, _ = self.run_controller(gateway, state, execute=True)
        self.assertEqual(result['action'], 'blocked')
        self.assertEqual(gateway.submitted, 1)

    def test_same_hash_is_never_submitted_twice(self):
        state = scheduler.new_state()
        scheduler.accept(state, self.candidate,
            {'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(), 'status': 'complete'}, NOW)
        gateway = FakeGateway()
        result, _, _ = self.run_controller(gateway, state, execute=True)
        self.assertEqual(result['action'], 'wait')
        self.assertEqual(gateway.submitted, 0)

    def test_score_mismatch_requires_review(self):
        state = self.state_with_previous(score=22.)
        gateway = FakeGateway([{'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(),
            'status': 'complete', 'description': '', 'public_score': '22.2'}])
        result, _, _ = self.run_controller(gateway, state, execute=True)
        self.assertEqual(result['action'], 'blocked')
        self.assertEqual(gateway.submitted, 0)

    def test_unknown_rounded_score_does_not_create_false_tiny_improvement(self):
        self.candidate = self.fixture('tiny', 22.00000000001)
        gateway = FakeGateway([{'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(),
            'status': 'complete', 'description': '', 'public_score': '22.0000000001'}])
        result, _, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'wait')

    def test_tracked_public_result_cannot_be_ignored_for_score_comparison(self):
        self.candidate = self.fixture('worse-than-live', 22.200000008)
        state = self.state_with_previous(score=22.200000009)
        gateway = FakeGateway([{'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(),
            'status': 'complete', 'description': '', 'public_score': '22.2000000000'}])
        direct = scheduler.plan([self.candidate], state, gateway.snapshot(), NOW, POLICY)
        self.assertEqual(direct['action'], 'wait')
        result, _, _ = self.run_controller(gateway, state, execute=True)
        self.assertEqual(result['action'], 'blocked')
        self.assertEqual(gateway.submitted, 0)

    def test_adopting_old_receipt_cannot_discard_an_ambiguous_intent(self):
        state = scheduler.new_state()
        state['pending'] = {'candidate': self.candidate, 'marker': scheduler.marker(self.candidate),
                            'request_started_at': NOW.isoformat()}
        previous = self.fixture('old-receipt', 23.)
        row = {'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(), 'status': 'complete',
               'description': '', 'public_score': '23.0000000000'}
        original = deepcopy(state)
        with self.assertRaises(ValueError):
            scheduler.adopt_existing(state, previous, row, NOW)
        self.assertEqual(state, original)

    def test_same_hash_old_receipt_without_pending_marker_is_not_adopted(self):
        state = scheduler.new_state()
        state['pending'] = {'candidate': self.candidate, 'marker': scheduler.marker(self.candidate),
                            'request_started_at': NOW.isoformat()}
        row = {'ref': 7, 'date': (NOW - timedelta(hours=2)).isoformat(), 'status': 'complete',
               'description': 'An older submission without this intent marker', 'public_score': '22.0'}
        with self.assertRaises(ValueError):
            scheduler.adopt_existing(state, self.candidate, row, NOW)
        self.assertIsNotNone(state['pending'])

    def policy_file(self, ceiling='22.24'):
        path = self.root / 'authorization-policy.json'
        path.write_text(json.dumps({'submission_score_must_be_strictly_below': ceiling,
            'strict_improvement_required': True, 'minimum_interval_seconds': 3600}))
        return path

    def test_new_ceiling_blocks_old_queue_and_exact_boundary(self):
        for score in (22.24, 22.240000001, 22.2973085390, 22.3, 23.):
            self.candidate = self.fixture('threshold-' + str(score), score)
            gateway = FakeGateway()
            result, _, _ = self.run_controller(gateway, execute=True)
            self.assertEqual(result['action'], 'blocked')
            self.assertEqual(result['score_must_be_strictly_below'], '22.24')
            self.assertEqual(gateway.submitted, 0)
        self.candidate = self.fixture('below-threshold', 22.239)
        result, _, _ = self.run_controller()
        self.assertEqual(result['action'], 'ready')

    def test_persisted_policy_survives_controller_restarts(self):
        self.candidate = self.fixture('persistently-blocked', 22.30001)
        policy_path = self.policy_file()
        gateway = FakeGateway()
        with patch.object(scheduler, 'AUTHORIZATION_POLICY', policy_path):
            for _ in range(2):
                result, _ = scheduler.controller([self.candidate], scheduler.new_state(),
                    gateway, NOW, execute=True)
                self.assertEqual(result['action'], 'blocked')
        self.assertEqual(gateway.submitted, 0)

    def test_22_point_239_still_requires_strict_improvement_and_full_hour(self):
        self.candidate = self.fixture('new-range', 22.239)
        for previous, elapsed, expected in ((22.297, 3599, 'wait'),
                                            (22.297, 3600, 'ready'),
                                            (22.239, 7200, 'wait'),
                                            (22.238, 7200, 'wait')):
            with self.subTest(previous=previous, elapsed=elapsed):
                result, _, _ = self.run_controller(
                    state=self.state_with_previous(score=previous, seconds_ago=elapsed))
                self.assertEqual(result['action'], expected)

    def test_old_explicit_policy_is_rejected_before_any_gateway_call(self):
        gateway = FakeGateway()
        with self.assertRaisesRegex(ValueError, 'authorization score ceiling'):
            scheduler.controller([self.candidate], scheduler.new_state(), gateway, NOW,
                                 execute=True, policy={**POLICY, 'score_ceiling': '22.3'})
        self.assertEqual((gateway.snapshots, gateway.verified, gateway.submitted), (0, 0, 0))

    def test_raw_below_ceiling_but_numeric_roundtrip_at_ceiling_is_blocked(self):
        self.candidate = self.fixture('transport-crosses-ceiling', 22.239999999999997)
        path = Path(self.candidate['roundtrip_report']['path']); report = json.loads(path.read_text())
        report['score'] = 22.24; path.write_text(json.dumps(report))
        self.candidate['roundtrip_report'] = scheduler.binding(path)
        path = Path(self.candidate['transport_report']['path']); summary = json.loads(path.read_text())
        summary.update(roundtrip_score=22.24, same_binary64_score=False)
        path.write_text(json.dumps(summary)); self.candidate['transport_report'] = scheduler.binding(path)
        gateway = FakeGateway()
        result, _, _ = self.run_controller(gateway, execute=True)
        self.assertEqual(result['action'], 'blocked')
        self.assertEqual(gateway.submitted, 0)

    def test_missing_policy_prevents_direct_execute_before_api_initialization(self):
        with patch.object(scheduler, 'AUTHORIZATION_POLICY', self.root / 'missing.json'), \
             patch.object(sys, 'argv', ['submission_scheduler.py', 'check', '--execute']), \
             patch.object(scheduler, 'KaggleGateway') as gateway:
            with self.assertRaises(FileNotFoundError):
                scheduler.main()
            gateway.assert_not_called()

    def test_policy_is_reloaded_after_remote_verification_before_mutation(self):
        self.candidate = self.fixture('policy-tightened', 22.23)
        policy_path = self.policy_file()
        class TighteningGateway(FakeGateway):
            def verify_notebook(inner, notebook, sha):
                super().verify_notebook(notebook, sha)
                self.policy_file('22.2')
        gateway = TighteningGateway()
        with patch.object(scheduler, 'AUTHORIZATION_POLICY', policy_path):
            result, state = scheduler.controller([self.candidate], scheduler.new_state(),
                gateway, NOW, execute=True)
        self.assertEqual(result['action'], 'blocked')
        self.assertIsNone(state['pending'])
        self.assertEqual(gateway.submitted, 0)

    def test_policy_cannot_weaken_score_ceiling_or_hourly_interval(self):
        path = self.policy_file('22.3')
        with self.assertRaises(ValueError):
            scheduler.load_authorization_policy(path)
        for patch_value in ({'strict_improvement_required': False}, {'minimum_interval_seconds': 3599}):
            path = self.policy_file(); data = json.loads(path.read_text()); data.update(patch_value)
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                scheduler.load_authorization_policy(path)


if __name__ == '__main__':
    unittest.main()
