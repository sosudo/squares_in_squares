import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
import fq_full_local_campaign as campaign


class FullLocalTests(unittest.TestCase):
    def test_contact_graph_and_translation_invariant_displacement(self):
        p = np.array([[.5,.5,0.],[1.5,.5,0.],[.5,1.5,0.],[1.5,1.5,0.]])
        selection = dict(free_indices=[0,1], frozen_indices=[2,3])
        self.assertEqual(campaign.contact_edges(p, [0]), {(0,1),(0,2),(0,3)})
        translated = p.copy(); translated[:,:2] += [3.,-8.]
        unchanged = campaign.displacement(p, translated, selection)
        self.assertEqual(unchanged['free_position_max'], 0.)
        self.assertEqual(unchanged['contacts_lost'], [])
        self.assertEqual(unchanged['contacts_gained'], [])
        translated[0,2] += .1
        changed = campaign.displacement(p, translated, selection)
        self.assertGreater(changed['free_angle_max_degrees'], 5.)
        self.assertTrue(changed['contacts_lost'])

    def test_mask_is_complete_disjoint_and_bounded(self):
        p = np.array([[x+.5,y+.5,.2 if x>=4 else 0.] for x in range(8) for y in range(8)])
        for count in [20,40,64]:
            frozen, selection = campaign.local_selection(p, 321, count, 1)
            free = set(selection['free_indices'])
            self.assertEqual(len(free), count)
            self.assertFalse(free & set(frozen))
            self.assertEqual(free | set(frozen), set(range(64)))

    def test_missing_zero_aspect_trace_never_reaches_decode_or_certification(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'n1-local-12.out').write_text('1 1\n.5 .5 0\n')
            result = subprocess.CompletedProcess([], 0, json.dumps({'soft':{'a0':.3}}),
                                                 'soft eps 0.2 hold 1\nsoft eps 0.1 hold 1\n')
            with patch.object(campaign, 'grouped_run', return_value=result), \
                 patch.object(campaign.fq, 'decode') as decode, \
                 patch.object(campaign, 'full_certificate') as certify:
                record, q = campaign.run_stage(np.array([[.5,.5,0.]]),1.,'local',
                    ['--soft-a0','.3','--soft-steps','2'],12,Path('/tmp/fake-fq'),directory,3.,time.monotonic()+4.)
            self.assertEqual(record['status'], 'failed-rigid-return-trace')
            self.assertIsNone(q); decode.assert_not_called(); certify.assert_not_called()
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0.)


if __name__ == '__main__':
    unittest.main()
