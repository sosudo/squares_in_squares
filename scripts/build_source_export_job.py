"""Build a compact, source-backed private Kaggle portfolio export.

Pinned public CSVs supply unchanged puzzles. Pinned rational certificates supply
exact high-precision catalogue puzzles; only remaining local constructions are
embedded. All input and output hashes are checked. No credentials are embedded.

Reusable API: make_loader(csv_path, report_path, records_path=None) returns
(Python source defining reconstruct_portfolio, manifest, local cache sources).
The same loader can initialize a bounded GPU composition job under Kaggle's
one-megabyte notebook source limit.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import csv
import hashlib
import io
import json
import lzma
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SHA256 = '312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
DEFAULT_EXPORT_REF = 'sos54352/squares-certified-portfolio-source-export'
DEFAULT_EXPORT_TITLE = 'Squares Certified Portfolio Source Export'
SOURCES = [
    ('kmmmvs22', 'artifacts/public/kmmmvs__squares-in-squares-best-packings.csv',
     'https://www.kaggle.com/api/v1/datasets/download/kmmmvs/squares-in-squares-best-packings/submission.csv?datasetVersionNumber=22',
     'aa8d390849d0ff5a8acacc36ad62f232ab76a11acdb8402a79e29167f6d1d920', 'Sung Heo / kmmmvs and credited source authors, dataset v22'),
    ('kmmmvs24', 'artifacts/public-v24/kmmmvs__squares-in-squares-best-packings.csv',
     'https://www.kaggle.com/api/v1/datasets/download/kmmmvs/squares-in-squares-best-packings/submission.csv?datasetVersionNumber=24',
     '79629f489cf84987f55165618f800c6e37c1dbdbd9d0ec8df30be21fee2436dc', 'Sung Heo / kmmmvs and credited source authors, dataset v24'),
    ('kmmmvs26', 'artifacts/public-v26/kmmmvs__squares-in-squares-best-packings.csv',
     'https://www.kaggle.com/api/v1/datasets/download/kmmmvs/squares-in-squares-best-packings/submission.csv?datasetVersionNumber=26',
     'cab501fe499261db1c9a5b2d665ca7964e509484442a920376282281444cdd4c', 'Sung Heo / kmmmvs and credited source authors, dataset v26'),
    ('cdeotte2', 'artifacts/public/cdeotte__squares-in-squares-22-315-data.csv',
     'https://www.kaggle.com/api/v1/datasets/download/cdeotte/squares-in-squares-22-315-data/submission.csv?datasetVersionNumber=2',
     '7a9fb4638f6de775d01a8300cbe3616b5c21052fdb5229a0d6bd4c9f67989725', 'Chris Deotte and credited source authors, dataset v2, CC0'),
    ('dariush11constructions', 'artifacts/additional-dataset-v11/constructions_v1/dariushafshar__squares-in-squares-certified-packings.csv',
     'https://www.kaggle.com/api/v1/datasets/download/dariushafshar/squares-in-squares-certified-packings/constructions_v1.csv?datasetVersionNumber=11',
     'a542b6a8c97922b0e923d59d96870fa10123fae47c9279a6eec096a7c5971786', 'Dariush Afshar and credited source authors, dataset v11 constructions_v1'),
    ('dariush11packings', 'artifacts/additional-dataset-v11/packings_v1/dariushafshar__squares-in-squares-certified-packings.csv',
     'https://www.kaggle.com/api/v1/datasets/download/dariushafshar/squares-in-squares-certified-packings/packings_v1.csv?datasetVersionNumber=11',
     '8f4579f41ee67a2fbd051bf91f2155c037aea7f4447e7363a1ac1b3d52132b61', 'Dariush Afshar and credited source authors, dataset v11 packings_v1'),
]


RUNTIME = r'''
import base64, concurrent.futures, csv, functools, gzip, hashlib, io, json, lzma, sys, time
from fractions import Fraction
from pathlib import Path
import urllib.error, urllib.request

def _source_sha(data):
    return hashlib.sha256(data).hexdigest()

def _source_rows(data):
    groups={}
    for row in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))):
        n,sid=int(row['n']),int(row['square_id'])
        group=groups.setdefault(n,{})
        assert sid not in group, 'Duplicate source square id'
        group[sid]=[row['x'],row['y'],row['angle']]
    return {n:[g[i] for i in range(n)] for n,g in groups.items()
            if len(g)==n and set(g)==set(range(n))}

def _source_download(source, cache):
    path=cache/(source['sha256']+'.bin')
    if path.is_file():
        data=path.read_bytes()
    else:
        try:
            with urllib.request.urlopen(source['url'],timeout=120) as response:
                data=response.read()
        except (urllib.error.URLError,urllib.error.HTTPError) as exc:
            # Signed redirect URLs are deliberately absent from diagnostics.
            raise RuntimeError('Public source download failed: '+source['key']+
                               ' ('+type(exc).__name__+')') from None
        assert _source_sha(data)==source['sha256'], 'Public source SHA256 mismatch: '+source['key']
        temporary=path.with_suffix('.part');temporary.write_bytes(data);temporary.replace(path)
    assert _source_sha(data)==source['sha256'], 'Cached source SHA256 mismatch: '+source['key']
    return source['key'],data

def _source_certificate(data, compressed=False):
    if compressed:data=gzip.decompress(data)
    lines=[line.split() for line in data.decode().splitlines() if line.strip() and not line.startswith('#')]
    n,side=int(lines[0][0]),Fraction(lines[0][1])
    squares=[tuple(map(Fraction,row[:3])) for row in lines[1:n+1]]
    assert len(squares)==n
    return side,squares

def _source_expand(side,squares,tiles,layers):
    rows=[(x+ix*side,y+iy*side,t) for iy in range(tiles) for ix in range(tiles)
          for x,y,t in squares]
    side*=tiles
    half=Fraction(1,2)
    for _ in range(layers):
        k=side.numerator//side.denominator
        rows.extend((side+half,i+half,Fraction(0)) for i in range(k+1))
        rows.extend((i+half,side+half,Fraction(0)) for i in range(k))
        side+=1
    return rows

def reconstruct_portfolio(destination, cache_dir=None):
    """Recreate the exact frozen CSV; fail closed on any input/output mismatch."""
    import mpmath as mp
    assert mp.__version__==PORTFOLIO_MANIFEST['mpmath_version'], 'Unexpected mpmath version'
    if hasattr(sys,'set_int_max_str_digits'):sys.set_int_max_str_digits(0)
    destination=Path(destination)
    if destination.is_file():
        assert _source_sha(destination.read_bytes())==PORTFOLIO_MANIFEST['csv_sha256']
        return destination
    started=time.monotonic()
    cache=Path(cache_dir) if cache_dir is not None else destination.parent/'.portfolio-source-cache'
    cache.mkdir(parents=True,exist_ok=True)
    sources=PORTFOLIO_MANIFEST['sources']+PORTFOLIO_MANIFEST['certificates']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fetched=dict(pool.map(lambda s:_source_download(s,cache),sources))
    groups={}
    for source in PORTFOLIO_MANIFEST['sources']:
        rows=_source_rows(fetched[source['key']])
        for n in source['puzzles']:
            assert n in rows,'Pinned public source is missing puzzle'
            groups[n]=rows[n]
    certificates={source['key']:_source_certificate(fetched[source['key']],source.get('gzip',False))
                  for source in PORTFOLIO_MANIFEST['certificates']}
    with mp.workdps(100):
        factor=1+mp.mpf('1e-40')
        def number(value):return mp.mpf(value.numerator)/value.denominator
        @functools.lru_cache(maxsize=None)
        def angle(t):return 2*mp.atan(number(t)) if t else mp.mpf(0)
        def render(v):return mp.nstr(v,75,strip_zeros=False)
        for recipe in PORTFOLIO_MANIFEST['certificate_cases']:
            side,squares=certificates[recipe['source']]
            expanded=_source_expand(side,squares,recipe['tiles'],recipe['layers'])
            n=recipe['n'];assert len(expanded)>=n
            groups[n]=[[render(number(x)*factor),render(number(y)*factor),render(angle(t))]
                       for x,y,t in expanded[:n]]
    patch_raw=lzma.decompress(base64.b64decode(PORTFOLIO_PATCH))
    assert _source_sha(patch_raw)==PORTFOLIO_MANIFEST['patch_sha256']
    for n,rows in json.loads(patch_raw).items():groups[int(n)]=rows
    assert set(groups)==set(range(1,1001))
    text=io.StringIO(newline='')
    writer=csv.writer(text,lineterminator='\r\n')
    writer.writerow(['id','n','square_id','x','y','angle'])
    rid=0
    for n in range(1,1001):
        rows=groups[n];assert len(rows)==n
        digest=_source_sha(json.dumps(rows,separators=(',',':')).encode())
        assert digest==PORTFOLIO_MANIFEST['puzzle_sha256'][str(n)], 'Puzzle reconstruction mismatch: '+str(n)
        for sid,(x,y,a) in enumerate(rows):
            assert all(isinstance(v,str) for v in (x,y,a))
            writer.writerow([rid,n,sid,x,y,a]);rid+=1
    data=text.getvalue().encode()
    assert rid==PORTFOLIO_MANIFEST['rows']==500500
    assert len(data)==PORTFOLIO_MANIFEST['csv_bytes']
    assert _source_sha(data)==PORTFOLIO_MANIFEST['csv_sha256'], 'Frozen CSV SHA256 mismatch'
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.csv.incoming');temporary.write_bytes(data);temporary.replace(destination)
    print(json.dumps({'stage':'exact_portfolio_reconstructed','sha256':_source_sha(data),
                      'score':PORTFOLIO_MANIFEST['official_score'],'rows':rid,
                      'seconds':time.monotonic()-started}),flush=True)
    return destination
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_groups(path):
    raw = Path(path).read_bytes()
    groups = {}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        n, sid = int(row['n']), int(row['square_id'])
        group = groups.setdefault(n, {})
        if sid in group:
            raise ValueError(f'Duplicate source square id n={n}, sid={sid}')
        group[sid] = [row['x'], row['y'], row['angle']]
    return raw, {n: [g[i] for i in range(n)] for n, g in groups.items()
                 if len(g) == n and set(g) == set(range(n))}


def make_loader(csv_path, report_path, records_path=None, export_ref=DEFAULT_EXPORT_REF):
    """Return (loader source, public manifest, hash-keyed local cache paths)."""
    csv_path, report_path = Path(csv_path), Path(report_path)
    raw, target = read_groups(csv_path)
    report_raw = report_path.read_bytes(); report = json.loads(report_raw)
    assert report['valid'] and report['invalid_count'] == 0 and report['puzzles'] == 1000
    assert report['metric_sha256'] == OFFICIAL_SHA256
    assert report['sha256'] == sha(raw)
    assert set(target) == set(range(1, 1001))
    unmatched = set(target); public_sources = []; cache_sources = {}
    for key, relative, url, expected, credit in SOURCES:
        path = ROOT / relative
        if not path.is_file():
            continue
        data, candidates = read_groups(path)
        assert sha(data) == expected, f'Local public-source hash mismatch: {key}'
        matches = [n for n in sorted(unmatched) if candidates.get(n) == target[n]]
        if not matches:
            continue
        public_sources.append(dict(key=key, url=url, sha256=expected, puzzles=matches, credit=credit))
        cache_sources[expected] = path
        unmatched.difference_update(matches)
    if records_path is None:
        catalogues = [ROOT / 'artifacts/candidates/records.json']
        catalogues += sorted((ROOT / 'artifacts/candidates').glob('records-fresh-*.json'))
    elif isinstance(records_path, (list, tuple)):
        catalogues = list(map(Path, records_path))
    else:
        catalogues = [Path(records_path)]
    records = {}
    for catalogue in catalogues:
        if catalogue.is_file():
            for key, record in json.loads(catalogue.read_text()).items():
                records.setdefault(key, []).append(record)
    certificate_cases = []; certificates = {}; certificate_n = 0
    for n in sorted(unmatched):
        record = next((r for r in records.get(str(n), []) if r.get('squares') == target[n]), None)
        if record is None:
            continue
        origin = record['provenance']
        finite = origin.get('finite_record') or {}
        if (origin.get('kind') or finite.get('kind')) != 'certificate':
            continue
        relative, expected = origin['certificate'], origin['certificate_sha256']
        locations = [ROOT / 'artifacts/public-freshness' / ('couzo-' + origin['commit'][:12]) / relative,
                     Path('/tmp/squares-research/couzo') / relative]
        local = next((p for p in locations if p.is_file() and sha(p.read_bytes()) == expected), None)
        assert local is not None, f'Pinned certificate bytes unavailable for n={n}'
        key = 'couzo_' + expected[:20]
        certificates[key] = dict(key=key,
            url=f"https://raw.githubusercontent.com/franciscouzo/square-packing/{origin['commit']}/{relative}",
            sha256=expected, gzip=relative.endswith('.gz'),
            credit=origin.get('credit', 'Francisco Couzo and credited mathematical witness authors'))
        cache_sources[expected] = local
        recipe = origin.get('construction') or finite.get('construction') or {}
        certificate_cases.append(dict(n=n, source=key, tiles=recipe.get('tiles_per_side', 1),
                                      layers=recipe.get('layers', 0)))
        certificate_n += 1
    unmatched.difference_update(r['n'] for r in certificate_cases)
    patch = {str(n): target[n] for n in sorted(unmatched)}
    patch_raw = json.dumps(patch, separators=(',', ':')).encode()
    compressed = lzma.compress(patch_raw, preset=6)
    payload = base64.b64encode(compressed).decode()
    manifest = dict(format_version=1, csv_sha256=sha(raw), csv_bytes=len(raw), rows=report['rows'],
        official_score=report['score'], metric_version=17, metric_sha256=OFFICIAL_SHA256,
        source_report_sha256=sha(report_raw), mpmath_version=report['mpmath_version'],
        sources=public_sources, certificates=list(certificates.values()), certificate_cases=certificate_cases,
        patch_sha256=sha(patch_raw), patch_puzzles=sorted(unmatched), patch_bytes=len(patch_raw),
        patch_compressed_bytes=len(compressed), patch_base64_bytes=len(payload),
        public_csv_puzzles=sum(len(s['puzzles']) for s in public_sources), certificate_puzzles=certificate_n,
        puzzle_sha256={str(n): sha(json.dumps(rows, separators=(',', ':')).encode())
                       for n, rows in target.items()},
        source_export_notebook_ref=export_ref,
        source_notices='Inherited source attribution/licenses retained in repository vendor/notices/; no mathematical discovery is claimed by the exporter.')
    script = ('# Exact source-backed public-data portfolio loader. No credentials.\n'
              'PORTFOLIO_MANIFEST = ' + repr(manifest) + '\n'
              'PORTFOLIO_PATCH = ' + repr(payload) + '\n' + RUNTIME)
    compile(script, 'portfolio_loader.py', 'exec')
    return script, manifest, cache_sources


def make_safe_loader(raw_csv, raw_report, safe_csv, safe_report, records_path=None,
                     helper_path=None, factor='1.00000000001', export_ref=DEFAULT_EXPORT_REF):
    """Reconstruct the raw portfolio, then run the exact shared safety helper.

    Public-source matching always uses raw coordinates. The transformed long
    decimals are generated by the reviewed helper instead of embedded as data.
    Both the raw and final CSV hashes must agree with their official reports.
    """
    loader, original, cache_sources = make_loader(raw_csv, raw_report, records_path, export_ref=export_ref)
    safe_csv, safe_report = Path(safe_csv), Path(safe_report)
    raw = safe_csv.read_bytes(); report_raw = safe_report.read_bytes()
    report = json.loads(report_raw)
    assert report['valid'] and report['invalid_count'] == 0 and report['puzzles'] == 1000
    assert report['sha256'] == sha(raw)
    assert report['metric_sha256'] == OFFICIAL_SHA256
    helper_path = Path(helper_path or ROOT / 'scripts/make_transport_safe.py')
    helper = helper_path.read_text()
    manifest = {**original, 'csv_sha256': sha(raw), 'csv_bytes': len(raw),
        'official_score': report['score'], 'source_report_sha256': sha(report_raw),
        'raw_csv_sha256': original['csv_sha256'], 'raw_csv_bytes': original['csv_bytes'],
        'raw_official_score': original['official_score'],
        'transport_transform': {'factor': factor, 'helper_sha256': sha(helper.encode()),
            'helper_source': 'scripts/make_transport_safe.py',
            'purpose': 'Centre-only Decimal100 dilation of long-decimal puzzles; angles unchanged.'}}
    # Raw puzzle hashes describe the source reconstruction, not the transformed
    # target; label that distinction in the final manifest.
    manifest['raw_puzzle_sha256'] = manifest.pop('puzzle_sha256')
    wrapper = '''
_reconstruct_raw_portfolio = reconstruct_portfolio
SAFE_PORTFOLIO_MANIFEST = SAFE_MANIFEST_LITERAL
_TRANSPORT_HELPER = HELPER_LITERAL
assert _source_sha(_TRANSPORT_HELPER.encode())==SAFE_PORTFOLIO_MANIFEST['transport_transform']['helper_sha256']
_transport_namespace={'__name__':'portfolio_transport_helper','__file__':'make_transport_safe.py'}
exec(compile(_TRANSPORT_HELPER,'make_transport_safe.py','exec'),_transport_namespace)

def reconstruct_portfolio(destination,cache_dir=None):
    destination=Path(destination)
    if destination.is_file():
        assert _source_sha(destination.read_bytes())==SAFE_PORTFOLIO_MANIFEST['csv_sha256']
        return destination
    cache=Path(cache_dir) if cache_dir is not None else Path('/tmp/squares-portfolio-source-cache')
    cache.mkdir(parents=True,exist_ok=True)
    raw=cache/('raw-'+PORTFOLIO_MANIFEST['csv_sha256']+'.csv')
    _reconstruct_raw_portfolio(raw,cache)
    transformed=_transport_namespace['make_transport_safe'](raw,destination,
        SAFE_PORTFOLIO_MANIFEST['transport_transform']['factor'])
    assert transformed['source_sha256']==SAFE_PORTFOLIO_MANIFEST['raw_csv_sha256']
    assert transformed['sha256']==SAFE_PORTFOLIO_MANIFEST['csv_sha256']
    assert destination.stat().st_size==SAFE_PORTFOLIO_MANIFEST['csv_bytes']
    (destination.parent/'transport_transform.json').write_text(json.dumps(transformed,indent=2)+'\\n')
    print(json.dumps({'stage':'transport_safe_portfolio_reconstructed','sha256':transformed['sha256'],
        'score':SAFE_PORTFOLIO_MANIFEST['official_score'],'rows':transformed['rows'],
        'selected_cases':transformed['selected_count']}),flush=True)
    return destination
'''.replace('SAFE_MANIFEST_LITERAL', repr(manifest)).replace('HELPER_LITERAL', repr(helper))
    source = loader + wrapper
    compile(source, 'safe_portfolio_loader.py', 'exec')
    return source, manifest, cache_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path, nargs='?', default=ROOT / 'artifacts/merged-v7.csv')
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/merged-v7-official.json')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/source-export')
    parser.add_argument('--slug', default=DEFAULT_EXPORT_REF)
    parser.add_argument('--title', default=DEFAULT_EXPORT_TITLE)
    parser.add_argument('--safe-csv', type=Path,
                        help='Transport-safe target; positional CSV remains the raw source portfolio')
    parser.add_argument('--safe-report', type=Path,
                        help='Official report for the exact transport-safe target')
    parser.add_argument('--transport-helper', type=Path, default=ROOT / 'scripts/make_transport_safe.py')
    parser.add_argument('--factor', default='1.00000000001')
    parser.add_argument('--skip-local-verification', action='store_true')
    args = parser.parse_args()
    if bool(args.safe_csv) != bool(args.safe_report):
        parser.error('--safe-csv and --safe-report must be supplied together')
    if args.safe_csv:
        loader, manifest, cache_sources = make_safe_loader(args.csv, args.report,
            args.safe_csv, args.safe_report, helper_path=args.transport_helper, factor=args.factor,
            export_ref=args.slug)
    else:
        loader, manifest, cache_sources = make_loader(args.csv, args.report, export_ref=args.slug)
    loader += ('\nEXPORT_MANIFEST = SAFE_PORTFOLIO_MANIFEST\n' if args.safe_csv
               else '\nEXPORT_MANIFEST = PORTFOLIO_MANIFEST\n')
    script = loader + '''
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache-dir')
    parser.add_argument('--destination',default='/kaggle/working/submission.csv')
    args=parser.parse_args()
    output=reconstruct_portfolio(Path(args.destination),args.cache_dir)
    (output.parent/'export_manifest.json').write_text(json.dumps(EXPORT_MANIFEST,indent=2)+'\\n')
'''
    assert len(script.encode()) < 1_000_000, f'Source exceeds Kaggle limit: {len(script.encode())}'
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'export.py').write_text(script)
    (args.out / 'portfolio_loader.py').write_text(loader)
    metadata = dict(id=args.slug, title=args.title, code_file='export.py', language='python',
        kernel_type='script', is_private=True, enable_gpu=False, enable_tpu=False, enable_internet=True,
        dataset_sources=[], kernel_sources=[], competition_sources=['squares-in-squares'])
    (args.out / 'kernel-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (args.out / 'export_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verified = False
    if not args.skip_local_verification:
        with tempfile.TemporaryDirectory(prefix='portfolio-reconstruct-', dir='/tmp') as directory:
            directory = Path(directory); cache = directory / 'cache'; cache.mkdir()
            for digest, source in cache_sources.items():
                (cache / (digest + '.bin')).symlink_to(source.resolve())
            output = directory / 'submission.csv'
            subprocess.run([sys.executable, str((args.out / 'export.py').resolve()),
                '--cache-dir', str(cache), '--destination', str(output)], check=True)
            expected = args.safe_csv or args.csv
            assert output.read_bytes() == expected.read_bytes(), 'Reconstruction differs from frozen target'
            verified = True
    result = dict(output=str(args.out), code_bytes=len(script.encode()), exact_local_reconstruction=verified,
        csv_sha256=manifest['csv_sha256'], official_score=manifest['official_score'],
        public_csv_puzzles=manifest['public_csv_puzzles'], certificate_puzzles=manifest['certificate_puzzles'],
        embedded_puzzles=len(manifest['patch_puzzles']), public_certificates=len(manifest['certificates']),
        embedded_compressed_bytes=manifest['patch_compressed_bytes'])
    (args.out / 'build_report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
