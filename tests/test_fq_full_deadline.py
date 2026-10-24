"""A whole-trial deadline must escape metric-style Exception handlers."""
from pathlib import Path
import signal
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_full_pilot


class DeadlineTests(unittest.TestCase):
    def test_deadline_escapes_swallowing_metric_handler(self):
        def metric_style_trial(job):
            try:
                time.sleep(.2)
            except Exception:
                return {'status': 'swallowed-deadline'}, None
            return {'status': 'missed-deadline'}, None
        job = ('10_10_1', None, 'polish', '', '', 1, .03, time.monotonic()+5)
        handler_before = signal.getsignal(signal.SIGALRM)
        with patch.object(fq_full_pilot, 'trial', metric_style_trial):
            result, donor = fq_full_pilot.checked_trial((job, 11.))
        self.assertEqual(result['status'], 'whole-trial-timeout')
        self.assertIsNone(donor)
        self.assertLess(result['seconds'], .15)
        self.assertIs(signal.getsignal(signal.SIGALRM), handler_before)


if __name__ == '__main__':
    unittest.main()
