import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import fq_joint_seed_check as subject


class HeldTraceTests(unittest.TestCase):
    def fixture(self):
        logs = '\n'.join(f'round r {(.15*(1-k/12)**2):.4f} hold 17.82287569 viol 0'
                         for k in range(1, 13))
        return logs, {'round':{'r0':.15, 's_soft':17.822875689195, 's_hold':17.822875689195}}

    def test_true_held_return(self):
        logs, report = self.fixture()
        self.assertTrue(subject.held_trace(subject.HELD, 17.822875689195, report, logs)['valid'])

    def test_compressed_or_changed_box_rejected(self):
        logs, report = self.fixture()
        self.assertFalse(subject.held_trace(subject.HELD+['--round-compress'], 17.822875689195, report, logs)['valid'])
        report['round']['s_hold'] += .0001
        self.assertFalse(subject.held_trace(subject.HELD, 17.822875689195, report, logs)['valid'])

    def test_partial_or_nonzero_return_rejected(self):
        logs, report = self.fixture()
        self.assertFalse(subject.held_trace(subject.HELD, 17.822875689195, report, '\n'.join(logs.splitlines()[:-1]))['valid'])
        self.assertFalse(subject.held_trace(subject.HELD, 17.822875689195, report, logs.rsplit('0.0000', 1)[0]+'0.0001 hold 17.82287569 viol 0')['valid'])


if __name__ == '__main__':
    unittest.main()
