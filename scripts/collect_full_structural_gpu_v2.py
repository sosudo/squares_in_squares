#!/usr/bin/env python3
"""Collect bounded named v2 outputs, never the potentially large raw ZIP."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import time
from urllib.parse import urlsplit
import requests
from submission_scheduler import KaggleGateway
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest,ApiDownloadKernelOutputRequest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook',default='sos54352/squares-full-packing-structural-repair-v2')
    parser.add_argument('--version',type=int,default=1)
    parser.add_argument('--source-sha256',default='7779faa0301a20fbd0164a45d8fd4d1bac7d3fc6fa6fec0cfee626c59225b7e9')
    parser.add_argument('--file',action='append',dest='files')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    names=args.files or ['full_structural_v2_summary.json','full_structural_v2_records.json',
        'full_structural_v2_candidates.json','full_structural_v2_raw_index.json','full_structural_v2_pairing.json',
        'job_manifest.json','prepared_config.json','artifacts/full_structural_v2_certified.npz']
    if not args.files:
        names += [f'artifacts/full_structural_v2_device{d}/{name}'for d in(0,1)for name in
            ('status.json','preflight.json','gradient_controls.json','gradient_patch.json','throughput_control.json',
             'pending.npz','certification-summary.json','preflight_packings.npz','preflight_packing_records.json')]
    args.out.mkdir(parents=True,exist_ok=False);started=time.monotonic();files={}
    receipt=dict(notebook=args.notebook,version=args.version,source_sha256=args.source_sha256,status='started',files=files)
    try:
        with KaggleGateway()as gateway:
            owner,slug=args.notebook.split('/');api=gateway.client.kernels.kernels_api_client
            query=ApiGetKernelRequest();query.user_name=owner;query.kernel_slug=slug;query.version_label='v'+str(args.version)
            kernel=api.get_kernel(query)
            assert kernel.metadata.is_private and kernel.metadata.enable_gpu
            assert hashlib.sha256(kernel.blob.source.encode()).hexdigest()==args.source_sha256
            receipt['private_source_verified']=True
            for name in names:
                relative=PurePosixPath(name)
                assert not relative.is_absolute()and'..'not in relative.parts and'\\'not in name
                request=ApiDownloadKernelOutputRequest();request.owner_slug=owner;request.kernel_slug=slug
                request.version_number=args.version;request.file_path=name
                redirect=api.download_kernel_output(request);url=urlsplit(redirect.url)
                assert url.scheme=='https'and url.hostname
                getter=gateway.client.http_client()._session.get if url.hostname in('www.kaggle.com','api.kaggle.com')else requests.get
                target=args.out/'outputs'/name;target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_suffix(target.suffix+'.incoming')
                digest=hashlib.sha256();size=0
                with getter(redirect.url,stream=True,timeout=(15,30))as response:
                    response.raise_for_status()
                    with temporary.open('wb')as stream:
                        for chunk in response.iter_content(1024*1024):
                            size+=len(chunk)
                            if time.monotonic()-started>240 or size>256*1024**2:raise TimeoutError('Named output collection bound')
                            stream.write(chunk);digest.update(chunk)
                temporary.replace(target);files[name]=dict(sha256=digest.hexdigest(),bytes=size,redirect_host=url.hostname)
                (args.out/'download-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
                print(json.dumps(dict(downloaded=name,bytes=size)),flush=True)
        receipt['status']='complete'
    except Exception as exc:
        receipt.update(status='failed',error_type=type(exc).__name__,http_status=getattr(getattr(exc,'response',None),'status_code',None))
        raise RuntimeError('Named collection failed; see sanitized receipt')from None
    finally:
        receipt['elapsed_seconds']=time.monotonic()-started
        (args.out/'download-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
