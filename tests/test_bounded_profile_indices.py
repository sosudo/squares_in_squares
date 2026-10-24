import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from compose_gadgets import BOUNDED_INDEX_HELPER


class BoundedProfileIndexTests(unittest.TestCase):
    def setUp(self):
        namespace={'cp':np,'np':np}
        exec(BOUNDED_INDEX_HELPER,namespace)
        self.compact=namespace['_bounded_active_indices']

    def test_matches_full_compaction_across_chunks(self):
        rng=np.random.default_rng(593)
        values=rng.integers(0,2**63,size=(13,17,9),dtype=np.uint64)
        values[rng.random(values.shape)<.73]=np.uint64(0xffffffffffffffff)
        expected=np.flatnonzero(values!=np.uint64(0xffffffffffffffff))
        for size in [1,7,127,10000]:
            np.testing.assert_array_equal(self.compact(values,size),expected)

    def test_empty_and_all_finite_states(self):
        full=np.full((11,7),np.uint64(0xffffffffffffffff))
        np.testing.assert_array_equal(self.compact(full,13),np.array([],dtype=np.int64))
        full[:]=123
        np.testing.assert_array_equal(self.compact(full,13),np.arange(full.size))


if __name__=='__main__':unittest.main()
