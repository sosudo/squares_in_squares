"""Finite four-original-packet benchmark of the standalone FUTURE codec."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import statistics
import time
import numpy as np
import fq_packet_codec as codec


def sha(data):return hashlib.sha256(data).hexdigest()


def run(out):
    start=time.perf_counter();deadline=start+55.;pins_path=Path('artifacts/fq-packet-dedup-probe-v1/report.json')
    pins=[pin for row in json.loads(pins_path.read_bytes())['records']for pin in row['source_packets']]
    records=[]
    for pin in pins:
        raw=Path(pin['path']).read_bytes()
        assert sha(raw)==pin['sha256']
        with np.load(io.BytesIO(raw),allow_pickle=False)as archive:
            arrays={name:archive[name].copy()for name in archive.files}
        assert 'metadata_json'in arrays and all(not a.dtype.hasobject for a in arrays.values())
        times=[];plain_times=[];decode_times=[];hashes=[]
        for repeat in range(3):
            assert time.perf_counter()<deadline,'55second bounded benchmark'
            before=time.perf_counter();stream=io.BytesIO();np.savez(stream,**arrays);plain=stream.getvalue()
            plain_times.append(time.perf_counter()-before)
            before=time.perf_counter();packed=codec.encode(arrays);times.append(time.perf_counter()-before)
            before=time.perf_counter();restored=codec.decode(packed,expected_sha256=sha(packed));decode_times.append(time.perf_counter()-before)
            assert list(restored)==list(arrays)
            for name,a in arrays.items():
                b=restored[name];assert a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()
            hashes.append(sha(packed))
        assert len(set(hashes))==1
        records.append(dict(source=pin,n=arrays['current_after'].shape[1],batch_size=32,repeats=3,
            fields={k:dict(dtype=a.dtype.str,shape=list(a.shape),sha256=sha(a.tobytes()))for k,a in arrays.items()},
            metadata_json_included=True,all_fields_exact=True,key_order_exact=True,deterministic_archive_sha256=hashes[0],
            bytes=len(packed),plain_bytes=len(plain),fraction=len(packed)/len(plain),
            encode_seconds=times,decode_seconds=decode_times,plain_seconds=plain_times,
            median_encode_seconds=statistics.median(times),median_decode_seconds=statistics.median(decode_times),
            median_plain_seconds=statistics.median(plain_times)))
    report=dict(passed=True,codec_source_sha256=sha(Path(codec.__file__).read_bytes()),
        benchmark_source_sha256=sha(Path(__file__).read_bytes()),pins_source_sha256=sha(pins_path.read_bytes()),
        seconds=time.perf_counter()-start,actual_individual_packets=4,repeats_each=3,records=records,
        codec_format=codec.FORMAT,codec_version=codec.VERSION,block_bytes=codec.BLOCK_BYTES,
        no_gpu=True,no_optimization=True,no_runtime_consumer_modified=True,
        scope='Four actual independent B32 historical803/861 packets including metadata_json. In-memory serialization only; no fsync, currentB64 production workload, throughput/search or admission claim.')
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise ValueError('Fresh benchmark report required')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=True,seconds=report['seconds'],results=[{k:r[k]for k in ['n','fraction','median_encode_seconds','median_decode_seconds','median_plain_seconds']}for r in records])))
    return report


if __name__=='__main__':run(Path('artifacts/fq-packet-codec-v2/benchmark.json'))
