#!/usr/bin/env python3
"""Bounded read-only monitor for one immutable targeted FTMC notebook version.

Polls official status and nested SSE logs; terminal outputs use exact known file
names only. No output pagination, notebook mutation, search launch or submission.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time
from urllib.parse import urlsplit

from submission_scheduler import KaggleGateway

NOTEBOOK='sos54352/squares-targeted-ftmc-n65-v1'
VERSION=1
SOURCE_SHA256='0aa0b1177774e46d2349520530cfc0757a40b73f2b129c1f504b284d40910e9b'
TERMINAL={'COMPLETE','ERROR','FAILED','CANCELLED','CANCELED','CANCEL_ACKNOWLEDGED'}
OUTPUT_FILES=(
    'job_manifest.json','preflight.json','heartbeat.json','campaign_incumbents.json',
    'ftmc_summary.json','ftmc_candidates.json','artifacts/campaign_gadgets.npz',
    'artifacts/campaign_strict_gadgets.npz','artifacts/campaign_best_gadgets.npz',
    *tuple(name for device in(0,1)for name in(
        f'policy_device{device}.json',f'artifacts/device{device}_initial_bank.npz',
        f'artifacts/certified_device{device}.json',f'artifacts/certified_device{device}.npz',
        f'artifacts/certified_device{device}_best.npz',f'artifacts/certified_device{device}_incumbents.npz',
        f'research/worker{device}_status.json',f'research/combined_funnel_device{device}.json',
        f'research/combined_refill_budget_device{device}.json')))


class MonitorLimit(Exception):pass
class MonitorStopped(Exception):pass


def now():return datetime.now(timezone.utc).isoformat()


def file_sha256(path):
    value=hashlib.sha256()
    with Path(path).open('rb')as stream:
        while chunk:=stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


def remaining_window(plan,requested,wall_now=None):
    if(plan.get('notebook')!=NOTEBOOK or plan.get('version')!=VERSION
       or plan.get('source_sha256')!=SOURCE_SHA256):raise ValueError('Monitor plan identity mismatch')
    origin=datetime.fromisoformat(plan['started_at_utc']);deadline=datetime.fromisoformat(plan['deadline_utc'])
    if deadline>origin+timedelta(seconds=4200):raise ValueError('Monitor plan exceeds the authorized70-minute bound')
    return max(0.,min(requested,(deadline-(wall_now or datetime.now(timezone.utc))).total_seconds()))


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


@contextmanager
def exclusive_lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a')as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Exact-version monitor already active')from None
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


class SSEDecoder:
    """Decode Kaggle data:{stream_name,time,data} wrappers, including fragments."""
    def __init__(self):self.buffers={}
    def feed(self,line):
        if line.startswith('data:'):line=line[5:].lstrip()
        if not line:return[]
        try:outer=json.loads(line)
        except(ValueError,TypeError):return[]
        if not isinstance(outer,dict):return[]
        if 'stage'in outer:return[outer]
        text=outer.get('data');stream=outer.get('stream_name','stdout')
        if not isinstance(text,str)or not isinstance(stream,str):return[]
        pending=self.buffers.get(stream,'')+text;events=[]
        while '\n'in pending:
            item,pending=pending.split('\n',1)
            try:value=json.loads(item)
            except ValueError:continue
            if isinstance(value,dict)and'stage'in value:events.append(value)
        # Bound unstructured lines and avoid retaining arbitrary log payloads.
        self.buffers[stream]=pending[-65536:]
        return events


def numeric(value):
    return value if type(value)in(int,float)and math.isfinite(value)else None


def compact_events(events):
    result={'boundary_preflights':{},'latest_heartbeat':None}
    for event in events:
        if event.get('stage')=='targeted_boundary_preflight':
            data=event.get('result',{});device=str(event.get('device'))
            if device not in('0','1')or not isinstance(data,dict):continue
            families=data.get('all_actual_families',{})
            result['boundary_preflights'][device]={'passed':data.get('passed')is True,
                'row_capacity':numeric(data.get('row_capacity')),'core257_rejected':data.get('core257_rejected')is True,
                'actual_full_count':numeric(data.get('largest_actual_full_count')),
                'active_family_count':len(families)if isinstance(families,dict)else None}
        elif event.get('stage')=='workers':
            devices=event.get('devices',{})
            if not isinstance(devices,dict):continue
            selected={}
            for device,data in devices.items():
                if str(device)not in('0','1')or not isinstance(data,dict):continue
                selected[str(device)]={key:numeric(data.get(key))for key in(
                    'seconds','batches','core_trials','refill_success','full_quenches','accepted','cuda_seconds','returncode')}
            heartbeat={'elapsed':numeric(event.get('elapsed')),'devices':selected}
            old=result['latest_heartbeat']
            if old is None or(heartbeat['elapsed']or 0)>=(old['elapsed']or 0):result['latest_heartbeat']=heartbeat
    return result


def bounded_sdk(api,deadline):
    http=api._client;http._init_session();original=http._session.send
    def send(request,**kwargs):
        remaining=max(.2,deadline-time.monotonic())
        kwargs.setdefault('timeout',(min(10.,remaining),min(25.,remaining)))
        return original(request,**kwargs)
    http._session.send=send


def read_logs(api,deadline):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionLogsStreamRequest
    request=ApiGetKernelSessionLogsStreamRequest();request.user_name=NOTEBOOK.split('/')[0]
    request.kernel_slug=NOTEBOOK.split('/')[1];request.version_label='v'+str(VERSION)
    request.wait_for_logs_url_seconds=2
    decoder=SSEDecoder();events=[];response=None;error=None;begin=time.monotonic();total=0
    try:
        response=api.get_kernel_session_logs_stream(request)
        for raw in response.iter_lines(chunk_size=128):
            total+=len(raw)
            events.extend(decoder.feed(raw.decode('utf8','replace')))
            if time.monotonic()>=min(deadline,begin+35)or total>=2*1024*1024:break
    except(MonitorLimit,MonitorStopped):raise
    except Exception as failure:error={'error_type':type(failure).__name__,
        'http_status':getattr(getattr(failure,'response',None),'status_code',None)}
    finally:
        if response is not None:response.close()
    return {**compact_events(events),'stream_bytes_read':total,'log_error':error}


def poll(deadline,verify_source):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest,ApiGetKernelSessionStatusRequest
    with KaggleGateway()as gateway:
        api=gateway.client.kernels.kernels_api_client;bounded_sdk(api,deadline)
        if verify_source:
            request=ApiGetKernelRequest();request.user_name=NOTEBOOK.split('/')[0]
            request.kernel_slug=NOTEBOOK.split('/')[1];request.version_label='v'+str(VERSION)
            remote=api.get_kernel(request)
            if not remote.metadata.is_private or not remote.metadata.enable_gpu:
                raise ValueError('Exact notebook metadata mismatch')
            if hashlib.sha256(remote.blob.source.encode()).hexdigest()!=SOURCE_SHA256:
                raise ValueError('Exact notebook source hash mismatch')
        request=ApiGetKernelSessionStatusRequest();request.user_name=NOTEBOOK.split('/')[0]
        request.kernel_slug=NOTEBOOK.split('/')[1];request.version_label='v'+str(VERSION)
        status=api.get_kernel_session_status(request).status.name
        logs=read_logs(api,deadline)if status not in TERMINAL else{}
        return {'status':status,'source_verified':True,**logs}


def download_outputs(directory,state_dir,deadline):
    import requests
    from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    manifest_path=Path(state_dir)/'downloads.json'
    if manifest_path.exists():
        ledger=json.loads(manifest_path.read_text())
        if(ledger.get('notebook')!=NOTEBOOK or ledger.get('version')!=VERSION
           or ledger.get('source_sha256')!=SOURCE_SHA256):
            raise ValueError('Output directory has a different notebook identity')
    else:ledger={'notebook':NOTEBOOK,'version':VERSION,'files':{},'source_sha256':SOURCE_SHA256}
    with KaggleGateway()as gateway:
        api=gateway.client.kernels.kernels_api_client;bounded_sdk(api,deadline)
        for name in OUTPUT_FILES:
            if time.monotonic()>=deadline:raise MonitorLimit()
            target=(directory/name).resolve()
            if not target.is_relative_to(directory):raise ValueError('Unsafe output filename')
            target.parent.mkdir(parents=True,exist_ok=True);previous=ledger['files'].get(name,{})
            if target.exists()and previous.get('sha256')==file_sha256(target):continue
            temporary=target.with_suffix(target.suffix+'.incoming')
            try:
                request=ApiDownloadKernelOutputRequest();request.owner_slug=NOTEBOOK.split('/')[0]
                request.kernel_slug=NOTEBOOK.split('/')[1];request.version_number=VERSION;request.file_path=name
                redirect=api.download_kernel_output(request);parsed=urlsplit(redirect.url)
                if parsed.scheme!='https'or not parsed.hostname:raise ValueError('Unexpected output redirect')
                remaining=max(.2,deadline-time.monotonic());sha=hashlib.sha256();size=0
                with requests.get(redirect.url,stream=True,timeout=(min(10.,remaining),min(25.,remaining)))as response:
                    response.raise_for_status()
                    with temporary.open('wb')as stream:
                        for chunk in response.iter_content(1024*1024):
                            if time.monotonic()>=deadline:raise MonitorLimit()
                            size+=len(chunk)
                            if size>512*1024*1024:raise ValueError('Aggregate file exceeds explicit512MiB bound')
                            stream.write(chunk);sha.update(chunk)
                temporary.replace(target)
                ledger['files'][name]={'status':'downloaded','sha256':sha.hexdigest(),'bytes':size,
                                       'path':str(target),'redirect_host':parsed.hostname}
            except(MonitorLimit,MonitorStopped):raise
            except Exception as failure:
                ledger['files'][name]={'status':'unavailable','error_type':type(failure).__name__,
                    'http_status':getattr(getattr(failure,'response',None),'status_code',None)}
            finally:
                temporary.unlink(missing_ok=True);atomic_json(manifest_path,ledger)
    ledger['complete']=all(ledger['files'].get(name,{}).get('status')=='downloaded'for name in OUTPUT_FILES)
    ledger['finished_at_utc']=now();atomic_json(manifest_path,ledger)
    return {'complete':ledger['complete'],'files_downloaded':sum(v.get('status')=='downloaded'for v in ledger['files'].values()),
            'known_files':len(OUTPUT_FILES),'manifest':str(manifest_path),
            'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}


def terminal_downloads(directory,state_dir,deadline,downloader=download_outputs,pause=time.sleep):
    result={'complete':False};attempts=0
    while attempts<3 and time.monotonic()<deadline:
        attempts+=1;result=downloader(directory,state_dir,deadline)
        if result['complete']or deadline-time.monotonic()<=5:break
        if attempts<3:pause(5)
    return {**result,'attempts':attempts}


def terminal_outcome(status,downloads):
    if status!='COMPLETE':return 'kernel_failed',1
    return ('complete',0)if downloads.get('complete')else('outputs_incomplete',2)


def run(args):
    state_dir=args.state_dir.resolve();state_dir.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();deadline=started+args.max_seconds;sequence=0;verified=False;consecutive_errors=0
    latest={'notebook':NOTEBOOK,'version':VERSION,'pid':os.getpid(),'started_at_utc':now(),
            'cadence_seconds':args.cadence,'max_seconds':args.max_seconds,'source_sha256':SOURCE_SHA256,
            'first_poll_success':False,'state':'starting'}
    def save():
        latest['updated_at_utc']=now();latest['elapsed_seconds']=time.monotonic()-started
        latest['overall_elapsed_seconds']=max(0.,(datetime.now(timezone.utc)-datetime.fromisoformat(latest['started_at_utc'])).total_seconds())
        atomic_json(state_dir/'latest.json',latest)
        with(state_dir/'events.jsonl').open('a')as stream:
            stream.write(json.dumps({key:value for key,value in latest.items()if key not in('boundary_preflights',)})+'\n')
        print(json.dumps({key:latest.get(key)for key in('pid','sequence','state','status','first_poll_success','elapsed_seconds')}),flush=True)
    def limit(signum,frame):raise MonitorLimit()
    def stop(signum,frame):raise MonitorStopped()
    signal.signal(signal.SIGALRM,limit);signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    signal.setitimer(signal.ITIMER_REAL,args.max_seconds)
    try:
        with exclusive_lock(state_dir/'monitor.lock'):
            plan_path=state_dir/'monitor-plan.json'
            if plan_path.exists():plan=json.loads(plan_path.read_text())
            else:
                origin=datetime.now(timezone.utc)
                plan={'notebook':NOTEBOOK,'version':VERSION,'source_sha256':SOURCE_SHA256,
                      'started_at_utc':origin.isoformat(),'deadline_utc':(origin+timedelta(seconds=args.max_seconds)).isoformat(),
                      'max_seconds':args.max_seconds}
                atomic_json(plan_path,plan)
            remaining=remaining_window(plan,args.max_seconds)
            latest.update(process_started_at_utc=latest['started_at_utc'],started_at_utc=plan['started_at_utc'],
                          deadline_utc=plan['deadline_utc'],process_limit_seconds=remaining)
            if remaining<=0:raise MonitorLimit()
            deadline=time.monotonic()+remaining;signal.setitimer(signal.ITIMER_REAL,remaining)
            save()
            while time.monotonic()<deadline:
                if(state_dir/'STOP').exists():raise MonitorStopped()
                tick=time.monotonic();sequence+=1;latest['sequence']=sequence
                try:
                    result=poll(deadline,not verified);verified=True;consecutive_errors=0
                    old_heartbeat=latest.get('latest_heartbeat');latest.update(result)
                    if result.get('latest_heartbeat')is None and old_heartbeat is not None:latest['latest_heartbeat']=old_heartbeat
                    latest.update(first_poll_success=True,state='polling')
                    save()
                    if result['status']in TERMINAL:
                        if result['status']=='COMPLETE':
                            latest['state']='downloading';save()
                            try:latest['downloads']=terminal_downloads(args.output_dir,state_dir,deadline)
                            except(MonitorLimit,MonitorStopped):raise
                            except Exception as failure:
                                latest['downloads']={'complete':False,'error_type':type(failure).__name__}
                        latest['state'],code=terminal_outcome(result['status'],latest.get('downloads',{}))
                        save();return code
                except(MonitorLimit,MonitorStopped):raise
                except Exception as failure:
                    consecutive_errors+=1;latest.update(state='poll_error',error_type=type(failure).__name__,consecutive_errors=consecutive_errors)
                    save()
                    if not verified or consecutive_errors>=3:return 2
                if args.once:latest['state']='one_poll_complete';save();return 0
                until=min(deadline,tick+args.cadence)
                while time.monotonic()<until:
                    if(state_dir/'STOP').exists():raise MonitorStopped()
                    time.sleep(min(15.,max(0.,until-time.monotonic())))
    except MonitorLimit:latest['state']='runtime_limit';save();return 0
    except MonitorStopped:latest['state']='stopped';save();return 0
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    latest['state']='runtime_limit';save();return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir',type=Path,default=Path('artifacts/targeted-ftmc-n65-monitor-v1'))
    parser.add_argument('--output-dir',type=Path,default=Path('artifacts/targeted-ftmc-n65-results-v1'))
    parser.add_argument('--cadence',type=float,default=150.)
    parser.add_argument('--max-seconds',type=float,default=4200.)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if not 120<=args.cadence<=180 or not 1<=args.max_seconds<=4200:
        parser.error('Require cadence120–180 seconds and overall bound≤4200 seconds')
    try:raise SystemExit(run(args))
    except RuntimeError as failure:
        print(json.dumps({'state':'lock_refused','error_type':type(failure).__name__}),flush=True);raise SystemExit(2)
    except Exception as failure:
        print(json.dumps({'state':'failed_to_start','error_type':type(failure).__name__}),flush=True);raise SystemExit(2)


if __name__=='__main__':main()
