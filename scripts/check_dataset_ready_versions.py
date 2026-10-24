#!/usr/bin/env python3
"""Inspect explicit Ready dataset versions; convenience current fields may lag.

Accept a saved public Kaggle dataset-view JSON response, or fetch that public
metadata when --metadata is omitted. This tool never downloads dataset content.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.request


def positive_version(value):
    if isinstance(value,bool):return None
    try:
        result=int(value)
    except (ValueError,TypeError):return None
    return result if result>0 and str(result)==str(value)else None


def ready_versions(metadata,pinned):
    current=positive_version(metadata.get('currentVersionNumber'))
    if current is None:current=positive_version(metadata.get('currentVersionNumberNullable'))
    versions=metadata.get('versions')
    explicit=[]
    if isinstance(versions,list):
        for record in versions:
            status=record.get('status')or record.get('statusNullable')
            number=positive_version(record.get('versionNumber'))
            if number is not None and isinstance(status,str)and status.casefold()=='ready':
                explicit.append({'version':number,'created_at':record.get('creationDate'),
                                 'status':status,'notes':record.get('versionNotes')or record.get('versionNotesNullable')})
    explicit.sort(key=lambda value:value['version'],reverse=True)
    latest=explicit[0]['version']if explicit else None
    complete=latest is not None and(current is None or current<=latest)
    newer=[record for record in explicit if record['version']>pinned]
    status=('newer_ready_version_available'if newer else
            'no_new_ready_version'if complete else'metadata_incomplete')
    return {'pinned_version':pinned,'current_version_convenience_field':current,
            'latest_ready_version':latest,'ready_versions':explicit,'newer_ready_versions':newer,
            'current_field_lags_ready_versions':current is not None and latest is not None and current<latest,
            'discovery_complete':complete,'status':status,
            'selection_rule':'Maximum versionNumber whose explicit status is Ready; never currentVersionNumber alone.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ref',help='Public owner/dataset-slug')
    parser.add_argument('--pinned',type=int,required=True)
    parser.add_argument('--metadata',type=Path,help='Use a saved JSON response without any network call')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.pinned<1 or len(args.ref.split('/'))!=2 or any(x in args.ref for x in '?&#'):
        parser.error('Expected owner/slug and a positive pinned version')
    if args.report.exists():parser.error('Preserve the previous report; select a new output path')
    url='https://www.kaggle.com/api/v1/datasets/view/'+args.ref
    if args.metadata:data=args.metadata.read_bytes()
    else:
        with urllib.request.urlopen(url,timeout=35)as response:data=response.read()
    result=ready_versions(json.loads(data),args.pinned)
    result.update(ref=args.ref,source=url,metadata_source=str(args.metadata)if args.metadata else'public_network',
                  metadata_sha256=hashlib.sha256(data).hexdigest(),
                  checked_at_utc=datetime.now(timezone.utc).isoformat())
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key]for key in ('ref','pinned_version','current_version_convenience_field',
                     'latest_ready_version','current_field_lags_ready_versions','status')},indent=2))


if __name__=='__main__':main()
