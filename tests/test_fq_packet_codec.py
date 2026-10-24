"""Byte fidelity and adversarial schema controls for the future-only codec."""
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import fq_packet_codec as codec


def exact(test,first,second):
    test.assertEqual(list(first),list(second))
    for name,a in first.items():
        b=second[name]
        test.assertEqual(a.shape,b.shape,name);test.assertEqual(a.dtype,b.dtype,name)
        test.assertEqual(a.tobytes(),b.tobytes(),name)


def unpack(raw):
    with zipfile.ZipFile(io.BytesIO(raw))as z:
        document=json.loads(z.read('manifest.json'));payload=z.read('payload.bin')
    document.pop('manifest_sha256');return document,payload


class PacketCodecTests(unittest.TestCase):
    def setUp(self):
        self.arrays={'first':np.arange(2*9*3,dtype='>f8').reshape(2,9,3),
                     'metadata_json':np.frombuffer(b'{"status":"UNVERIFIED","n":9}',dtype=np.uint8),
                     'accepted':np.array([True,False]),'scalar':np.array(-0.,dtype='<f8')}
        self.raw=codec.encode(self.arrays)

    def test_scalar_endian_empty_noncontiguous_and_bit_patterns(self):
        bits=np.array([0x7ff8000000001234,0xfff0000000000000,0x8000000000000000],dtype=np.uint64).view(np.float64)
        arrays=dict(self.arrays,nan_payload=bits,empty=np.empty((0,803,3),dtype='>i2'),
                    unicode=np.array(['λ','square'],dtype='>U6'),complex=np.array([1+2j],dtype='>c16'),
                    datetime=np.array(['2026-10-24'],dtype='datetime64[D]'),
                    noncontiguous=np.arange(120,dtype='<i4').reshape(4,10,3)[::-1,::2,:])
        raw=codec.encode(arrays);exact(self,arrays,codec.decode(raw,expected_sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(codec.decode(raw)['scalar'].shape,())
        with self.assertRaisesRegex(codec.CodecError,'external_packet_hash'):
            codec.decode(raw,expected_sha256='0'*64)

    def test_structured_subarray_titles_alignment_and_padding_bytes(self):
        inner=np.dtype([('x','>i2'),('v','<f4',(2,))],align=True)
        dtype=np.dtype({'names':['id','nested'],'formats':['>i4',(inner,(2,))],
                        'offsets':[0,8],'titles':['identifier',None],'itemsize':40},align=True)
        raw=bytearray((i*17)%256 for i in range(3*dtype.itemsize))
        values=np.ndarray((3,),dtype=dtype,buffer=raw)
        exact(self,{'structured':values},codec.decode(codec.encode({'structured':values})))
        # The padding byte pattern is part of the exact packet, even when a
        # structured-array copy would discard it.
        strided=values[::-1]
        exact(self,{'structured':strided},codec.decode(codec.encode({'structured':strided})))

    def test_mixedN_and_cross_array_dedup_independently_decodable(self):
        arrays={'n803':np.zeros((2,803,3)), 'n861':np.zeros((3,861,3)),
                'metadata_json':np.frombuffer(b'complete individual packet',np.uint8)}
        raw=codec.encode(arrays);exact(self,arrays,codec.decode(raw))
        document,payload=unpack(raw)
        self.assertLess(len(payload),sum(a.nbytes for a in arrays.values())/10)
        self.assertEqual(list(codec.decode(raw)),list(arrays))

    def test_valid_zip_payload_and_per_array_tampering_detected(self):
        document,payload=unpack(self.raw)
        changed=bytes([payload[0]^1])+payload[1:]
        with self.assertRaisesRegex(codec.CodecError,'payload_hash'):
            codec.decode(codec._archive(document,changed)[0])
        document['payload_sha256']=hashlib.sha256(changed).hexdigest()
        with self.assertRaisesRegex(codec.CodecError,'array_hash'):
            codec.decode(codec._archive(document,changed)[0])
        # Valid archive CRC and unchanged payload cannot hide altered indices.
        document,payload=unpack(self.raw);document['arrays'][0]['indices'][0]=len(document['pool_ends'])
        with self.assertRaisesRegex(codec.CodecError,'block_index'):
            codec.decode(codec._archive(document,payload)[0])

    def test_manifest_signature_canonical_form_and_duplicate_json_keys(self):
        document,payload=unpack(self.raw)
        with zipfile.ZipFile(io.BytesIO(self.raw))as z:metadata=z.read('manifest.json')
        changed=metadata.replace(b'"version":1',b'"version":2')
        for invalid in [changed,b' '+metadata,metadata.replace(b'"version":1',b'"version":1,"version":1')]:
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w')as z:z.writestr('manifest.json',invalid);z.writestr('payload.bin',payload)
            with self.assertRaises(codec.CodecError):codec.decode(out.getvalue())

    def test_invalid_shape_dtype_names_indices_pool_ends_and_schema(self):
        original,payload=unpack(self.raw)
        mutations=[
            lambda d:d['arrays'][0].update(shape=[-1,9,3]),
            lambda d:d['arrays'][0].update(shape=[1000000,1000000,3]),
            lambda d:d['arrays'][0].update(bytes=1),
            lambda d:d['arrays'][0].update(name='../escape'),
            lambda d:d['arrays'][1].update(name=d['arrays'][0]['name']),
            lambda d:d['arrays'][0].update(dtype={'kind':'plain','str':'|O'}),
            lambda d:d['arrays'][0]['indices'].__setitem__(0,True),
            lambda d:d['arrays'][0]['indices'].append(0),
            lambda d:d['pool_ends'].__setitem__(0,0),
            lambda d:d['pool_ends'].__setitem__(0,1000000000),
            lambda d:d.update(block_bytes=384),
            lambda d:d.update(unknown_schema_field=True),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                document=json.loads(json.dumps(original));mutate(document)
                with self.assertRaises(codec.CodecError):codec.decode(codec._archive(document,payload)[0])

    def test_object_encoder_and_npz_object_reader_rejected_without_pickle(self):
        objects=np.array([{'forbidden':'object pickle'}],dtype=object)
        with self.assertRaisesRegex(codec.CodecError,'object_metadata'):
            codec.encode({'object':objects})
        nested=np.empty(1,dtype=[('unsafe',object)])
        with self.assertRaisesRegex(codec.CodecError,'object_metadata'):codec.encode({'nested':nested})
        stream=io.BytesIO();np.savez(stream,object=objects)
        # The future codec does not call np.load at all: unknown ZIP members
        # are rejected before any NPY/pickle parser could execute.
        with patch.object(np,'load',side_effect=AssertionError('pickle parser must never run')):
            with self.assertRaises(codec.CodecError):codec.decode(stream.getvalue())

    def test_central_directory_is_bounded_before_zipfile_parser(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w')as z:
            for i in range(5):z.writestr('extra'+str(i),b'x')
        malformed=[out.getvalue()]
        for offset,value in [(-12,0xffffffff),(-10,0xffff)]:
            raw=bytearray(self.raw);raw[offset:offset+2]=(value&0xffff).to_bytes(2,'little');malformed.append(bytes(raw))
        with patch.object(codec.zipfile,'ZipFile',side_effect=AssertionError('directory parser must not run')):
            for raw in malformed:
                with self.assertRaisesRegex(codec.CodecError,'directory_envelope'):codec.decode(raw)

    def test_top_level_subarray_cannot_silently_expand_declared_scalar_shape(self):
        raw=codec.encode({'tiny':np.array([1,2],dtype=np.uint8)})
        document,payload=unpack(raw);record=document['arrays'][0]
        record['shape']=[];record['dtype']={'kind':'subarray','base':{'kind':'plain','str':'|u1'},'shape':[2]}
        with self.assertRaisesRegex(codec.CodecError,'top_level_subarray'):
            codec.decode(codec._archive(document,payload)[0])

    def test_truncations_compression_and_member_size_resource_limits(self):
        for length in [0,1,len(self.raw)//2,len(self.raw)-22,len(self.raw)-1]:
            with self.subTest(length=length):
                with self.assertRaises(codec.CodecError):codec.decode(self.raw[:length])
        document,payload=unpack(self.raw)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED)as z:
            z.writestr('manifest.json',b'{}');z.writestr('payload.bin',b'x'*10000)
        with self.assertRaisesRegex(codec.CodecError,'compressed'):codec.decode(out.getvalue())
        for limits in [replace(codec.DEFAULT_LIMITS,packet_bytes=20),
                       replace(codec.DEFAULT_LIMITS,decoded_bytes=20),
                       replace(codec.DEFAULT_LIMITS,payload_bytes=20),
                       replace(codec.DEFAULT_LIMITS,manifest_bytes=20),
                       replace(codec.DEFAULT_LIMITS,indices=1),replace(codec.DEFAULT_LIMITS,pool_blocks=1)]:
            with self.subTest(limits=limits):
                with self.assertRaises(codec.CodecError):codec.decode(self.raw,limits=limits)
                with self.assertRaises(codec.CodecError):codec.encode(self.arrays,limits=limits)


if __name__=='__main__':unittest.main()
