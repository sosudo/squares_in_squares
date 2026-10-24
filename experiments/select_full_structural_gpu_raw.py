"""Bounded complete metadata scan and exact selected-pose verification only."""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path
import time
import zipfile
import numpy as np
from packer_hop_physical_energy import physical_energy
from native_input_format import encode


def sha(data): return hashlib.sha256(data).hexdigest()
def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def save(path,value):
    temporary=path.with_suffix(path.suffix+'.incoming')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)


def weighted_energy(p,box):
    """Independent all-pairs reconstruction of the frozen CUDA reporting loss."""
    x,y,a=p.T;c=np.cos(a);s=np.sin(a);half=.5*(abs(c)+abs(s))
    wall=np.maximum(0.,np.stack((half-x,half-y,x+half-box,y+half-box)))
    i,j=np.triu_indices(len(p),1);dx=x[j]-x[i];dy=y[j]-y[i]
    cd=c[i]*c[j]+s[i]*s[j];sd=c[i]*s[j]-s[i]*c[j]
    radius=.5*(1+abs(cd)+abs(sd))+2e-10
    projections=np.stack((dx*c[i]+dy*s[i],-dx*s[i]+dy*c[i],dx*c[j]+dy*s[j],-dx*s[j]+dy*c[j]))
    overlap=np.maximum(0.,radius-np.max(abs(projections),axis=0))
    return dict(energy=float(2*np.sum(wall*wall)+.5*np.sum(overlap*overlap)),
                residual=float(max(wall.max(initial=0.),overlap.max(initial=0.))))


def metadata(path):
    with zipfile.ZipFile(path) as archive:
        item=archive.getinfo('metadata_json.npy')
        if item.file_size>2_000_000: raise ValueError('Unexpected metadata size')
        return json.loads(np.load(io.BytesIO(archive.read(item)),allow_pickle=False).tobytes())


def analyze(root,config,out,deadline):
    started=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    root=root.resolve();index_path=root/'full_structural_v2_raw_index.json'
    assert digest(index_path)==config['index_sha256']
    assert digest(root/'job_manifest.json')==config['parent_manifest_sha256']
    index=json.loads(index_path.read_bytes());assert index['validated'] is False
    expected=[dict(record,device=str(device)) for device,rows in index['files'].items() for record in rows]
    assert len(expected)==config['expected_packet_count']
    rank={n:[] for n in (147,299,335)};scanned=[];eligible=0
    report=dict(status='scanning',source_notebook=config['parent_ref'],source_sha256=config['parent_source_sha256'],
        index_sha256=config['index_sha256'],expected_packet_count=len(expected),metadata_packets_scanned=0,
        metadata_scan_complete=False,selected=[],all_packet_hashes_verified=False,full_packet_hashes_verified=0,
        optimization_performed=False,geometry_certification_performed=False,competition_submission_performed=False,
        ranking_metric='Frozen fresh CUDA loss: 2*wall_squared + .5*unordered_pair_squared with2e-10 pair margin.',
        scope='All metadata records are scanned before selection; full file hashes initially only for selected packets. '
              'Global physical-energy minimum is not claimed. Selected exact raw poses remain UNVERIFIED.')
    for entry in expected:
        if time.monotonic()>deadline-35: break
        path=(root/entry['path']).resolve();assert path.is_relative_to(root)
        assert path.stat().st_size==entry['bytes']
        m=metadata(path);n=int(m['n']);assert n in rank and m['validated'] is False and len(m['rows'])==32
        assert m['array_sha256']['input']==entry['input_sha256']
        assert [s['label'] for s in m['stages']]==entry['stages']
        scanned.append(dict(path=entry['path'],metadata_sha256=sha(json.dumps(m,sort_keys=True,separators=(',',':')).encode())))
        for stage in m['stages']:
            label=stage['label']
            if not label.startswith('target'): continue
            assert stage['tau']==0. and len(stage['exact_energies'])==32
            for replica,row in enumerate(m['rows']):
                box=stage['box_sides'][replica];energy=stage['exact_energies'][replica];residual=stage['exact_residuals'][replica]
                if any(v is None or not math.isfinite(v) for v in (box,energy,residual)) or energy<0: continue
                gap=Decimal(config['current_reference_sides'][str(n)])-Decimal(str(box))
                if gap<Decimal('.001'): continue
                eligible+=1
                rank[n].append(dict(n=n,packet=entry['path'],packet_sha256=entry['sha256'],device=entry['device'],
                    stage=label,replica=replica,source_id=row['source_id'],box=box,target_gap_vs_current=str(gap),
                    weighted_energy=energy,residual=residual,stage_array_sha256=m['array_sha256'][label],
                    input_array_sha256=entry['input_sha256'],input_geometry_sha256=row['mutation']['input_geometry_sha256'],
                    row=row,arm=m['arm']))
        if len(scanned)%64==0:
            report.update(metadata_packets_scanned=len(scanned),eligible_rows=eligible,seconds=time.monotonic()-started)
            save(out/'progress.json',report)
    report.update(metadata_packets_scanned=len(scanned),metadata_scan_complete=len(scanned)==len(expected),eligible_rows=eligible)
    save(out/'metadata-inventory.json',scanned)
    # No selections from a partial metadata scan: avoid conflating a prefix with the complete population.
    if not report['metadata_scan_complete']:
        report.update(status='metadata-budget-partial',seconds=time.monotonic()-started)
        save(out/'selection-report.json',report);return report
    full_hashes={};arrays={};selected=[];excluded={x['geometry_sha256'] for x in config['excluded_rows']}
    excluded_encoded={x['native_encoded_input_sha256'] for x in config['excluded_rows']}
    seen={n:set() for n in rank};geometry_seen=set();exclusion_count=0;tested=0
    by_path={x['path']:x for x in expected}
    def load_candidate(row):
        path=root/row['packet'];entry=by_path[row['packet']]
        if row['packet'] not in full_hashes:
            actual=digest(path);assert actual==entry['sha256'];full_hashes[row['packet']]=actual
        with np.load(path,allow_pickle=False) as z:
            m=json.loads(z['metadata_json'].tobytes());inputs=z['input'];stage=z[row['stage']]
            assert inputs.shape==(32,row['n'],3) and stage.shape==inputs.shape
            assert inputs.dtype==stage.dtype==np.dtype('<f8')
            assert sha(inputs.tobytes())==row['input_array_sha256']==m['array_sha256']['input']
            assert sha(stage.tobytes())==row['stage_array_sha256']==m['array_sha256'][row['stage']]
            assert m['rows'][row['replica']]==row['row']
            q=stage[row['replica']].copy();original=inputs[row['replica']].copy()
            assert sha(original.tobytes())==row['input_geometry_sha256'] and np.isfinite(q).all()
        return q,original
    # Round-robin cases prevents one case consuming the bounded verification reserve.
    candidates={n:iter(sorted(rows,key=lambda r:(r['weighted_energy'],r['residual'],r['packet'],r['stage'],r['replica']))) for n,rows in rank.items()}
    exhausted=set();counts={n:0 for n in rank}
    while len(exhausted)<3 and time.monotonic()<deadline-10:
        for n in (147,299,335):
            if n in exhausted: continue
            if counts[n]>=8: exhausted.add(n);continue
            while True:
                try:row=next(candidates[n])
                except StopIteration:exhausted.add(n);row=None;break
                if row['source_id'] not in seen[n]:break
            if row is None:continue
            q,original=load_candidate(row);tested+=1;geometry=sha(q.tobytes())
            encoded,offsets=encode(q,math.isqrt(n),math.isqrt(n));assert offsets==[0,0]
            encoded_sha=sha(encoded.encode())
            if geometry in excluded or encoded_sha in excluded_encoded or geometry in geometry_seen:
                exclusion_count+=1;continue
            weighted=weighted_energy(q,row['box']);physical=physical_energy(q,row['box'])
            assert abs(weighted['energy']-row['weighted_energy'])<=1e-12+1e-8*abs(row['weighted_energy'])
            assert abs(weighted['residual']-row['residual'])<=1e-10
            key=f'n{n}_{counts[n]:02d}';arrays[key]=q;arrays[key+'__source_input']=original
            selected.append(dict(row,key=key,geometry_sha256=geometry,native_encoded_input_sha256=encoded_sha,
                cpu_weighted_energy=weighted,physical_energy=physical,verified_geometry=False,
                selection='Lowest metadata loss among remaining distinct source IDs; exact previously tested geometry/native-input exclusions.'))
            seen[n].add(row['source_id']);geometry_seen.add(geometry);counts[n]+=1
            np.savez_compressed(out/'selected-raw-states.npz',**arrays)
            save(out/'selected-rows.json',selected)
    # Opportunistic complete hash audit uses only the remaining fixed budget.
    for entry in expected:
        if time.monotonic()>deadline-3:break
        if entry['path'] in full_hashes:continue
        actual=digest(root/entry['path']);assert actual==entry['sha256'];full_hashes[entry['path']]=actual
    save(out/'full-packet-hash-audit.json',full_hashes)
    compact={str(n):{k:v for k,v in min(rows,key=lambda x:x['weighted_energy']).items() if k!='row'} if rows else None for n,rows in rank.items()}
    report.update(status='complete' if all(counts[n]>=8 for n in counts) else 'bounded-selection',selected=selected,
        selected_counts=counts,metadata_minima=compact,distinct_source_counts={str(n):len({r['source_id']for r in rows})for n,rows in rank.items()},
        selected_packet_hashes_verified=True,full_packet_hashes_verified=len(full_hashes),
        all_packet_hashes_verified=len(full_hashes)==len(expected),verified_candidate_loads=tested,excluded_or_duplicate_geometries=exclusion_count,
        metadata_inventory_sha256=digest(out/'metadata-inventory.json'),full_packet_hash_audit_sha256=digest(out/'full-packet-hash-audit.json'),
        selected_archive_sha256=digest(out/'selected-raw-states.npz') if arrays else None,
        seconds=time.monotonic()-started,current_reference_proof=config['current_reference_proof'])
    save(out/'selection-report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args()
    report=analyze(args.root,json.loads(args.config.read_bytes()),args.out,args.deadline)
    print(json.dumps({k:v for k,v in report.items() if k not in ('selected','metadata_minima')}),flush=True)


if __name__=='__main__':main()
