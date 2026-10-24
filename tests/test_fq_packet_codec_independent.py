"""Independent mutable-array ownership control for the future-only codec."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import fq_packet_codec as codec


class IndependentPacketOwnership(unittest.TestCase):
    def test_deduplicated_blocks_do_not_alias_decoded_arrays_or_input(self):
        original = np.arange(384, dtype='>f8').reshape(2, 64, 3)
        arrays = {
            'old': original,
            'proposal': original.copy(),
            'metadata_json': np.frombuffer(b'{"status":"UNVERIFIED"}', np.uint8),
            'scalar': np.array(-0., dtype='>f8'),
        }
        expected = {name: value.tobytes(order='C') for name, value in arrays.items()}
        encoded = codec.encode(arrays)
        decoded = codec.decode(encoded)
        self.assertEqual(list(decoded), list(arrays))
        self.assertFalse(np.shares_memory(decoded['old'], decoded['proposal']))
        decoded['old'][0, 0, 0] = 991.
        self.assertEqual(decoded['proposal'].tobytes(), expected['proposal'])
        self.assertEqual(original.tobytes(), expected['old'])
        # The packet remains self-contained and immutable after mutable views
        # from an earlier decode are changed.
        again = codec.decode(encoded)
        for name, value in again.items():
            self.assertEqual(value.shape, arrays[name].shape)
            self.assertEqual(value.dtype, arrays[name].dtype)
            self.assertEqual(value.tobytes(order='C'), expected[name])


if __name__ == '__main__':
    unittest.main()
