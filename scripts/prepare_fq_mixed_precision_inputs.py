#!/usr/bin/env python3
"""Freeze the predeclared first/last completed cold-transfer proposals exactly."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np
import build_fq_mixed_precision_job as builder

ROOT = Path(__file__).resolve().parents[1]
AGGREGATES = ROOT/'artifacts/fq-cold-transfer-results-v1'
PACKETS = ROOT/'artifacts/fq-cold-transfer-packet-fixtures-v1'
SELECTION = {803:(1,248),861:(1,238)}


def sha(data): return hashlib.sha256(data).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2)+'\n')


def receipt(root):
    value=json.loads((root/'download-receipt.json').read_bytes())
    if not (value['status']=='complete' and value['version']==1 and value['private_source_verified']
            and value['notebook']=='sos54352/squares-cold-transfer-803-861'
            and value['source_sha256']==builder.PARENT_SHA):
        raise ValueError('Exact private source receipt required')
    return value


def checked(root, record, name):
    path=root/'outputs'/name; data=path.read_bytes()
    if sha(data)!=record['files'][name]['sha256']: raise ValueError('Downloaded bytes differ: '+name)
    return data


def prepare(out):
    if out.exists(): raise ValueError('Use a fresh fixture freeze directory')
    aggregates, packets=receipt(AGGREGATES),receipt(PACKETS)
    _,_,parent=builder.unpack(builder.PARENT,builder.PARENT_SHA,'xz85')
    cuda,cuda_proof=builder.corrected_source(parent['public_solver/gpu_topology.py'],parent['public_solver/gpu_rect_optimizer.py'])
    out.mkdir(parents=True); provenance=out/'provenance'; provenance.mkdir()
    arrays={}; batches=[]; selected=[]
    for label,root in [('aggregate',AGGREGATES),('packet',PACKETS)]:
        shutil.copyfile(root/'download-receipt.json',provenance/(label+'-download-receipt.json'))
    for n,indices in SELECTION.items():
        prefix='case-'+str(n)
        index_bytes=checked(AGGREGATES,aggregates,prefix+'/raw-index.json')
        design_bytes=checked(AGGREGATES,aggregates,prefix+'/chain-design.json')
        events_bytes=checked(AGGREGATES,aggregates,prefix+'/hop-events.jsonl')
        case_bytes=checked(AGGREGATES,aggregates,prefix+'/case-config.json')
        index=json.loads(index_bytes); design=json.loads(design_bytes)
        events=[json.loads(line) for line in events_bytes.splitlines() if line.strip()]
        terminal=max(row['index'] for row in index['packets'] if row['status']=='completed')
        if indices!=(1,terminal): raise ValueError('Predeclared early/terminal indices differ')
        for name,data in [('raw-index.json',index_bytes),('chain-design.json',design_bytes),('case-config.json',case_bytes)]:
            (provenance/(prefix+'-'+name)).write_bytes(data)
        for epoch,packet_index in zip(('early','late'),indices):
            entry=next(row for row in index['packets'] if row['index']==packet_index)
            if entry['status']!='completed': raise ValueError('Only completed proposals may be selected')
            packet_name=prefix+'/'+entry['path']; packet_bytes=checked(PACKETS,packets,packet_name)
            if sha(packet_bytes)!=entry['sha256']: raise ValueError('Packet receipt/index mismatch')
            packet_path=PACKETS/'outputs'/packet_name
            with np.load(packet_path,allow_pickle=False) as z:
                metadata=json.loads(z['metadata_json'].tobytes())
                if set(metadata['array_sha256'])!=set(z.files)-{'metadata_json'}:
                    raise ValueError('Packet member inventory differs')
                for name,digest in metadata['array_sha256'].items():
                    if sha(z[name].tobytes())!=digest: raise ValueError('Packet member hash differs')
                if metadata['status']!='completed' or metadata['design']!=design or metadata['initialization']:
                    raise ValueError('Unexpected packet protocol or initialization state')
                event=next(e for e in events if e['packet']['index']==packet_index)
                if event['packet']!=entry or {k:v for k,v in event.items() if k!='packet'}!=metadata['event']:
                    raise ValueError('Event/packet/index binding differs')
                q=z['proposal_input'].copy(); boxes=z['sides'].copy()
                if q.dtype!=np.float64 or q.shape!=(32,n,3) or boxes.shape!=(32,) or not np.isfinite(q).all():
                    raise ValueError('Exact finite full-N B32 packet required')
                if not np.array_equal(boxes,np.array([row['side'] for row in design],dtype=np.float64)):
                    raise ValueError('Exact original per-chain boxes required')
                key='n'+str(n)+'_'+epoch; pose_key=key+'_poses'; boxes_key=key+'_boxes'
                arrays[pose_key]=q; arrays[boxes_key]=boxes
            metadata_file=provenance/(key+'-packet-metadata.json'); save(metadata_file,metadata)
            packet_binding=dict(path=str(packet_path),sha256=entry['sha256'],index=packet_index,
                source_notebook=packets['notebook'],source_version=1,source_sha256=packets['source_sha256'],
                packet_metadata_sha256=sha(metadata_file.read_bytes()),event_file_sha256=sha(events_bytes),
                selected_event_sha256=sha(json.dumps(metadata['event'],sort_keys=True,separators=(',',':')).encode()))
            batch=dict(key=key,n=n,epoch=epoch,pose_key=pose_key,boxes_key=boxes_key,
                pose_sha256=sha(q.tobytes()),boxes_sha256=sha(boxes.tobytes()),source_packet=packet_binding)
            batches.append(batch); selected.append(batch)
    np.savez(out/'mixed-inputs.npz',**arrays)
    with np.load(out/'mixed-inputs.npz',allow_pickle=False) as restored:
        if restored.files!=list(arrays) or any(restored[k].tobytes()!=arrays[k].tobytes() for k in arrays):
            raise ValueError('Fixture archive did not preserve exact bytes/order')
    archive_sha=sha((out/'mixed-inputs.npz').read_bytes())
    proof=dict(inputs_sha256=archive_sha, arrays={k:dict(shape=list(v.shape),dtype=v.dtype.str,sha256=sha(v.tobytes()))for k,v in arrays.items()},
        selected_batches=selected,selection_policy='Exactly packet1 and terminal completed proposal_input per803/861; no energy-based selection.',
        source_receipts={label:sha((root/'download-receipt.json').read_bytes())for label,root in [('aggregate',AGGREGATES),('packet',PACKETS)]},
        preparation_source_sha256=sha(Path(__file__).read_bytes()),cuda_reconstruction=cuda_proof,
        no_coordinate_changes=True,verified_geometry=False,
        scope='Original FP64 proposal inputs and boxes only. Raw proposals remain UNVERIFIED; no certificate or feasibility claim.')
    save(out/'input-proof.json',proof)
    config=dict(corrected_fp64_cuda_path='corrected-fp64.cu',corrected_fp64_cuda_sha256=sha(cuda),
        inputs_path='mixed-inputs.npz',inputs_sha256=archive_sha,batches=batches,work_seconds=240,
        occupancy=dict(enabled=True,steps=2000,batch_sizes=[32,64,128],fixture_key='n803_early'),
        protocol=dict(arms={'A':[['fp64',2000]],'B':[['fp32',1500],['fp64',500]],'C':[['fp64',1500],['fp64',500]]},
            repeats=3,order='ABC/BCA/CAB',phase2_fresh_optimizer_state=True,original_fp64_boxes_in_phase2=True),
        runtime_priority=['mandatory_live_controls','predeclared_fp64_occupancy','order_rotated_primary_pipelines'],
        compiler_options=['--std=c++17','--fmad=false'],native_finish=False,search_campaign=False)
    save(out/'mixed-config.json',config)
    shutil.copyfile(Path(__file__),provenance/'prepare-mixed-inputs.py')
    print(json.dumps(dict(out=str(out),inputs_sha256=archive_sha,raw_bytes=sum(v.nbytes for v in arrays.values()),
                         archive_bytes=(out/'mixed-inputs.npz').stat().st_size,selected=[(r['n'],r['epoch'],r['source_packet']['index'])for r in batches])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    prepare(parser.parse_args().out)
