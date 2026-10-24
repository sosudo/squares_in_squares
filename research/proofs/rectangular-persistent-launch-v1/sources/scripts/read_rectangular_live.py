#!/usr/bin/env python3
"""One bounded read-only live log stream; exact, size-bounded payload recovery."""
from pathlib import Path
import argparse,ast,base64,collections,hashlib,json,signal,sys,time,zlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
FAMILIES={'5_17_7','7_19_13','7_20_14','8_21_13'}
FILES={'family-config.json','chain-design.json','recovery.json','finish/certified.npz','finish/rectangular-donors.npz','finish/results.json','finish/manifest.json','finish/summary.json'}
class ReadBound(BaseException):pass
def stop(*_):raise ReadBound()
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def decode(lines):
 streams=collections.defaultdict(str);chunks=collections.Counter()
 for line in lines:
  if not line.startswith('data: '):continue
  try:outer=json.loads(line[6:])
  except ValueError:continue
  if not isinstance(outer,dict)or not isinstance(outer.get('data'),str):continue
  stream=str(outer.get('stream_name','unknown'));streams[stream]+=outer['data'];chunks[stream]+=1
 events=[];seen=set()
 for stream,text in streams.items():
  for line in text.splitlines():
   try:event=json.loads(line)
   except ValueError:continue
   if isinstance(event,dict):
    identity=sha(line.encode())
    if identity not in seen:events.append(dict(stream=stream,line_sha256=identity,event=event));seen.add(identity)
 return events,dict(chunks)

def unpack_event(record,out,manifest):
 event=record['event'];family=event['family']
 if family not in FAMILIES or event['stage']!='rectangular_family_payload':raise ValueError('Unexpected family payload')
 if event['input_archive_sha256']!=manifest['inputs_sha256']or event['protocol_sha256']!=manifest['files']['rectangular-protocol.json']:raise ValueError('Live payload source/input protocol differs')
 if set(event['files'])!=FILES:raise ValueError('Incomplete live family file inventory')
 decoded={};total=0
 for name,r in event['files'].items():
  if r['encoding']!='zlib1-base85' or not isinstance(r['bytes'],int)or not 0<=r['bytes']<=2*1024**2:raise ValueError('Unexpected live file encoding/size')
  total+=r['bytes']
  if total>2*1024**2:raise ValueError('Live payload exceeds frozen raw cap')
  packed=base64.b85decode(r['data']);decoder=zlib.decompressobj();data=decoder.decompress(packed,r['bytes']+1)
  if not decoder.eof or decoder.unused_data or len(data)!=r['bytes']or sha(data)!=r['sha256']:raise ValueError('Live file decompression/hash differs')
  decoded[name]=data
 folder=out/'families'/family;folder.mkdir(parents=True,exist_ok=False)
 for name,data in decoded.items():
  path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 receipt=dict(family=family,event_line_sha256=record['line_sha256'],files={name:sha(data)for name,data in decoded.items()},
  protocol_sha256=event['protocol_sha256'],input_archive_sha256=event['input_archive_sha256'],bytes=total,
  scope='Exact live transport verified only. Geometry/certificates/native lineage require independent binding before recomposition.',geometry_admitted=False)
 save(folder/'live-transport-proof.json',receipt);return receipt

def main(args):
 started=time.monotonic();args.out.mkdir(parents=True,exist_ok=False);lines=[];raw_bytes=0
 source=(args.job/'search.py').read_bytes();parsed=ast.parse(source);manifest=ast.literal_eval(parsed.body[0].value)
 metadata=json.loads((args.job/'kernel-metadata.json').read_text());owner,slug=metadata['id'].split('/')
 proof=dict(utc=datetime.now(timezone.utc).isoformat(),notebook=metadata['id'],version=args.version,source_sha256=sha(source),
  absolute_read_alarm_seconds=29,one_read_only_log_request=True,decoder='Reassemble outer.data per stream across SSE boundaries, then parse completed JSON lines.')
 signal.signal(signal.SIGALRM,stop);signal.alarm(29)
 try:
  from submission_scheduler import KaggleGateway
  from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest,ApiGetKernelSessionLogsStreamRequest
  with KaggleGateway()as gateway:
   api=gateway.client.kernels.kernels_api_client;request=ApiGetKernelRequest();request.user_name=owner;request.kernel_slug=slug;request.version_label='v'+str(args.version)
   remote=api.get_kernel(request)
   assert sha(remote.blob.source.encode())==sha(source)and remote.metadata.is_private and remote.metadata.enable_gpu
   proof['private_exact_source_verified']=True
   http=gateway.client._http_client;http._init_session();r=ApiGetKernelSessionLogsStreamRequest();r.user_name=owner;r.kernel_slug=slug;r.version_label='v'+str(args.version);r.wait_for_logs_url_seconds=2
   prepared=http._prepare_request('kernels.KernelsApiService','GetKernelSessionLogsStream',r)
   settings=http._session.merge_environment_settings(prepared.url,{},None,None,None);settings.update(stream=True,timeout=(5,10))
   with http._session.send(prepared,**settings)as response:
    proof.update(http_status=response.status_code,content_type=response.headers.get('content-type',''));response.raise_for_status()
    for raw in response.iter_lines(chunk_size=4096):
     line=raw.decode('utf8','replace')
     if 'KGAT_'in line or('https://'in line and('X-Goog-'in line or'X-Amz-'in line)):continue
     lines.append(line);raw_bytes+=len(raw)
     if time.monotonic()-started>=25 or raw_bytes>=8*1024**2:break
 except ReadBound:proof['bounded_end']='29_second_absolute_alarm'
 except Exception as error:proof['read_error_type']=type(error).__name__
 finally:signal.alarm(0)
 log=('\n'.join(lines)+'\n'if lines else'').encode();(args.out/'sanitized.log').write_bytes(log)
 events,chunks=decode(lines);payloads=[]
 for event in events:
  if event['event'].get('stage')=='rectangular_family_payload':payloads.append(unpack_event(event,args.out,manifest))
 save(args.out/'events.json',events)
 proof.update(seconds=time.monotonic()-started,line_count=len(lines),raw_bytes=raw_bytes,stream_sha256=sha(log),stream_chunks=chunks,
  events_sha256=sha((args.out/'events.json').read_bytes()),event_count=len(events),stages=dict(collections.Counter(r['event'].get('stage','summary')for r in events)),
  payloads=payloads,reader_sha256=sha(Path(__file__).read_bytes()),scope='Parent relayed stdout only; empty/partial live stream is not proof of a stalled child.')
 save(args.out/'proof.json',proof)
 print(json.dumps({k:proof[k]for k in('notebook','version','seconds','event_count','stages')},indent=2))
 for row in events[-4:]:
  event=row['event']
  if event.get('stage')!='rectangular_family_payload':print(json.dumps(event)[:1500])
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--version',type=int,default=1);main(ap.parse_args())
