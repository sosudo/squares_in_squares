#!/usr/bin/env python3
"""Fetch the exact private structural pilot once as a verified output ZIP."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import time
from urllib.parse import urlsplit
import zipfile
import requests
from submission_scheduler import KaggleGateway
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest,ApiDownloadKernelOutputRequest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook',default='sos54352/squares-full-packing-structural-repair-pilot')
    parser.add_argument('--version',type=int,default=1)
    parser.add_argument('--source-sha256',default='b79e6d174215379ad8033e8ae2d4b986bcca34f5355bdcc1564c82f6118683bf')
    parser.add_argument('--essential',action='store_true',help='Fetch only final aggregates and control proofs')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);started=time.monotonic();receipt={}
    temporary=args.out/'bundle.zip.incoming'
    try:
        owner,slug=args.notebook.split('/')
        with KaggleGateway()as gateway:
            api=gateway.client.kernels.kernels_api_client
            query=ApiGetKernelRequest();query.user_name=owner;query.kernel_slug=slug;query.version_label='v'+str(args.version)
            kernel=api.get_kernel(query)
            assert kernel.metadata.is_private and kernel.metadata.enable_gpu
            assert hashlib.sha256(kernel.blob.source.encode()).hexdigest()==args.source_sha256
            if args.essential:
                names=['full_structural_summary.json','full_structural_records.json','job_manifest.json',
                       'prepared_config.json','prepared_references.npz','prepared_variants.npz',
                       'artifacts/full_structural_certified.npz']
                names += [f'artifacts/full_structural_device{d}/{name}'for d in(0,1)
                          for name in('preflight.json','preflight_packings.npz','preflight_packing_records.json','status.json')]
                contents=args.out/'outputs';contents.mkdir();files={}
                receipt=dict(status='downloading_named_aggregates',notebook=args.notebook,version=args.version,
                             source_sha256=args.source_sha256,private_source_verified=True,files=files)
                for name in names:
                    request=ApiDownloadKernelOutputRequest();request.owner_slug=owner;request.kernel_slug=slug
                    request.version_number=args.version;request.file_path=name
                    redirect=api.download_kernel_output(request);parsed=urlsplit(redirect.url)
                    assert parsed.scheme=='https'and parsed.hostname
                    getter=(gateway.client.http_client()._session.get
                            if parsed.hostname in('www.kaggle.com','api.kaggle.com')else requests.get)
                    target=contents/name;target.parent.mkdir(parents=True,exist_ok=True)
                    digest=hashlib.sha256();size=0
                    with getter(redirect.url,stream=True,timeout=(15,30))as response:
                        response.raise_for_status()
                        with target.open('wb')as stream:
                            for chunk in response.iter_content(1024*1024):
                                if time.monotonic()-started>240:raise TimeoutError('Named collection deadline')
                                size+=len(chunk)
                                if size>256*1024**2:raise ValueError('Named aggregate exceeds256MiB bound')
                                stream.write(chunk);digest.update(chunk)
                    files[name]=dict(sha256=digest.hexdigest(),bytes=size,redirect_host=parsed.hostname)
                    (args.out/'download-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
                    print(json.dumps(dict(downloaded=name,bytes=size)),flush=True)
                receipt.update(status='complete_named_aggregates',file_count=len(files),outputs=str(contents),elapsed_seconds=time.monotonic()-started)
                return
            request=ApiDownloadKernelOutputRequest();request.owner_slug=owner;request.kernel_slug=slug;request.version_number=args.version
            redirect=api.download_kernel_output(request)
            parsed=urlsplit(redirect.url);assert parsed.scheme=='https'and parsed.hostname
            size=0;digest=hashlib.sha256()
            # Private whole-bundle redirects may be an unsigned Kaggle API URL
            # rather than signed object storage. Reuse authenticated SDK session
            # only for exact Kaggle hosts; foreign signed hosts receive no auth.
            getter=(gateway.client.http_client()._session.get
                    if parsed.hostname in('www.kaggle.com','api.kaggle.com')else requests.get)
            with getter(redirect.url,stream=True,timeout=(15,30))as response:
                response.raise_for_status()
                with temporary.open('wb')as stream:
                    for chunk in response.iter_content(1024*1024):
                        if time.monotonic()-started>180:raise TimeoutError('Bundle transfer deadline')
                        size+=len(chunk)
                        if size>1024*1024*1024:raise ValueError('Compressed bundle exceeds1GiB bound')
                        stream.write(chunk);digest.update(chunk)
        archive_path=args.out/'bundle.zip';temporary.replace(archive_path)
        contents=args.out/'outputs';contents.mkdir()
        with zipfile.ZipFile(archive_path)as archive:
            if sum(i.file_size for i in archive.infolist())>4*1024**3:raise ValueError('Expanded bundle exceeds4GiB bound')
            for entry in archive.infolist():
                name=PurePosixPath(entry.filename)
                if name.is_absolute()or'..'in name.parts or'\\'in entry.filename:raise ValueError('Unsafe archive path')
                if (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink forbidden')
                if not(contents/entry.filename).resolve().is_relative_to(contents.resolve()):raise ValueError('Archive traversal')
            assert archive.testzip()is None
            archive.extractall(contents);count=len(archive.infolist())
        receipt=dict(status='complete',notebook=args.notebook,version=args.version,source_sha256=args.source_sha256,
                     private_source_verified=True,compressed_bytes=size,bundle_sha256=digest.hexdigest(),
                     file_count=count,redirect_host=parsed.hostname,outputs=str(contents),elapsed_seconds=time.monotonic()-started)
    except Exception as exc:
        receipt=dict(status='failed',error_type=type(exc).__name__,
                     http_status=getattr(getattr(exc,'response',None),'status_code',None),elapsed_seconds=time.monotonic()-started)
        raise RuntimeError('Output collection failed; see sanitized receipt')from None
    finally:
        temporary.unlink(missing_ok=True)
        (args.out/'download-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
