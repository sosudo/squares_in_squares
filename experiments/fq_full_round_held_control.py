"""Paired<=45s control: jitter all squares, hold the actual incumbent box."""
import time
STARTED=time.monotonic()
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import fq_full_round_control as base

ORIGINAL_RUN=base.rounded_run
ORIGINAL_TRIAL=base.remote.strict_trial


def held_run(command,**kwargs):
    result=ORIGINAL_RUN(command,**kwargs)
    if result.returncode==0:
        expected=float(Path(command[command.index('--in')+1]).read_text().splitlines()[0].split()[1])
        report=json.loads(result.stdout.strip().splitlines()[-1]);rounding=report['round']
        if '--round-compress'in command or float(command[command.index('--hold-f')+1])!=1.:
            raise ValueError('True incumbent-box treatment required')
        if max(abs(rounding['s_soft']-expected),abs(rounding['s_hold']-expected))>1e-10:
            raise ValueError('Native rehardening box differs from the actual encoded incumbent')
    return result


def held_trial(job):
    options=list(base.fq.MODES[job[2]])
    options.remove('--round-compress');options[options.index('--hold-f')+1]='1'
    options+=['--kick','.04']
    base.fq.MODES[job[2]]=options
    return ORIGINAL_TRIAL(job)


def worker(out,deadline):
    prior=Path('artifacts/fq-full-round-control-v1');manifest=json.loads((prior/'manifest.json').read_text())
    if base.fq.digest(prior/'inputs.npz')!=manifest['input_sha256']:
        raise ValueError('Previous fully certified input archive changed')
    cached={row['geometry_sha256']:manifest['input_certificates'][row['key']]
        for row in manifest['selected'].values()}
    def exact_input_certificate(p):
        identity=base.geometry_sha(p)
        if identity not in cached or not cached[identity]['valid']:raise ValueError('Exact input certificate missing')
        return cached[identity]
    source=out.with_name(out.name+'-source');source.mkdir(exist_ok=False)
    base.atomic_json(source/'adapter_manifest.json',dict(source_sha256=base.fq.digest(__file__),
        original_helper_sha256=base.fq.digest(base.__file__),previous_input_manifest_sha256=base.fq.digest(prior/'manifest.json'),
        previous_input_archive_sha256=manifest['input_sha256'],whole_ceiling_seconds=45,
        treatment='No round-compress; hold-f1; all-square initial kick.04; exact incumbent encoded box checked against native JSON before admission.',
        input_certificate_reuse='Exact pose hashes only; every output uses unchanged fresh full gates.'))
    base.PLAN=[(147,'.45',10.),(299,'.3',15.),(335,'.3',15.)]
    base.full_certificate=exact_input_certificate
    base.rounded_run=held_run;base.remote.strict_trial=held_trial
    base.worker(out,deadline)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--deadline',type=float);args=parser.parse_args()
    if args.worker:worker(args.out,args.deadline)
    else:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--out',str(args.out.resolve()),
            '--worker','--deadline',str(STARTED+43)],start_new_session=True);forced=False
        try:process.wait(timeout=max(.01,STARTED+44-time.monotonic()))
        except subprocess.TimeoutExpired:
            forced=True
            try:os.kill(process.pid,signal.SIGSTOP)
            except ProcessLookupError:pass
            for pid in base.descendants(process.pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=1)
        receipt=dict(returncode=process.returncode,whole_seconds=time.monotonic()-STARTED,workers=1,
            hard_deadline_enforced=forced,maximum_seconds=45)
        if args.out.exists():base.atomic_json(args.out/'supervisor.json',receipt)
        print(json.dumps(receipt),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
