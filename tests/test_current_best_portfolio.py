"""Prevent a lower aggregate score from overwriting another merge's case gains."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.update_current_best_portfolio import require_casewise_nonregression


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


if __name__ == '__main__':
    unittest.main()
