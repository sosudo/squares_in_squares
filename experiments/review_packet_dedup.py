"""Independent finite audit of the existing storage-only probe, not a codec.

All four original B32 packets are tested separately with metadata_json. No
production packet consumer or frozen job is modified.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import statistics
import time
import zipfile
import numpy as np
import probe_packet_dedup as probe


def sha(data):return hashlib.sha256(data).hexdigest()
def npz(arrays):
    stream=io.BytesIO();np.savez(stream,**arrays);return stream.getvalue()
def fields(arrays):
    return {k:dict(shape=list(a.shape),dtype=a.dtype.str,sha256=sha(a.tobytes()),
                   has_object=bool(a.dtype.hasobject)) for k,a in arrays.items()}
def exact(first,second):
    return (first.keys()==second.keys() and all(a.shape==second[k].shape and a.dtype==second[k].dtype
        and a.tobytes()==second[k].tobytes() for k,a in first.items()))


def run(out):
    start=time.perf_counter();deadline=start+55.
    original=Path('artifacts/fq-packet-dedup-probe-v1/report.json')
    pins=[p for row in json.loads(original.read_bytes())['records'] for p in row['source_packets']]
    records=[]
    for pin in pins:
        path=Path(pin['path']);source=path.read_bytes()
        if sha(source)!=pin['sha256']:raise ValueError('source_packet_changed')
        with np.load(io.BytesIO(source),allow_pickle=False) as archive:
            arrays={key:archive[key].copy() for key in archive.files}
        assert 'metadata_json' in arrays and not any(a.dtype.hasobject for a in arrays.values())
        assert arrays['current_after'].shape[0]==32
        decode_json=json.loads(arrays['metadata_json'].tobytes())
        plain=[];encoded=[];decoded=[];sizes=[]
        for repeat in range(3):
            if time.perf_counter()>deadline:raise TimeoutError('55second audit deadline')
            before=time.perf_counter();raw=npz(arrays);plain.append(time.perf_counter()-before)
            before=time.perf_counter();packed,count=probe.encode(arrays,1536);encoded.append(time.perf_counter()-before)
            before=time.perf_counter();restored=probe.decode(packed);decoded.append(time.perf_counter()-before)
            assert exact(arrays,restored)
            assert json.loads(restored['metadata_json'].tobytes())==decode_json
            sizes.append((len(raw),len(packed),count))
        assert len(set(sizes))==1
        records.append(dict(source=pin,n=arrays['current_after'].shape[1],arrays=fields(arrays),
            metadata_json_included_and_byte_exact=True,metadata_json_dtype=arrays['metadata_json'].dtype.str,
            metadata_json_shape=list(arrays['metadata_json'].shape),plain_bytes=sizes[0][0],dedup_bytes=sizes[0][1],
            fraction=sizes[0][1]/sizes[0][0],unique_blocks=sizes[0][2],plain_seconds=plain,
            encode_seconds=encoded,decode_seconds=decoded,median_plain_seconds=statistics.median(plain),
            median_encode_seconds=statistics.median(encoded),median_decode_seconds=statistics.median(decoded),
            all_fields_shape_dtype_byteorder_and_bytes_exact=True,original_field_order_preserved=list(restored)==list(arrays),
            independent_packet=True,repeats=3))

    # Read-only negative evidence for what the experiment must not promise.
    synthetic={
        'be_float':np.arange(60,dtype='>f8').reshape(2,10,3),
        'le_int':np.arange(18,dtype='<i2').reshape(2,3,3),
        'bool_mask':np.array([True,False,True]),
        'literal':np.array([b'a',b'bb'],dtype='S2'),
        'metadata_json':np.frombuffer(b'{"explicit":"mixedN"}',np.uint8),
    }
    restored=probe.decode(probe.encode(synthetic,1536)[0]);assert exact(synthetic,restored)
    zero={'scalar':np.array(1.25,dtype='>f8')}
    zero_after=probe.decode(probe.encode(zero,1536)[0])['scalar']
    truncations=[];packed=probe.encode(synthetic,1536)[0]
    for length in (0,1,len(packed)//2,len(packed)-1):
        try:probe.decode(packed[:length]);rejected=False
        except Exception:rejected=True
        truncations.append(dict(retained_bytes=length,rejected=rejected))
    assert all(row['rejected'] for row in truncations)
    # A valid ZIP/NPY with modified pool data passes this unauthenticated probe.
    with np.load(io.BytesIO(packed),allow_pickle=False) as archive:
        changed={key:archive[key].copy() for key in archive.files}
    changed['pool'][0]^=1
    tampered=probe.decode(npz(changed))
    tamper_accepted=not exact(synthetic,tampered)
    assert tamper_accepted
    # Object literals are accepted by the encoder and stored using NPY pickle;
    # its decoder rejects them because allow_pickle=False. Future encoder must
    # reject before writing, not rely on a later reader failure.
    obj={'object_literal':np.array([{'forbidden':'pickle'}],dtype=object)}
    object_encoded,_=probe.encode(obj,1536)
    try:probe.decode(object_encoded);object_decoder_rejected=False
    except ValueError:object_decoder_rejected=True
    report=dict(status='positive_fixture_storage_result_not_production_codec',
        probe_source_sha256=sha(Path(probe.__file__).read_bytes()),source_report_sha256=sha(original.read_bytes()),
        audit_source_sha256=sha(Path(__file__).read_bytes()),seconds=time.perf_counter()-start,
        records=records,actual_individual_packets=4,repeats_per_packet=3,metadata_json_included=True,
        synthetic_mixedN_endian_dtype_case_passed=True,
        scalar_shape_defect=dict(input_shape=[],output_shape=list(zero_after.shape),preserved=zero_after.shape==()),
        truncation_tests=truncations,valid_zip_pool_tamper_not_detected=bool(tamper_accepted),
        encoder_accepts_object_pickle=True,decoder_rejects_object_pickle=object_decoder_rejected,
        requires_new_standalone_codec_before_production=True,no_gpu=True,no_search=True,
        no_production_consumer_or_frozen_job_changed=True,
        limitations=['Four B32 historical fixtures only; not measured B64 sustained packet workload.',
          'Literal0d arrays become1d in the original probe; metadata_json in these actual packets is1d uint8.',
          'Probe decoder lacks per-array content hashes, strict block/index schema bounds and explicit no-object encoder policy.',
          'Timing includes in-memory serialization only; no fsync/index publication or search-coverage conclusion.'])
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise ValueError('Fresh audit report required')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k]for k in ['status','seconds','actual_individual_packets','repeats_per_packet','scalar_shape_defect','valid_zip_pool_tamper_not_detected']}))
    print(json.dumps([dict(n=r['n'],source=r['source']['path'],fraction=r['fraction'],plain=r['median_plain_seconds'],encode=r['median_encode_seconds'],decode=r['median_decode_seconds'])for r in records]))
    return report


if __name__=='__main__':run(Path('artifacts/fq-packet-dedup-independent-review-v1/report.json'))
