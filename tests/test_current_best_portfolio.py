"""Prevent a lower aggregate score from overwriting another merge's case gains."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.update_current_best_portfolio import require_casewise_nonregression
from scripts import submission_scheduler as scheduler
from scripts import update_current_best_portfolio as updater


class CurrentBestCaseGate(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def record(self, label, changed=None, same_hash=False):
        changed = changed or {}
        results = [{'n': n, 'side_lower': changed.get(n, '10'),
                    'side_upper': changed.get(n, '10')} for n in range(1, 1001)]
        hashes = {str(n): ('same' if same_hash or n not in changed else label) for n in range(1, 1001)}
        official = self.root / (label + '-official.json')
        independent = self.root / (label + '-independent.json')
        official.write_text(json.dumps({'puzzle_hashes': hashes}))
        independent.write_text(json.dumps({'results': results}))
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        return {'raw': {'official_report': str(official), 'official_report_sha256': digest(official)},
                'independent_report': {'path': str(independent), 'sha256': digest(independent)}}

    def test_lower_total_with_one_case_regression_is_rejected(self):
        # Current wins on n20. A stale parallel branch wins more on n10 but
        # restores n20 to its older, worse geometry despite the lower total.
        previous = self.record('previous', {20: '9'})
        proposed = self.record('proposed', {10: '8'})
        with self.assertRaisesRegex(ValueError, 'n=20'):
            require_casewise_nonregression(previous, proposed)

    def test_exact_row_reuse_accepts_different_interval_rounding(self):
        previous = self.record('previous')
        proposed = self.record('proposed', {10: '10.000000000000000000000001'}, same_hash=True)
        require_casewise_nonregression(previous, proposed)

    def test_separated_interval_improvement_is_accepted(self):
        previous = self.record('previous')
        proposed = self.record('proposed', {10: '9.999'})
        require_casewise_nonregression(previous, proposed)

    def test_modified_previous_report_is_rejected(self):
        previous = self.record('previous')
        proposed = self.record('proposed', {10: '9'})
        Path(previous['independent_report']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'independent case report changed'):
            require_casewise_nonregression(previous, proposed)


class CurrentBestAuthorization(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.policy = self.root / 'authorization.json'
        self.write_policy('22.24')
        patcher = patch.object(updater, 'load_authorization_policy',
                               side_effect=lambda: scheduler.load_authorization_policy(self.policy))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_policy(self, ceiling):
        self.policy.write_text(json.dumps({'submission_score_must_be_strictly_below': ceiling,
                                          'strict_improvement_required': True,
                                          'minimum_interval_seconds': 3600}))

    def fixture(self, score=22.297):
        proof = {'schema_version': 2, 'metric_sha256': updater.METRIC_SHA,
                 'scores_agree_within_1e_10': True, 'absolute_score_difference': 0.,
                 # Historical proof metadata is preserved, not used as authorization.
                 'user_submission_score_threshold': 22.3,
                 'eligible_under_user_score_threshold': True}
        for role, key in [('raw', 'raw_source'), ('safe', 'safe_submission'),
                          ('roundtrip', 'roundtrip_submission')]:
            csv = self.root / (role + '.csv')
            csv.write_text('unchanged certified fixture ' + role)
            report = csv.with_name(csv.stem + '-official.json')
            report.write_text(json.dumps({'sha256': updater.digest(csv), 'valid': True,
                'invalid_count': 0, 'puzzles': 1000, 'rows': 500500,
                'metric_sha256': updater.METRIC_SHA, 'score': score,
                'reuse': {'evaluated': 1000, 'reused': 0}}))
            proof.update({key: str(csv), role + '_sha256': updater.digest(csv),
                          role + '_official_report_sha256': updater.digest(report),
                          role + '_score': score})
        interval = self.root / 'independent.json'
        interval.write_text(json.dumps({'valid': True, 'sha256': proof['raw_sha256'],
            'puzzles': 1000, 'rows': 500500, 'results': [{'n': n} for n in range(1, 1001)]}))
        proof['composition_merge_provenance'] = {'path': str(interval), 'sha256': updater.digest(interval)}
        target = self.root / 'canonical.json'
        target.write_text(json.dumps(proof))
        return target

    def test_same_csv_refreshes_live_policy_but_preserves_historical_proof(self):
        proof = self.fixture()
        proof_bytes = proof.read_bytes()
        previous = updater.certified_record(proof)
        previous.update(user_submission_score_threshold=22.3,
                        eligible_under_user_score_threshold=True,
                        authorization_policy={'score_ceiling': '22.3', 'sha256': 'old'},
                        historical_note='preserved')
        pointer = self.root / 'current.json'
        pointer.write_text(json.dumps(previous))
        with patch.object(updater, 'require_casewise_nonregression') as case_gate:
            result = updater.update(proof, pointer)
            case_gate.assert_not_called()
        self.assertFalse(result['eligible_under_user_score_threshold'])
        self.assertEqual(result['user_submission_score_threshold'], 22.24)
        self.assertEqual(result['authorization_policy']['sha256'], updater.digest(self.policy))
        self.assertEqual(result['historical_note'], 'preserved')
        for role in ('raw', 'safe', 'roundtrip'):
            self.assertEqual(result[role], previous[role])
        self.assertEqual(json.loads(pointer.read_text()), result)
        self.assertEqual(proof.read_bytes(), proof_bytes)

    def test_live_policy_strict_boundary_and_tightening(self):
        for score, expected in ((22.239, True), (22.24, False), (22.297, False)):
            with self.subTest(score=score):
                result = updater.certified_record(self.fixture(score))
                self.assertEqual(result['eligible_under_user_score_threshold'], expected)
        self.write_policy('22.23')
        result = updater.certified_record(self.fixture(22.239))
        self.assertFalse(result['eligible_under_user_score_threshold'])
        self.assertEqual(result['user_submission_score_threshold'], 22.23)

    def test_missing_or_weakened_policy_cannot_publish_pointer(self):
        proof = self.fixture()
        pointer = self.root / 'current.json'
        self.write_policy('22.3')
        with self.assertRaises(ValueError):
            updater.update(proof, pointer)
        self.assertFalse(pointer.exists())
        self.policy.unlink()
        with self.assertRaises(FileNotFoundError):
            updater.update(proof, pointer)
        self.assertFalse(pointer.exists())

    def test_policy_is_reloaded_after_certification_before_pointer_write(self):
        proof = self.fixture(22.239)
        original = updater.certified_record
        def certify_then_tighten(path):
            record = original(path)
            self.assertTrue(record['eligible_under_user_score_threshold'])
            self.write_policy('22.23')
            return record
        with patch.object(updater, 'certified_record', side_effect=certify_then_tighten):
            result = updater.update(proof, self.root / 'current.json')
        self.assertFalse(result['eligible_under_user_score_threshold'])
        self.assertEqual(result['authorization_policy']['sha256'], updater.digest(self.policy))
        self.assertEqual(result['user_submission_score_threshold'], 22.23)


if __name__ == '__main__':
    unittest.main()
