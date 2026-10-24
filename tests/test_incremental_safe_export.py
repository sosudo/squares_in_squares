"""Exact transport and fail-closed checks; fixture coordinates are not packings."""
import base64
import copy
import hashlib
import json
import lzma
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_incremental_safe_export_job import runtime_namespace,notebook_metadata,COMPRESSED_MANIFEST_RUNTIME


def sha(data):return hashlib.sha256(data).hexdigest()


class MetadataTests(unittest.TestCase):
    def test_requested_slug_matches_title_derived_slug(self):
        slug='sos54352/squares-portfolio-5cba3bdac3cf-incremental'
        metadata=notebook_metadata(slug)
        self.assertEqual(metadata['id'],slug)
        self.assertEqual(metadata['title'].lower().replace(' ','-'),slug.split('/')[-1])
        alternate='sos54352/squares-next-safe-checkpoint'
        self.assertEqual(notebook_metadata(alternate)['title'].replace(' ','-'),alternate.split('/')[-1])


class CompressedManifestTests(unittest.TestCase):
    def setUp(self):
        namespace={};exec(compile(COMPRESSED_MANIFEST_RUNTIME,'<manifest-test>','exec'),namespace)
        self.decode=namespace['_decode_embedded_manifest']
        self.manifest={'notice':'MIT — exact CRLF\r\n','nested':{'a':None,'b':True},
                       'decimal_coordinate':'0.1234567890123456789012345','score':22.300613633186703}
        self.raw=json.dumps(self.manifest,separators=(',',':'),ensure_ascii=False).encode()
        self.compressed=lzma.compress(self.raw,preset=6)
        self.payload=base64.b64encode(self.compressed).decode()

    def test_exact_notice_text_and_coordinate_string_roundtrip(self):
        actual=self.decode(self.payload,len(self.raw),sha(self.raw),sha(self.compressed))
        self.assertEqual(actual,self.manifest)
        self.assertEqual(actual['notice'].encode(),self.manifest['notice'].encode())

    def test_compressed_and_raw_hash_tampering_rejected(self):
        changed=bytearray(self.compressed);changed[len(changed)//2]^=1
        with self.assertRaisesRegex(ValueError,'Compressed manifest SHA256'):
            self.decode(base64.b64encode(changed).decode(),len(self.raw),sha(self.raw),sha(self.compressed))
        with self.assertRaisesRegex(ValueError,'Exact manifest SHA256'):
            self.decode(self.payload,len(self.raw),'0'*64,sha(self.compressed))

    def test_bounded_decoding_rejects_trailing_stream_and_wrong_size(self):
        joined=self.compressed+lzma.compress(b'extra')
        with self.assertRaisesRegex(ValueError,'stream or size'):
            self.decode(base64.b64encode(joined).decode(),len(self.raw),sha(self.raw),sha(joined))
        with self.assertRaisesRegex(ValueError,'stream or size'):
            self.decode(self.payload,len(self.raw)-1,sha(self.raw),sha(self.compressed))
        with self.assertRaisesRegex(ValueError,'Invalid embedded manifest size'):
            self.decode(self.payload,4*1024*1024,sha(self.raw),sha(self.compressed))


class IncrementalSafeExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns=runtime_namespace()
        lines=[b'id,n,square_id,x,y,angle\r\n'];rid=0
        for n in range(1,1001):
            for sid in range(n):
                lines.append(f'{rid},{n},{sid},0,0,0\r\n'.encode());rid+=1
        cls.parent=b''.join(lines);target=lines.copy()
        target[1]=b'0,1,0,0.123456789012345678901234567890,-0.00000000000000000001,0e-99\r\n'
        target[-1]=b'500499,1000,999,123.4500,1.25e-30,-0\r\n'
        cls.target=b''.join(target);cls.patch={'rows':[[0,target[1].decode()],[500499,target[-1].decode()]]}
        changed={0,500499}
        cls.manifest={'parent_csv_bytes':len(cls.parent),'parent_csv_sha256':sha(cls.parent),
            'csv_bytes':len(cls.target),'csv_sha256':sha(cls.target),'changed_rows':2,'changed_puzzles':[1,1000],
            'changed_parent_rows_sha256':cls.ns['_line_digest'](lines,changed,True),
            'changed_target_rows_sha256':cls.ns['_line_digest'](target,changed,True),
            'unchanged_rows_sha256':cls.ns['_line_digest'](lines,changed,False)}
        cls.payload,cls.manifest=cls.encoded(cls.patch,cls.manifest)

    @staticmethod
    def encoded(patch,manifest):
        manifest=dict(manifest);raw=json.dumps(patch,separators=(',',':')).encode();packed=lzma.compress(raw)
        manifest.update(patch_bytes=len(raw),patch_sha256=sha(raw),patch_compressed_sha256=sha(packed))
        return base64.b64encode(packed).decode(),manifest

    def test_preserves_all_bytes_including_long_decimals_and_signed_zero(self):
        actual=self.ns['apply_safe_row_patch'](self.parent,self.payload,self.manifest)
        self.assertEqual(actual,self.target)
        self.assertIn(b'0.123456789012345678901234567890,-0.00000000000000000001,0e-99',actual)

    def test_tampered_parent_rejected_before_patch(self):
        changed=self.parent.replace(b'0,1,0,0,0,0',b'0,1,0,1,0,0',1)
        with self.assertRaisesRegex(ValueError,'Parent SAFE-CSV'):
            self.ns['apply_safe_row_patch'](changed,self.payload,self.manifest)

    def test_tampered_compressed_patch_rejected(self):
        packed=bytearray(base64.b64decode(self.payload));packed[len(packed)//2]^=1
        with self.assertRaisesRegex(ValueError,'Compressed patch SHA256'):
            self.ns['apply_safe_row_patch'](self.parent,base64.b64encode(packed).decode(),self.manifest)

    def test_changed_coordinate_rejected_even_with_rehashed_patch_envelope(self):
        patch=copy.deepcopy(self.patch);patch['rows'][0][1]=patch['rows'][0][1].replace('0.123456789','0.923456789')
        payload,manifest=self.encoded(patch,self.manifest)
        with self.assertRaisesRegex(ValueError,'Changed coordinate strings'):
            self.ns['apply_safe_row_patch'](self.parent,payload,manifest)

    def test_patch_ids_and_parent_schema_fail_closed(self):
        patch=copy.deepcopy(self.patch);patch['rows'][0][1]=patch['rows'][0][1].replace('0,1,0,','0,1,1,',1)
        payload,manifest=self.encoded(patch,self.manifest)
        with self.assertRaisesRegex(ValueError,'square id'):
            self.ns['apply_safe_row_patch'](self.parent,payload,manifest)
        changed=self.parent.replace(b'0,1,0,0,0,0',b'0,1,1,0,0,0',1)
        rebound=dict(self.manifest,parent_csv_sha256=sha(changed))
        with self.assertRaisesRegex(ValueError,'square id'):
            self.ns['apply_safe_row_patch'](changed,self.payload,rebound)

    def test_duplicate_row_ids_are_rejected(self):
        patch=copy.deepcopy(self.patch);patch['rows'][1]=patch['rows'][0]
        payload,manifest=self.encoded(patch,self.manifest)
        with self.assertRaisesRegex(ValueError,'Duplicate, unsorted'):
            self.ns['apply_safe_row_patch'](self.parent,payload,manifest)


if __name__=='__main__':unittest.main()
