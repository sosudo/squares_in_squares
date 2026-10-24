"""Cap the common negative-control sampling budget in an audited runtime copy."""
import ast
import hashlib
import inspect

import numpy as np


def cap_weights(weights, keys, controls, cap=.1):
    weights = np.asarray(weights, dtype=float)
    if not np.isfinite(weights).all() or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError('Invalid FTMC sampling weights')
    result = weights/weights.sum()
    mask = np.array([key in controls for key in keys])
    mass = result[mask].sum()
    if mass > cap and (~mask).any():
        result[mask] *= cap/mass
        result[~mask] *= (1-cap)/result[~mask].sum()
    return result


def install_sampling_cap(worker, controls, cap=.1):
    if not 0 < cap < 1:
        raise ValueError('Control group cap must lie strictly between zero and one')
    original = worker.worker
    source = inspect.getsource(original)
    tree = ast.parse(source)
    expected = ast.parse('weights/=weights.sum()').body[0]
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.AugAssign)
               and ast.dump(node, include_attributes=False) == ast.dump(expected, include_attributes=False)]
    if len(matches) != 1:
        raise ValueError('Public sampler changed; review the runtime cap')
    target = matches[0]

    class Replace(ast.NodeTransformer):
        def visit_AugAssign(self, node):
            if node is target:
                return ast.copy_location(ast.parse('weights=_ftmc_capped_weights(weights,keys)').body[0], node)
            return node
    tree = Replace().visit(tree)
    ast.fix_missing_locations(tree)
    controls = frozenset(controls)
    # Keep the module globals shared: the capture and diagnostic observers must
    # remain visible to the runtime copy of the worker body.
    namespace = original.__globals__
    namespace['_ftmc_capped_weights'] = lambda weights, keys: cap_weights(weights, keys, controls, cap)
    exec(compile(tree, '<explicit-ftmc-control-cap>', 'exec'), namespace)
    worker.worker = namespace[original.__name__]
    return {'original_worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'adapted_worker_sha256': hashlib.sha256(ast.unparse(tree).encode()).hexdigest(),
            'control_keys': sorted(controls), 'maximum_sampling_mass': cap,
            'modification': 'common control-group probability cap only'}
