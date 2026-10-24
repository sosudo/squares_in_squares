from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from fq_night_seed_campaign import excess_interval,checkpoint_directory
from extract_broad_active_frontier import orient


class RectangleExcessTests(unittest.TestCase):
    def test_rectangular_excess_is_maximum_of_both_offset_spans(self):
        p=np.array([[.5,.5,0.],[3.,17.25,0.]])
        interval=excess_interval(p,3,17)
        self.assertLessEqual(Decimal(interval['lower']),Decimal('.75'))
        self.assertGreaterEqual(Decimal(interval['upper']),Decimal('.75'))
        self.assertLess(Decimal(interval['upper'])-Decimal(interval['lower']),Decimal('1e-55'))

    def test_transpose_preserves_the_matching_container_excess(self):
        p=np.array([[.5,.5,0.],[3.,17.25,0.]])
        q=orient(p,True,1,1)
        first=excess_interval(p,3,17)
        second=excess_interval(q,17,3)
        self.assertLess(abs(float(first['upper'])-float(second['upper'])),1e-12)

    def test_final_checkpoint_preserves_same_count_progress_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            progress=checkpoint_directory(root,5,'running')
            (progress/'proof').write_text('immutable progress evidence')
            final=checkpoint_directory(root,5,'complete')
            self.assertNotEqual(progress,final)
            self.assertTrue(final.is_dir())
            self.assertEqual((progress/'proof').read_text(),'immutable progress evidence')


if __name__=='__main__':unittest.main()
