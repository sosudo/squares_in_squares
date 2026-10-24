from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_frame300_check as subject


class FrameHeldPathTests(unittest.TestCase):
    def test_complete_true_held_return_and_compression_negative(self):
        logs='\n'.join(f'round r {(.4*(1-k/12)**2):.4f} hold 18.82412339 viol0'for k in range(1,13))
        report={'round':{'r0':.4,'s_soft':18.82412339,'s_hold':18.82412339}}
        self.assertTrue(subject.held_trace(subject.HELD,18.82412339,report,logs)['valid'])
        self.assertFalse(subject.held_trace(subject.HELD+['--round-compress'],18.82412339,report,logs)['valid'])


if __name__=='__main__':unittest.main()
