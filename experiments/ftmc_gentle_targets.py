"""Change only full-packing target sides in an audited copy of public FTMC.

Values are shrink depths: negative depths expand slightly, zero preserves f0,
and positive depths ask for a small improvement. Geometry admission is unchanged.
"""
import ast
import hashlib
import inspect

import numpy as np


SHRINK_DEPTHS = np.array([-.002, -.0005, 0., 1e-5, 5e-5, .0002, .0005, .001])


def gentle_fractional_sides(f0, filled_count, replicas):
    if replicas != 16 or filled_count < 1:
        raise ValueError('Gentle target schedule expects the released 16-replica full batch')
    return float(f0)-np.tile(SHRINK_DEPTHS, filled_count*2)


def install_gentle_targets(worker, enabled=False):
    original = worker.worker
    source = inspect.getsource(original)
    audit = {'enabled': bool(enabled), 'original_worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'modification': 'full-quench ff assignment only' if enabled else 'none',
        'shrink_depths': SHRINK_DEPTHS.tolist() if enabled else None,
        'side_formula': 'f0 minus shrink_depth; negative depths expand' if enabled else 'unchanged public target rule'}
    if not enabled:
        return audit
    tree = ast.parse(source)
    assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'ff']
    expected = ast.parse('ff=np.repeat(np.array(filled_fs),R)').body[0]
    if (len(assignments) != 1 or ast.dump(assignments[0].value, include_attributes=False)
            != ast.dump(expected.value, include_attributes=False)):
        raise ValueError('Public full-packing target expression changed; review before adapting')
    assignments[0].value = ast.parse('_ftmc_gentle_sides(f0,len(filled),R)', mode='eval').body
    ast.fix_missing_locations(tree)
    namespace = original.__globals__
    namespace['_ftmc_gentle_sides'] = gentle_fractional_sides
    exec(compile(tree, '<explicit-ftmc-gentle-targets>', 'exec'), namespace)
    worker.worker = namespace[original.__name__]
    audit['adapted_worker_sha256'] = hashlib.sha256(ast.unparse(tree).encode()).hexdigest()
    return audit
