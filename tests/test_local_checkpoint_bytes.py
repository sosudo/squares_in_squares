import hashlib
import lzma
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import local_checkpoint_bytes as codec


class LocalCheckpointTests(unittest.TestCase):
    def test_exact_mixed_line_endings_and_unchanged_byte_runs(self):
        parent=b'id,n,x\r\n0,1,0.50000000000000\r\n1,2,1.5\r\n2,2,2.5\r\n'
        targets=[parent,b'id,n,x\r\n0,1,0.50000000000001\r\n1,2,1.5\r\n2,2,2.5\r\n',
                 b'id,n,x\n0,1,0.5\n1,2,1.5\n2,2,2.5\n']
        for target in targets:
            patch,record=codec.make_patch(parent,target)
            self.assertEqual(codec.apply_patch(parent,patch,record),target)
            self.assertEqual(codec.make_patch(parent,target),(patch,record))

    def test_wrong_parent_and_compressed_or_raw_tampering_refused(self):
        parent=b'a\r\nb\r\n';target=b'a\nbc\n';patch,record=codec.make_patch(parent,target)
        with self.assertRaisesRegex(ValueError,'wrong_parent'):
            codec.apply_patch(parent[:-1]+b'x',patch,record)
        with self.assertRaisesRegex(ValueError,'compressed_patch'):
            codec.apply_patch(parent,patch[:-1]+bytes([patch[-1]^1]),record)
        with self.assertRaises(ValueError):codec.apply_patch(parent,patch[:-1],record)

    def test_valid_compressed_but_invalid_copy_bounds_fails_closed(self):
        parent=b'a\n';raw=codec.MAGIC+b'C'+codec._varint(100)+codec._varint(1)
        packed=lzma.compress(raw,preset=6)
        record=dict(parent_bytes=len(parent),parent_sha256=codec.sha(parent),target_bytes=1,
            target_sha256=codec.sha(b'x'),patch_bytes=len(raw),patch_sha256=codec.sha(raw),
            compressed_bytes=len(packed),compressed_sha256=codec.sha(packed),operations=1)
        with self.assertRaisesRegex(ValueError,'copy_bounds'):codec.apply_patch(parent,packed,record)


if __name__=='__main__':unittest.main()
