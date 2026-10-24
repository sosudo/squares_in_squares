"""Four-worker actual-held full-puzzle continuation with explicit frozen starts."""
from __future__ import annotations
import argparse
import ast
import inspect
import json
from pathlib import Path
import numpy as np
import fq_remote_cpu_search as remote
import fq_productive_campaign as productive
from fq_full_round_control import rounded_run
from fq_variant_campaign import geometry_sha

CAPS={147:20.,299:45.,335:60.}
MODE_OPTIONS={'held_r010_k020':('.1','.02'),'held_r015_k040':('.15','.04'),
              'held_r030_k040':('.3','.04'),'held_r030_k080':('.3','.08')}


def actual_held_run(command,**kwargs):
    result=rounded_run(command,**kwargs)
    if result.returncode==0:
        expected=float(Path(command[command.index('--in')+1]).read_text().splitlines()[0].split()[1])
        info=json.loads(result.stdout.strip().splitlines()[-1])['round']
        if '--round-compress'in command or command[command.index('--hold-f')+1]!='1':
            raise ValueError('Only actual selected-parent box rehardening is allowed')
        if max(abs(info['s_soft']-expected),abs(info['s_hold']-expected))>1e-10:
            raise ValueError('Native rounded continuation held a different box')
    return result


def configured_round_trial(job,options):
    key,pose,mode,binary,directory,seed,cap,deadline=job
    n=len(pose)
    if n not in CAPS:raise ValueError('Unsupported full-puzzle count')
    remote.fq.MODES[mode]=list(options);remote.grouped_run=actual_held_run
    return remote.strict_trial((key,pose,mode,binary,directory,seed,min(cap,CAPS[n]),deadline))


def freeze_start_sources(reference,pools,expected):
    frozen={}
    for key,p in reference.items():
        original=p.copy();original.setflags(write=False);alternates=[]
        for entry in pools[key].values():
            item=dict(entry);item['pose']=entry['pose'].copy();item['pose'].setflags(write=False)
            if geometry_sha(item['pose'])!=item['geometry_sha256']:raise ValueError('Immutable input geometry differs')
            alternates.append(item)
        alternates=tuple(sorted(alternates,key=lambda row:row['geometry_sha256']))
        if {row['geometry_sha256']for row in alternates}!=set(expected[key]):
            raise ValueError('Controlled alternatives were lost to a source cutoff or coarse bucket')
        frozen[key]=dict(original=original,original_sha256=geometry_sha(original),alternates=alternates)
    return frozen


def choose_start(key,visit,best,frozen):
    entry=frozen[key]
    if visit%4==3:
        pose=entry['original'].copy()
        parent=dict(source_archive='reference_0',source_name=key,geometry_sha256=entry['original_sha256'],
            selection='original_current',source_pool='immutable_original_current')
    elif visit%4==1:
        alternatives=entry['alternates'];index=(visit//4)%len(alternatives);selected=alternatives[index]
        pose=selected['pose'].copy()
        parent={field:selected[field]for field in ['source_archive','source_name','geometry_sha256','bucket']}
        parent.update(selection='immutable_control',source_pool='immutable_control_outputs',
            source_pool_index=index,source_pool_size=len(alternatives),source_pool_cycle=(visit//4)//len(alternatives))
    else:
        pose=best[key].copy();parent=dict(source_archive='campaign_best',source_name=key,
            geometry_sha256=geometry_sha(pose),selection='incumbent',source_pool='campaign_best')
    if geometry_sha(pose)!=parent['geometry_sha256']:raise ValueError('Selected pose and source differ')
    return pose,parent


def start_manifest(frozen):
    return {key:dict(original_geometry_sha256=entry['original_sha256'],
        alternatives=[{field:row[field]for field in ['source_archive','source_name','geometry_sha256','excess']}
                      for row in entry['alternates']])for key,entry in frozen.items()}


def select_mode(key,visit,offset,frozen,modes):
    """Cycle settings per source, independently of the weighted case schedule."""
    phase=visit%4;block=visit//4
    if phase==1:
        counter=block//len(frozen[key]['alternates'])
    elif phase==3:
        counter=block
    else:
        counter=2*block+phase//2
    return modes[(counter+offset)%len(modes)]


def build_runtime(config):
    """One checked AST copy of the established scheduler; its gates are unchanged."""
    original=productive.fixed.large.local._ordinary_campaign
    tree=ast.parse(inspect.getsource(original));function=tree.body[0]
    counts=dict(input_cutoff=0,bucket=0,mode_rotation=0,selection=0,freeze=0,manifest=0,fork=0)

    class Adapter(ast.NodeTransformer):
        def visit_If(self,node):
            if ast.unparse(node.test)=='excess > baseline[key] + 0.005':
                counts['input_cutoff']+=1
                return ast.parse("if not np.isfinite(excess): raise ValueError('Nonfinite immutable input')").body[0]
            if ast.unparse(node.test)=='visit % 4 == 3 and pool':
                counts['selection']+=1
                return ast.parse('pose, parent = choose_start(key, visit, best, frozen_starts)').body[0]
            return self.generic_visit(node)

        def visit_Assign(self,node):
            if (len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
                    and node.targets[0].id=='bucket' and ast.unparse(node.value)=='diversity_bucket(pose)'):
                counts['bucket']+=1
                if counts['bucket']==1:node.value=ast.Name(id='sha',ctx=ast.Load())
            if (len(node.targets)==1 and isinstance(node.targets[0],ast.Name)and node.targets[0].id=='slot'):
                if ast.unparse(node.value)!='MODE_SLOTS[(visit + key_offsets[key]) % len(MODE_SLOTS)]':
                    raise ValueError('Original mode schedule changed')
                counts['mode_rotation']+=1
                node.value=ast.parse('select_mode(key, visit, key_offsets[key], frozen_starts, MODE_SLOTS)',mode='eval').body
            return self.generic_visit(node)

        def visit_Call(self,node):
            if isinstance(node.func,ast.Name)and node.func.id=='ProcessPoolExecutor':
                if any(k.arg=='mp_context'for k in node.keywords):raise ValueError('Original executor changed')
                counts['fork']+=1
                node.keywords.append(ast.keyword(arg='mp_context',value=ast.parse("mp.get_context('fork')",mode='eval').body))
            return self.generic_visit(node)

    function=Adapter().visit(function);body=[]
    for statement in function.body:
        body.append(statement)
        if isinstance(statement,ast.Assign)and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):
            name=statement.targets[0].id
            if name=='keys':
                body.extend(ast.parse('frozen_starts = freeze_start_sources(reference, pools, EXPECTED_ALTERNATES)').body)
                counts['freeze']+=1
            if name=='manifest':
                body.extend(ast.parse("""manifest['restart_policy'] = {
    'original_current_fraction': .25, 'immutable_control_fraction': .25, 'incumbent_fraction': .5,
    'phase_by_visit_mod4': ['incumbent', 'immutable_control', 'incumbent', 'original_current'],
    'sources': start_manifest(frozen_starts), 'input_side_cutoff': None,
    'generated_runtime_sha256': GENERATED_RUNTIME_SHA256}
manifest['selection_note'] = 'Exact frozen originals and all four controlled alternatives are independently scheduled; the wider335 source is not discarded by the legacy.005 cutoff.'
manifest['budget_note'] = 'Four native workers; whole-stage caps147:20s,299:45s,335:60s including geometry gates. Parent supervisor bounds full execution1500s.'
manifest['actual_held_policy'] = 'Every selected parent is jittered, rounded and re-hardened inside its own encoded box with hold-f1 and no round-compress, then rigid ALM/polish. Native radius0 and held-side identity are checked before every admission.'
""").body)
                counts['manifest']+=1
    function.body=body;tree.body[0]=function
    expected=dict(input_cutoff=1,bucket=2,mode_rotation=1,selection=1,freeze=1,manifest=1,fork=1)
    if counts!=expected:raise ValueError('Original scheduler changed; refuse unchecked AST adaptation: '+repr(counts))
    ast.fix_missing_locations(tree);source=ast.unparse(tree)+'\n'
    namespace=dict(original.__globals__)
    options={mode:['--loosen','1','--round-r0',radius,'--round-steps','12','--round-p','2',
        '--round-kick','.004','--hold-f','1','--outer','45','--pit','100','--flip-top','16','--v','--kick',kick]
        for mode,(radius,kick)in MODE_OPTIONS.items()}
    namespace.update(__file__=__file__,KICK_OPTIONS=options,MODE_SLOTS=list(options),FOCUS=config['weights'],
        configured_trial=configured_round_trial,freeze_start_sources=freeze_start_sources,choose_start=choose_start,
        start_manifest=start_manifest,select_mode=select_mode,EXPECTED_ALTERNATES=config['alternative_geometry_hashes'],
        GENERATED_RUNTIME_SHA256=remote.fq.hashlib.sha256(source.encode()).hexdigest())
    exec(compile(source,__file__,'exec'),namespace)
    return namespace['campaign'],source,counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seconds',type=float,default=1200)
    parser.add_argument('--workers',type=int,default=4);parser.add_argument('--max-trials',type=int,default=0)
    parser.add_argument('--collect-only',action='store_true');args=parser.parse_args()
    if args.collect_only:print(json.dumps(remote.collect(args.out)),flush=True);return
    if not 15<args.seconds<=1200 or not 1<=args.workers<=4 or args.max_trials<0:
        raise ValueError('Authorized full-case CPU bounds exceeded')
    config=json.loads((args.package/'campaign_config.json').read_text())
    if remote.fq.digest(args.binary)!=config['binary_sha256']:raise ValueError('Exact ready binary required')
    for name,expected in config['input_hashes'].items():
        path=args.package/name
        if not path.resolve().is_relative_to(args.package.resolve())or remote.fq.digest(path)!=expected:
            raise ValueError('Exact full-case inputs changed')
    runtime,source,counts=build_runtime(config)
    if remote.fq.hashlib.sha256(source.encode()).hexdigest()!=config['generated_runtime_sha256']:
        raise ValueError('Generated scheduler differs from frozen source')
    args.reference=[args.package/'inputs/reference.npz'];args.donors=[args.package/'inputs/donors.npz']
    args.priorities=args.package/'inputs/priorities.json';args.seed=config['seed'];args.trial_seconds=60.
    runtime(args)
    print(json.dumps(dict(stage='full_rounded_certified_collection',**remote.collect(args.out))),flush=True)


if __name__=='__main__':main()
