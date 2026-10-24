"""Separate immutable-input restart scheduler for the larger-region method.

Exactly every fourth visit to each type starts from a frozen copy of its
initial eligible pool, cycling by full geometry SHA. Source selection occurs
inside next_job before its parent metadata is constructed. The existing
solver, geometry method, certification, collection and supervisor stay intact.
"""
import ast
import inspect
from pathlib import Path

import fq_large_region_campaign as large
from fq_variant_campaign import geometry_sha


def freeze_original_pools(pools, keys):
    frozen = {}
    for key in keys:
        entries = []
        for original in pools[key].values():
            entry = dict(original)
            entry['pose'] = original['pose'].copy()
            entry['pose'].setflags(write=False)
            if geometry_sha(entry['pose']) != entry['geometry_sha256']:
                raise ValueError('Initial source geometry does not match its identity')
            entries.append(entry)
        if not entries:
            raise ValueError(f'No immutable eligible input starts for {key}')
        frozen[key] = tuple(sorted(entries, key=lambda entry: entry['geometry_sha256']))
    return frozen


def choose_start(key, visit, best, immutable_pools):
    if visit % 4 == 3:
        pool = immutable_pools[key]
        index = (visit//4) % len(pool)
        selected = pool[index]
        pose = selected['pose'].copy()
        parent = {name: selected[name] for name in
                  ['source_archive', 'source_name', 'geometry_sha256', 'bucket']}
        parent.update(selection='immutable_input', source_pool='immutable_original',
                      source_pool_index=index, source_pool_size=len(pool),
                      source_pool_cycle=(visit//4)//len(pool))
    else:
        pose = best[key].copy()
        parent = {'source_archive': 'campaign_best', 'source_name': key,
                  'geometry_sha256': geometry_sha(pose), 'selection': 'incumbent',
                  'source_pool': 'campaign_best'}
    if geometry_sha(pose) != parent['geometry_sha256']:
        raise ValueError('Selected pose and parent provenance differ')
    return pose, parent


def pool_manifest(immutable_pools):
    return {key: [{name: value[name] for name in
                   ['source_archive', 'source_name', 'geometry_sha256', 'bucket', 'excess']}
                  for value in entries] for key, entries in immutable_pools.items()}


def build_runtime():
    """Apply one checked AST pass to the untouched original runtime body."""
    base = large.local._ordinary_campaign
    tree = ast.parse(inspect.getsource(base))
    function = tree.body[0]
    inserted_pool = inserted_manifest = replaced_selection = 0
    body = []
    for statement in function.body:
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == 'keys'):
            body.extend(ast.parse('immutable_pools = freeze_original_pools(pools, best.keys())').body)
            inserted_pool += 1
        body.append(statement)
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == 'manifest'):
            body.extend(ast.parse("""manifest['restart_policy'] = {
                'immutable_input_fraction': .25,
                'ordering': 'full geometry SHA256, cyclic, independent of campaign output',
                'immutable_inputs_by_key': pool_manifest(immutable_pools),
                'base_runtime_source_sha256': BASE_RUNTIME_SOURCE_SHA256,
                'generated_runtime_source_sha256': GENERATED_RUNTIME_SOURCE_SHA256}
manifest['selection_note'] = 'Every fourth visit to each type uses its immutable initial eligible pool, cycled by geometry SHA. Other visits use the incumbent. Every selected pose is checked against the recorded exact parent SHA before dispatch.'
""").body)
            inserted_manifest += 1
        if isinstance(statement, ast.FunctionDef) and statement.name == 'next_job':
            next_body = []
            for candidate in statement.body:
                if (isinstance(candidate, ast.Assign) and len(candidate.targets) == 1
                        and isinstance(candidate.targets[0], ast.Name) and candidate.targets[0].id == 'pool'):
                    # The dynamic pool remains available for archival diversity
                    # statistics, but cannot control immutable restart ordering.
                    continue
                if (isinstance(candidate, ast.If)
                        and ast.unparse(candidate.test) == 'visit % 4 == 3 and pool'):
                    next_body.extend(ast.parse('pose, parent = choose_start(key, visit, best, immutable_pools)').body)
                    replaced_selection += 1
                else:
                    next_body.append(candidate)
            statement.body = next_body
    function.body = body
    if (inserted_pool, inserted_manifest, replaced_selection) != (1, 1, 1):
        raise ValueError('Original scheduler structure changed; refusing an unchecked adapter')
    ast.fix_missing_locations(tree)
    source = ast.unparse(tree)+'\n'
    namespace = dict(base.__globals__)
    namespace.update(__file__=__file__, freeze_original_pools=freeze_original_pools,
                     choose_start=choose_start, pool_manifest=pool_manifest,
                     BASE_RUNTIME_SOURCE_SHA256=large.campaign.fq.digest(inspect.getsourcefile(base)),
                     GENERATED_RUNTIME_SOURCE_SHA256=large.campaign.fq.hashlib.sha256(source.encode()).hexdigest())
    exec(compile(source, str(Path(__file__).resolve()), 'exec'), namespace)
    return namespace['campaign'], source


def install():
    runtime, source = build_runtime()
    # The existing collector looks up this module global when invoked, and
    # remains inside the original outer supervisor.
    large.local._ordinary_campaign = runtime
    return source


if __name__ == '__main__':
    install()
    large.campaign.main()
