"""Submit an officially certified CSV with bounded upload and safe diagnostics.

Never print the signed upload URL or credential. A receipt is written only after
Kaggle acknowledges CreateSubmission. Recheck submissions after an ambiguous
connection failure before retrying submission creation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import requests
from kagglesdk.kaggle_client import KaggleClient
from kagglesdk.competitions.types.competition_api_service import (
    ApiStartSubmissionUploadRequest, ApiCreateSubmissionRequest,
)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv',type=Path)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--message',required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    a=ap.parse_args()
    r=json.loads(a.report.read_text())
    digest=hashlib.sha256(a.csv.read_bytes()).hexdigest()
    expected_metric='312458227c78f56bd5e2eec3dc5fbb8787989422bbf72ce66c3c290048e89733'
    if not (r.get('valid') and r.get('invalid_count')==0 and r.get('puzzles')==1000
            and r.get('sha256')==digest and r.get('metric_sha256')==expected_metric):
        raise SystemExit('CSV does not match a valid complete official v17 report.')
    if a.receipt.exists():
        raise SystemExit('Receipt already exists; inspect submission status before another submission.')
    token=os.environ.get('KAGGLE_API_TOKEN')
    if not token:
        token=Path(os.environ.get('KAGGLE_TOKEN_FILE','/tmp/squares-kaggle-auth/token')).read_text().strip()
    with KaggleClient(api_token=token) as client:
        api=client.competitions.competition_api_client
        req=ApiStartSubmissionUploadRequest()
        req.competition_name='squares-in-squares'
        req.file_name=a.csv.name
        req.content_length=a.csv.stat().st_size
        req.last_modified_epoch_seconds=int(a.csv.stat().st_mtime)
        started=api.start_submission_upload(req)
        print('Upload destination:',urlsplit(started.create_url).hostname,flush=True)
        # A regular seekable file allows requests to determine Content-Length.
        # No automatic retry: the caller diagnoses a failure before retrying.
        with a.csv.open('rb') as source:
            response=requests.put(started.create_url,data=source,
                                  headers={'Content-Length':str(req.content_length)},
                                  timeout=(15,90))
        if response.status_code not in (200,201,204):
            raise SystemExit(f'Upload failed: HTTP {response.status_code}; no submission created.')
        print('Upload completed; requesting scoring.',flush=True)
        req2=ApiCreateSubmissionRequest()
        req2.competition_name='squares-in-squares'
        req2.blob_file_tokens=started.token
        req2.submission_description=a.message
        response=api.create_submission(req2)
        receipt={'csv':str(a.csv),'sha256':digest,'official_score':r['score'],
                 'message':a.message,'kaggle_response':response.to_dict()}
        a.receipt.parent.mkdir(parents=True,exist_ok=True)
        a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    try:main()
    except requests.RequestException as e:
        req=getattr(e,'request',None);resp=getattr(e,'response',None)
        host=urlsplit(req.url).hostname if req is not None else 'unknown'
        status=resp.status_code if resp is not None else 'connection failed'
        raise SystemExit(f'{type(e).__name__}: host={host}; status={status}. Check submission history before retrying.')
