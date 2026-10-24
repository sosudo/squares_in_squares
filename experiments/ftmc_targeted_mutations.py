"""Counted proposal-only FTMC continuation changes; final admission is untouched."""
import ast
import hashlib
import inspect
import numpy as np
from ftmc_adaptive_angles import adaptive_angles


def same(left,right):
    return ast.dump(left,include_attributes=False)==ast.dump(right,include_attributes=False)


def transform_mutations(source,config):
    tree=ast.parse(source);changes={};broad=config['arm']=='broad'
    patterns={
        'angles=np.radians([26.565051,28.072487,33.690068,36.869898,40.,45.,-26.565051,-33.690068])':
            ('adaptive_angles','angles=_targeted_angles(p)'),
        'm=min(len(p)-2,max(4,m0+offset))':('bounded_core_count','m=min(256,len(p)-2,max(4,m0+offset))')}
    if broad:
        patterns['offset=1 if mode==1 else -int(rng.integers(1,4))if mode==2 else 0']=(
            'broader_core_count_moves','offset=_targeted_offset(mode,rng)')
    calls={
        'rng.normal(0,.018 if b%2 else .065)':('broader_rotation','rng.normal(0,.04 if b%2 else .12)'),
        'rng.normal(0,.015)':('broader_shear','rng.normal(0,.035)'),
        'rng.normal(0,.004,q[:,:2].shape)':('broader_position','rng.normal(0,.012,q[:,:2].shape)')}
    class Adapt(ast.NodeTransformer):
        def record(self,label,node):
            changes[label]=changes.get(label,0)+1;return node
        def visit_Assign(self,node):
            for old,(label,new)in patterns.items():
                if same(node,ast.parse(old).body[0]):return self.record(label,ast.parse(new).body[0])
            return self.generic_visit(node)
        def visit_Compare(self,node):
            if same(node,ast.parse('len(core)>160',mode='eval').body):
                return self.record('core_guard_256',ast.parse('len(core)>256',mode='eval').body)
            return self.generic_visit(node)
        def visit_Call(self,node):
            if broad:
                for old,(label,new)in calls.items():
                    if same(node,ast.parse(old,mode='eval').body):return self.record(label,ast.parse(new,mode='eval').body)
            return self.generic_visit(node)
    tree=Adapt().visit(tree);ast.fix_missing_locations(tree)
    expected={'adaptive_angles','bounded_core_count','core_guard_256'}
    if broad:expected|={'broader_core_count_moves','broader_rotation','broader_shear','broader_position'}
    if set(changes)!=expected or any(value!=1 for value in changes.values()):
        raise ValueError('Public mutation structure changed; refusing adaptation: '+repr(changes))
    return tree,changes


def make_mutations(worker,config,source_text=None):
    original=worker.mutations;source=source_text or inspect.getsource(original)
    tree,changes=transform_mutations(source,config)
    namespace=dict(original.__globals__)
    namespace['_targeted_angles']=lambda p:adaptive_angles(p,config['local_angle_fraction'])
    namespace['_targeted_offset']=lambda mode,rng:(int(rng.integers(1,4))if mode==1 else
        -int(rng.integers(2,7))if mode==2 else 0)
    exec(compile(tree,'<targeted-ftmc-mutations>','exec'),namespace)
    return namespace[original.__name__],{'changes':changes,'original_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'adapted_sha256':hashlib.sha256(ast.unparse(tree).encode()).hexdigest(),'core_cap':256,
        'proposal_only':True,'config':config}


def install_policy(worker,keeper,refill_policy,checkpoint,config):
    import ftmc_combined_policy as combined
    original_transform=combined.transform_worker
    def targeted_transform(source):
        tree,changes=original_transform(source)
        matches=[];sampling=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign)and same(node,ast.parse("mode=(stats['batches']+device)%6").body[0]):
                matches.append(node)
            if isinstance(node,ast.Assign)and same(node,ast.parse(
                "weights=np.array([(.08+100*priority.get(k,0.))/math.sqrt(1+visits[k]) for k in keys])").body[0]):
                sampling.append(node)
        if len(matches)!=1:raise ValueError('Expected one public mode assignment')
        if len(sampling)!=1:raise ValueError('Expected one public sampling assignment')
        matches[0].value=ast.parse("_targeted_modes[(stats['batches']+device)%len(_targeted_modes)]",mode='eval').body
        sampling[0].value=ast.parse('_targeted_weights(keys,priority)',mode='eval').body
        changes['targeted_mode_cycle']=1;changes['fixed_high_leverage_sampling']=1;ast.fix_missing_locations(tree)
        return tree,changes
    combined.transform_worker=targeted_transform
    try:audit=combined.install_combined_policy(worker,keeper,refill_policy,checkpoint)
    finally:combined.transform_worker=original_transform
    namespace=worker.worker.__globals__
    depths=np.asarray(config['full_shrink_depths'],dtype=float)
    if depths.shape!=(8,):raise ValueError('Sixteen-replica full batch requires eight doubled depths')
    def sides(f0,filled,replicas):
        if replicas!=16 or filled<1:raise ValueError('Unexpected full-quench batch shape')
        return float(f0)-np.tile(depths,filled*2)
    def weights(keys,priority):
        other=sum(priority[k]for k in keys if k!='8_8_1')
        return np.array([config['n65_mass']if k=='8_8_1'else
            (1-config['n65_mass'])*priority[k]/other for k in keys])
    namespace.update(_targeted_modes=tuple(config['mode_cycle']),_ftmc_gentle_sides=sides,_targeted_weights=weights)
    return {**audit,'mode_cycle':config['mode_cycle'],'full_shrink_depths':depths.tolist()}


def extend_row_capacity(source):
    old='tx[192],ty[192],co[192],si[192]';new='tx[256],ty[256],co[256],si[256]'
    guard='assert m<=192 and w<=31 and h<=31 and 0<=f<1'
    if source.count(old)!=1 or source.count(guard)!=1:raise ValueError('Public row capacity source changed')
    patched=('# Modified by squares_in_squares: row-core storage/checked capacity192 to256; geometry and algorithm unchanged.\n'+
        source.replace(old,new).replace(guard,'assert m<=256 and w<=31 and h<=31 and 0<=f<1'))
    return patched,{'coordinate_trig_arrays':4,'original_core_capacity':192,'new_core_capacity':256,
                    'additional_shared_bytes':4*(256-192)*4,'algorithm_unchanged':True}


def extend_reference_capacity(source):
    old='if len(core) > 192:'
    if source.count(old)!=1:raise ValueError('Measured reference guard changed')
    return source.replace(old,'if len(core) > 256:')
