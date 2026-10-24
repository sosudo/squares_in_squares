"""Read-only, self-contained lossless packet storage benchmark; no GPU/search.

This experiment is not a production codec. Every packet is independently
decodable, and all original dtype/shape/bytes are checked after reconstruction.
"""
import hashlib
import io
import json
from pathlib import Path
import statistics
import time

import numpy as np


def encode(arrays, block_bytes):
    pool, lookup, fields = [], {}, {}
    saved = {}
    for key, value in arrays.items():
        a = np.ascontiguousarray(value)
        if a.ndim != 3:
            saved['literal_' + key] = a
            fields[key] = dict(kind='literal')
            continue
        rows = a.reshape(a.shape[0], -1).view(np.uint8)
        width = rows.shape[1]
        size = width if block_bytes is None else block_bytes
        indices = []
        for row in rows:
            raw = row.tobytes()
            for start in range(0, width, size):
                part = raw[start:start + size]
                index = lookup.get(part)
                if index is None:
                    index = len(pool)
                    lookup[part] = index
                    pool.append(part)
                indices.append(index)
        saved['index_' + key] = np.asarray(indices, dtype=np.uint32)
        fields[key] = dict(kind='blocks', shape=list(a.shape), dtype=a.dtype.str,
                           row_bytes=width, block_bytes=size)
    saved['pool'] = np.frombuffer(b''.join(pool), dtype=np.uint8)
    saved['ends'] = np.cumsum([len(x) for x in pool], dtype=np.uint64)
    saved['metadata'] = np.frombuffer(json.dumps(fields, sort_keys=True).encode(), dtype=np.uint8)
    stream = io.BytesIO()
    np.savez(stream, **saved)
    return stream.getvalue(), len(pool)


def decode(raw):
    result = {}
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        fields = json.loads(archive['metadata'].tobytes())
        data = archive['pool'].tobytes()
        ends = archive['ends'].tolist()
        pool = [data[a:b] for a, b in zip([0] + ends[:-1], ends)]
        for key, info in fields.items():
            if info['kind'] == 'literal':
                result[key] = archive['literal_' + key].copy()
            else:
                joined = b''.join(pool[int(i)] for i in archive['index_' + key])
                result[key] = np.frombuffer(joined, dtype=info['dtype']).reshape(info['shape']).copy()
    return result


def run(out):
    started = time.perf_counter()
    source = Path('artifacts/fq-sustained-lossless-storage-probe-v1/report.json')
    original = json.loads(source.read_text())
    results = []
    for item in original['records']:
        inputs = []
        for pin in item['source_packets']:
            path = Path(pin['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
            with np.load(path, allow_pickle=False) as archive:
                inputs.append({k: archive[k].copy() for k in archive.files})
        assert inputs[0].keys() == inputs[1].keys()
        arrays = {k: np.concatenate([x[k] for x in inputs], axis=0)
                  if inputs[0][k].ndim and inputs[0][k].shape[0] == 32
                  else inputs[0][k] for k in inputs[0] if k in item['arrays']}
        assert arrays.keys() == item['arrays'].keys()
        for k, a in arrays.items():
            assert hashlib.sha256(a.tobytes()).hexdigest() == item['arrays'][k]['sha256']
        modes = []
        for block in (None, 1536, 384):
            times, decode_times = [], []
            for repeat in range(3):
                begin = time.perf_counter()
                packed, unique = encode(arrays, block)
                times.append(time.perf_counter() - begin)
                begin = time.perf_counter()
                restored = decode(packed)
                decode_times.append(time.perf_counter() - begin)
                assert restored.keys() == arrays.keys()
                for k, a in arrays.items():
                    b = restored[k]
                    assert a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()
            modes.append(dict(block_bytes=block, unique_blocks=unique, bytes=len(packed),
                              fraction=len(packed)/item['results'][0]['bytes'],
                              encode_seconds=times, decode_seconds=decode_times,
                              median_encode_seconds=statistics.median(times),
                              all_arrays_bit_exact=True, independently_decodable_packet=True))
        results.append(dict(n=item['n'], source_packets=item['source_packets'],
                            arrays=item['arrays'], original_stored_bytes=item['results'][0]['bytes'], modes=modes))
    report = dict(scope=original['records'][0]['scope'],
                  source_probe_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  seconds=time.perf_counter()-started, records=results,
                  no_gpu=True, no_search=True, no_runtime_changes=True,
                  metadata_scope='Same numerical arrays as the earlier concatenation probe; original metadata_json remains in both hash-pinned source packets.',
                  limitation='Two concatenated real B32 fixtures; not measured actual B64 production overhead or search coverage.')
    out.parent.mkdir(parents=True, exist_ok=True)
    assert not out.exists()
    out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(seconds=report['seconds'], results=[dict(n=r['n'], modes=r['modes']) for r in results])))


if __name__ == '__main__':
    run(Path('artifacts/fq-packet-dedup-probe-v1/report.json'))
