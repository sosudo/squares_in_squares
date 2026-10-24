#!/usr/bin/env python3
"""Download public Kaggle notebook output CSVs without credentials.

Only public outputs are accessed. Provenance records URL, timestamp and digest;
signed redirect URLs are deliberately not stored or logged.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(ref, output, filename='submission.csv', kind='notebook', version=None):
    if len(ref.split('/')) != 2 or any(c in ref for c in '?&#'):
        raise ValueError('Expected owner/notebook-slug')
    target = output / (ref.replace('/', '__') + '.csv')
    prefix = 'kernels/output/download/' if kind == 'notebook' else 'datasets/download/'
    url = 'https://www.kaggle.com/api/v1/' + prefix + ref + '/' + filename
    if version is not None:
        if kind != 'dataset':
            raise ValueError('Version pin currently supports datasets only')
        url += '?datasetVersionNumber=' + str(version)
    temporary = target.with_suffix('.part')
    hosts = []

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            hosts.append(urllib.parse.urlsplit(newurl).hostname)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    try:
        opener = urllib.request.build_opener(Redirect)
        with opener.open(url, timeout=90) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        with temporary.open('rb') as stream:
            header = stream.readline().decode('utf8').strip().lstrip('\ufeff').split(',')
            if not {'n', 'square_id', 'x', 'y', 'angle'}.issubset(header):
                raise ValueError('Output is not a packing submission CSV')
        temporary.replace(target)
        with target.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        metadata = {kind: ref, 'url': url, 'filename': filename, 'version': version,
                    'retrieved_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'sha256': digest, 'bytes': target.stat().st_size,
                    'redirect_hosts': hosts}
        target.with_suffix('.source.json').write_text(json.dumps(metadata, indent=2) + '\n')
        return {'notebook': ref, 'ok': True, 'path': str(target), 'bytes': metadata['bytes']}
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        # Do not include signed URLs from exceptions in logs.
        return {'notebook': ref, 'ok': False, 'error_type': type(exc).__name__,
                'http_status': getattr(exc, 'code', None), 'redirect_hosts': hosts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebooks', nargs='+')
    parser.add_argument('--output', type=Path, default=Path('artifacts/public'))
    parser.add_argument('--filename', default='submission.csv')
    parser.add_argument('--kind', choices=['notebook', 'dataset'], default='notebook')
    parser.add_argument('--version', type=int, help='Explicit dataset version; unversioned endpoints may be stale')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        for result in pool.map(lambda ref: fetch(ref, args.output, args.filename, args.kind, args.version), args.notebooks):
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
