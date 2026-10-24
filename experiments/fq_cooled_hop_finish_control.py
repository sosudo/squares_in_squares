"""One bounded rigid FQ finish of a retained infeasible cooled-hop best state."""
import time
STARTED=time.monotonic()
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import fq_active_pilot as fq
import fq_remote_cpu_search as remote
from fq_torch_raw_finish_control import recorded_run
from fq_full_structural import descendants
from fq_variant_campaign import atomic_json,atomic_npz,geometry_sha

ROOT=Path(__file__).resolve().parents[1]
HANDOFF=ROOT/'artifacts/packer-hop-cooled-335-v1/best-infeasible-handoff.json'
ARCHIVE_SHA='58af99513d847949e8f9d65d5732b036078989dd6a47a867e94a40a850cc165d'
GEOMETRY_SHA='cef0adb5ddcc0f9296b31908aa2c87fa7ba3faae43f06160c2fff76e85d431d7'
RAW_SHA='aa0a96f88155d8eb8a4df5d8842f1cf335cfe611995008af1441d2dcfd31a95c'
CURRENT_RAW_SHA='a0dad731adc6cacc9c882082aaf9464c7c7fc755ce4eabba6f711b1c31b969bc'
CURRENT_SAFE_SHA='6764e4b48e5218b42f4ddaae83c8e38a81168e74c573404c5e3ee961141a06f0'
BINARY_SHA='10ec7cf773ac0ebca3791d5cfb84e9ecbb10e3f0a9e43194330c80e1cfc9dc3d'


def worker(out,deadline):
    out.mkdir(exist_ok=False);trials=out/'trials';trials.mkdir()
    handoff=json.loads(HANDOFF.read_text());archive=ROOT/handoff['archive'];raw=ROOT/handoff['exact_raw_file']
    if handoff['archive_sha256']!=ARCHIVE_SHA or fq.digest(archive)!=ARCHIVE_SHA:
        raise ValueError('Exact radians initializer archive changed')
    if handoff['exact_raw_sha256']!=RAW_SHA or fq.digest(raw)!=RAW_SHA:
        raise ValueError('Exact raw radians record changed')
    with np.load(archive,allow_pickle=False)as z:p=z['pose'].copy()
    if p.shape!=(335,3)or not np.isfinite(p).all()or geometry_sha(p)!=GEOMETRY_SHA or handoff['geometry_sha256']!=GEOMETRY_SHA:
        raise ValueError('Exact radians initializer geometry differs')
    lines=raw.read_text().splitlines();header=lines[0].split()
    parsed=np.array([[float(x)for x in line.split()]for line in lines[1:]])
    if int(header[0])!=335 or float(header[1])!=18.807 or not np.array_equal(parsed,p):
        raise ValueError('Raw radians text does not reconstruct the archived geometry')
    source_manifest=ROOT/'artifacts/packer-hop-cooled-v1-source/source-manifest.json'
    source=json.loads(source_manifest.read_text())
    parent_manifest=HANDOFF.parent/'manifest.json';parent=json.loads(parent_manifest.read_text())
    if fq.digest(parent_manifest)!=handoff['manifest_sha256']or fq.digest(source_manifest)!=parent['source_manifest_sha256']:
        raise ValueError('Hop source provenance differs')
    binary=Path('/tmp/squares-fq-portable-target/release/fq')
    if fq.digest(binary)!=BINARY_SHA:raise ValueError('Exact portable FQ binary differs')
    pointer=json.loads((ROOT/'artifacts/current-best-portfolio.json').read_text());current=pointer['raw']
    if current['sha256']!=CURRENT_RAW_SHA or pointer['safe']['sha256']!=CURRENT_SAFE_SHA:
        raise ValueError('Expected canonical6764/a0dad baseline')
    if fq.digest(Path(current['path']))!=CURRENT_RAW_SHA:raise ValueError('Canonical RAW bytes differ')
    report_path=Path(current['official_report'])
    if fq.digest(report_path)!=current['official_report_sha256']:raise ValueError('Canonical report differs')
    report=json.loads(report_path.read_text())
    if not report['valid']or report['sha256']!=CURRENT_RAW_SHA:raise ValueError('Canonical report binding failed')
    current_side=next(r['side']for r in report['results']if r['n']==335)
    atomic_npz(out/'unverified-input.npz',{'pose':p})
    options=['--loosen','1','--outer','45','--pit','100','--flip-top','16','--v']
    manifest=dict(input_handoff_path=str(HANDOFF),input_handoff_sha256=fq.digest(HANDOFF),handoff=handoff,
        input_archive_sha256=ARCHIVE_SHA,geometry_sha256=GEOMETRY_SHA,raw_text_sha256=RAW_SHA,
        source_manifest=source,source_manifest_sha256=fq.digest(source_manifest),
        input_status='UNVERIFIED and overlapping. No initializer legalization/rescaling. FQ encoding translates centers only.',
        energy_semantics='Raw fixed-box energy and span are not a feasible score; only fully certified terminal geometry is admissible.',
        options=options,workers=1,trial_seconds=25,outer_seconds=45,native_binary_sha256=BINARY_SHA,
        native_commit=fq.SOURCE_COMMIT,license='MIT; Evan Daniel',current_raw=current,current_side=current_side,
        source_sha256=fq.digest(Path(__file__)),helper_hashes={str(path.relative_to(ROOT)):fq.digest(path)for path in
            [Path(remote.__file__),Path(fq.__file__),ROOT/'experiments/fq_torch_raw_finish_control.py',
             ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/compose_gadgets.py',ROOT/'research/official_metric_v17.py']},
        no_gpu=True,no_submission=True)
    atomic_json(out/'manifest.json',manifest)
    mode='cooled_hop_best_rigid';fq.MODES[mode]=options;remote.grouped_run=recorded_run
    record,_=remote.strict_trial(('18_18_11',p,mode,str(binary),str(trials.resolve()),23147001,25.,deadline-3))
    record.update(initializer_geometry_sha256=GEOMETRY_SHA,initializer_verified=False,current_raw_side=current_side)
    if record.get('certificate',{}).get('valid'):
        terminal=record['certificate']['shared_official_gate']['raw_side']
        record.update(terminal_official_side=terminal,terminal_side_gain_vs_current=float(current_side)-float(terminal))
    atomic_json(out/'result.json',record);aggregate=remote.collect(out)
    summary=dict(status=record['status'],terminal_official_side=record.get('terminal_official_side'),
        terminal_side_gain_vs_current=record.get('terminal_side_gain_vs_current'),aggregate=aggregate,
        elapsed_seconds=time.monotonic()-STARTED,result_sha256=fq.digest(out/'result.json'),
        manifest_sha256=fq.digest(out/'manifest.json'),no_raw_initializer_gain_claim=True)
    atomic_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        if args.out.exists():raise ValueError('Fresh output required')
        source=args.out.with_name(args.out.name+'-source');source.mkdir();(source/'executed_source.py').write_bytes(Path(__file__).read_bytes())
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+42)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+43-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(process.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in descendants(process.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1)
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,maximum_seconds=45,
            hard_deadline_enforced=forced,workers=1,source_sha256=fq.digest(Path(__file__)))
        if args.out.exists():atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
