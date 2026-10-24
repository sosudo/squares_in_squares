"""Three completion-only reruns of the frozen no-ALM80 experiment; no extra iterations."""
import time
STARTED=time.monotonic()
import argparse
from concurrent.futures import ProcessPoolExecutor,FIRST_COMPLETED,wait
from decimal import Decimal
import hashlib,json,math,multiprocessing as mp,os
from pathlib import Path
import shutil,signal,subprocess,sys
import numpy as np
import fq_current_rigid_campaign as base
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='05c07430d935b6d005ec1d0dde7a383aa32aa6e22745dcfc3dc765f5440d75eb'
RAW_SHA='add7c0ee1599b97bb229f279dd0ee927c502ad6710940faccd92dca7c7658a53'
CASES={997,981,995}
FLAGS=['--no-alm','--loosen','1','--pit','80','--flip-top','0','--v']


def configure_worker():
    """Explicit process-local settings; the imported source is never edited."""
    assert base.digest(Path(base.__file__))==BASE_SHA
    base.RIGID_FLAGS=FLAGS.copy();base.NATIVE_SECONDS=75.;base.CERTIFICATE_SECONDS=8.
    assert not {key for key in os.environ if key.startswith('FQ_')and key not in {'FQ_TR','FQ_LPT'}},'Unexpected inherited native options'
    os.environ.update(FQ_TR='1',FQ_LPT='1')


def campaign(args):
    configure_worker();out=args.out;out.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','trials','raw-returned','decoded','retained','snapshots'):(out/name).mkdir()
    frozen=json.loads((args.inputs/'freeze.json').read_text())
    for name,sha in frozen['files'].items():assert base.digest(args.inputs/name)==sha
    audit=json.loads((args.inputs/'audit.json').read_text());baseline=audit['pointer']['raw'];queue=audit['finite_queue']
    assert baseline['sha256']==RAW_SHA and base.digest(baseline['path'])==RAW_SHA and base.digest(baseline['official_report'])==baseline['official_report_sha256']
    official=json.loads(Path(baseline['official_report']).read_text());assert official['valid']and official['puzzles']==1000 and official['sha256']==RAW_SHA and official['metric_sha256']==base.OFFICIAL_SHA256
    assert len(queue)==3 and {entry['n']for entry in queue}==CASES
    with np.load(args.inputs/'inputs/current-poses.npz',allow_pickle=False)as archive:poses={int(key):archive[key]for key in archive.files}
    assert all(base.geometry_sha(poses[entry['n']])==entry['geometry_sha256']for entry in queue)
    for entry in queue:
        text,_=base.encode(poses[entry['n']],math.isqrt(entry['n']),math.isqrt(entry['n']))
        assert hashlib.sha256(text.encode()).hexdigest()==entry['original_input_sha256']
        assert entry['original_seed']==9610000+entry['original_job']
    sides={r['n']:r['side']for r in official['results']}
    for name in ('audit.json','freeze.json','pointer.json'):shutil.copyfile(args.inputs/name,out/'inputs'/name)
    shutil.copyfile(args.inputs/'inputs/current-poses.npz',out/'inputs/current-poses.npz')
    binary=out/'inputs/fq';shutil.copyfile(args.binary,binary);binary.chmod(0o500);assert base.digest(binary)==base.BINARY_SHA
    paths=[Path(__file__),Path(base.__file__),ROOT/'experiments/prepare_selective_polish_completion.py',ROOT/'experiments/fq_selective_polish_campaign.py',ROOT/'experiments/fq_active_pilot.py',ROOT/'experiments/fq_capacity_probe.py',ROOT/'experiments/fq_joint_seed_check.py',ROOT/'experiments/fq_variant_campaign.py',ROOT/'experiments/compose_gadgets.py',ROOT/'scripts/score_official.py',ROOT/'scripts/validate_submission.py',ROOT/'research/official_metric_v17.py']
    source_hashes={}
    for path in paths:
        dst=out/'source'/path.name;shutil.copyfile(path,dst);dst.chmod(0o444);source_hashes[str(path)]=base.digest(dst)
    manifest=dict(baseline=baseline,input_freeze_sha256=base.digest(args.inputs/'freeze.json'),source_hashes=source_hashes,
        unchanged_worker_sha256=BASE_SHA,binary_sha256=base.BINARY_SHA,source_commit=base.SOURCE_COMMIT,metric_sha256=base.OFFICIAL_SHA256,
        workers=3,maximum_total_seconds=100,flags=FLAGS,environment_overrides={'FQ_TR':'1','FQ_LPT':'1'},
        native_seconds_cap=75,certificate_seconds_cap=8,queue=queue,
        hypothesis='Completion of the same frozen parents, encoded inputs, original seeds and pit80 settings; wall cap and concurrency differ. Only final full gates establish gains.',
        no_native_source_edits=True,no_metric_edits=True,no_canonical_mutation=True,no_submission=True)
    base.atomic_json(out/'manifest.json',manifest);records=[];donors={};candidates={};snapshots=0
    def checkpoint(status,gain=False):
        nonlocal snapshots
        base.atomic_json(out/'results.json',records);base.atomic_json(out/'candidates.json',candidates)
        summary=dict(status=status,seconds=time.monotonic()-STARTED,trials=len(records),queue_count=3,certified_geometries=len(donors),improved_cases=len(candidates),score_gain=sum(r['score_gain']for r in candidates.values()),candidates_sha256=base.digest(out/'candidates.json'),results_sha256=base.digest(out/'results.json'),manifest_sha256=base.digest(out/'manifest.json'),source_hashes_unchanged=all(base.digest(path)==sha for path,sha in source_hashes.items()))
        base.atomic_json(out/'summary.json',summary)
        if gain:
            snapshots+=1;snapshot=out/'snapshots'/f'gain-{snapshots:04d}';snapshot.mkdir()
            for name in ('results.json','candidates.json','summary.json'):shutil.copyfile(out/name,snapshot/name);(snapshot/name).chmod(0o444)
            base.atomic_json(out/'latest-immutable.json',dict(path=str(snapshot),candidate_sha256=base.digest(snapshot/'candidates.json'),results_sha256=base.digest(snapshot/'results.json'),summary_sha256=base.digest(snapshot/'summary.json')))
        return summary
    checkpoint('prepared');pending={};cursor=0
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('fork'),initializer=configure_worker)as pool:
        while cursor<3 or pending:
            while len(pending)<3 and cursor<3 and time.monotonic()<args.deadline-2:
                entry=queue[cursor];cursor+=1;n=entry['n'];pending[pool.submit(base.worker,(n,poses[n],sides[n],entry,entry['original_job'],str(binary.resolve()),str(out.resolve()),args.deadline))]=n
            if not pending:break
            ready,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
            for future in ready:
                pending.pop(future);record,q=future.result();gain=False
                if q is not None:
                    donors[record['archive_key']]=q
                    if Decimal(record['side'])<Decimal(sides[record['n']])-Decimal('1e-8'):
                        candidates[str(record['n'])]=dict(side=record['side'],squares=[[f'{v:.17g}'for v in row]for row in q],certificate=record['certificate'],score_gain=record['score_gain'],source='Selective fresh-feasible no-ALM extended contact polish',provenance=dict(job=record['job'],parent_geometry_sha256=record['parent_geometry_sha256'],native_output_sha256=record['native_output_sha256'],raw_geometry_sha256=record['raw_returned']['geometry_sha256'],command_sha256=record['command_sha256']));gain=True
                records.append(record);summary=checkpoint('running',gain)
                print(json.dumps(dict(n=record['n'],status=record['status'],side_gain=record.get('side_gain'),total_gain=summary['score_gain'],trials=len(records))),flush=True)
            if time.monotonic()>=args.deadline+1:break
    base.atomic_npz(out/'donors.npz',donors);summary=checkpoint('complete'if len(records)==3 else'deadline_partial');final=out/'complete';final.mkdir()
    for name in ('results.json','candidates.json','summary.json','manifest.json','donors.npz'):shutil.copyfile(out/name,final/name);(final/name).chmod(0o444)
    print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--binary',type=Path,default=ROOT/'artifacts/fq-n65-small-v1/inputs/fq');parser.add_argument('--child',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.child:return campaign(args)
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--child','--deadline',str(STARTED+86.)],start_new_session=True);forced=False
    try:child.wait(timeout=max(.01,STARTED+97.-time.monotonic()))
    except subprocess.TimeoutExpired:
        forced=True
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=1.)
    receipt=dict(returncode=child.returncode,seconds=time.monotonic()-STARTED,workers=3,maximum_total_seconds=100,hard_deadline_enforced=forced)
    if args.out.exists():base.atomic_json(args.out/'supervisor.json',receipt)
    print(json.dumps(receipt),flush=True)
    if child.returncode and not forced:raise SystemExit(child.returncode)


if __name__=='__main__':main()
