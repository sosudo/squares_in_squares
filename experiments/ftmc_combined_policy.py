"""Audited single-pass worker adaptation for the productive FTMC campaign.

The public CUDA solver, geometric gates and raw/pandas certification stay intact.
All altered worker expressions are matched structurally and counted before use.
"""
import ast
import hashlib
import inspect

from ftmc_gentle_targets import gentle_fractional_sides
from ftmc_certified_archive import update_search_archive


def _same(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def transform_worker(source):
    tree = ast.parse(source)
    changes = {}

    class Adapt(ast.NodeTransformer):
        def counted(self, label, replacement):
            changes[label] = changes.get(label, 0)+1
            return replacement

        def visit_Assign(self, node):
            patterns = {
                "ff=np.repeat(np.array(filled_fs),R)": ('gentle_full_targets',
                    'ff=_ftmc_gentle_sides(f0,len(filled),R)'),
                "initial=np.load('artifacts/night_seed_gadgets.npz')": ('device_initial_bank',
                    'initial=np.load(_ftmc_seed_path(device))'),
                "wins[key+'__'+signature]=q": ('immutable_certified_retention',
                    '_ftmc_keep(wins,key,signature,q,w,h)'),
            }
            for old, (label, new) in patterns.items():
                if _same(node, ast.parse(old).body[0]):
                    return self.counted(label, ast.parse(new).body[0])
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == 'priority'):
                return [self.counted('initial_archive_diversity',
                    ast.parse('_ftmc_prepare_archive(archive)').body[0]), node]
            return self.generic_visit(node)

        def visit_If(self, node):
            old = ast.parse('if row_counts.reshape(-1,2)[b].max()<w*h+d-4:continue').body[0]
            if _same(node, old):
                return self.counted('measured_refill_eligibility', ast.parse(
                    'if not _ftmc_allow_refill(row_counts.reshape(-1,2)[b].max(),w,h,d,source,loose):continue').body[0])
            old = ast.parse('if signature not in known:archive[key].append(q);archive[key]=sorted(archive[key],key=lambda t:excess(t,w,h))[:6]').body[0]
            if _same(node, old):
                return self.counted('replace_stale_archive_signature', ast.parse(
                    '_ftmc_update_archive(archive,key,q,w,h,signature)').body[0])
            return self.generic_visit(node)

        def visit_Compare(self, node):
            if _same(node, ast.parse('attempts>=4', mode='eval').body):
                return self.counted('one_general_refill_attempt', ast.parse('attempts>=1', mode='eval').body)
            return self.generic_visit(node)

        def visit_Call(self, node):
            patterns = {
                'signal.setitimer(signal.ITIMER_REAL,1.25)': ('half_second_refill_alarm',
                    'signal.setitimer(signal.ITIMER_REAL,.5)'),
                'refill(w+loose,h+loose,cores[b],w*h+d,extra,seconds=.25,soft=.008)':
                    ('bounded_milp_solver_time', 'refill(w+loose,h+loose,cores[b],w*h+d,extra,seconds=.15,soft=.008)'),
                'atom_npz(existing,wins)': ('throttled_bound_checkpoint',
                    '_ftmc_checkpoint(bank,wins,existing)'),
            }
            for old, (label, new) in patterns.items():
                if _same(node, ast.parse(old, mode='eval').body):
                    return self.counted(label, ast.parse(new, mode='eval').body)
            return self.generic_visit(node)

    tree = Adapt().visit(tree)
    expected = {'gentle_full_targets', 'device_initial_bank', 'immutable_certified_retention',
        'initial_archive_diversity', 'measured_refill_eligibility', 'replace_stale_archive_signature',
        'one_general_refill_attempt', 'half_second_refill_alarm', 'bounded_milp_solver_time',
        'throttled_bound_checkpoint'}
    if set(changes) != expected or any(count != 1 for count in changes.values()):
        raise ValueError('Public worker changed; combined adaptation refused: '+repr(changes))
    ast.fix_missing_locations(tree)
    return tree, changes


def install_combined_policy(worker, keeper, refill_policy, checkpoint):
    original = worker.worker
    source = inspect.getsource(original)
    tree, changes = transform_worker(source)

    def update(archive, key, q, w, h, signature):
        return update_search_archive(archive, key, q, w, h, signature,
                                     fingerprint=worker.fingerprint)

    def prepare(archive):
        for key, poses in list(archive.items()):
            w, h, _ = map(int, key.split('_'))
            # The input builder certified every pose; retain the best twelve
            # distinct sampling fingerprints without modifying live incumbents.
            chosen = {}
            for q in poses:
                signature = worker.fingerprint(q)
                if signature not in chosen or worker.excess(q, w, h) < worker.excess(chosen[signature], w, h):
                    chosen[signature] = q
            archive[key] = [q.copy() for q in sorted(chosen.values(),
                key=lambda q: worker.excess(q, w, h))[:12]]

    namespace = original.__globals__
    namespace.update(_ftmc_gentle_sides=gentle_fractional_sides,
        _ftmc_seed_path=lambda device: f'artifacts/device{device}_initial_bank.npz',
        _ftmc_keep=keeper.keep, _ftmc_prepare_archive=prepare,
        _ftmc_allow_refill=refill_policy.allow_refill,
        _ftmc_update_archive=update, _ftmc_checkpoint=checkpoint)
    exec(compile(tree, '<explicit-ftmc-combined-policy>', 'exec'), namespace)
    worker.worker = namespace[original.__name__]
    return {'original_worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'adapted_worker_sha256': hashlib.sha256(ast.unparse(tree).encode()).hexdigest(),
        'changes': changes, 'shared_live_globals': worker.worker.__globals__ is namespace,
        'admission': 'Original finite, penetration, LP, gap, strict/novel and raw/pandas gates unchanged.'}
