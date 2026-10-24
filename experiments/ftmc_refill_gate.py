"""Optional bounded MILP fallback without treating a row lower bound as upper.

The public whole-row refill is a conservative feasible family. Falling short of
N-4 does not imply that the more general two-dimensional refill cannot reach N.
This adapter removes only that heuristic rejection from an AST copy of the
unchanged Apache-2.0 public worker. Four-attempt, core-residual and timeout gates
remain unchanged, as do final geometry and official-metric admission.
"""
from __future__ import annotations

import ast
import hashlib
import inspect


ROW_GATE = 'row_counts.reshape(-1,2)[b].max()<w*h+d-4'


def make_worker(module, enabled=False, source_text=None):
    original = module.worker
    source = inspect.getsource(original) if source_text is None else source_text
    audit = {'enabled': bool(enabled), 'original_worker_sha256': hashlib.sha256(source.encode()).hexdigest(),
             'modification': 'remove row-deficit rejection only' if enabled else 'none',
             'maximum_milp_attempts_per_batch': 4, 'per_attempt_alarm_seconds': 1.25,
             'core_max_penetration_gate': .01,
             'public_source': 'Lightning v21, Apache-2.0; see vendor/lightning_ftmc/NOTICE'}
    if not enabled:
        return original, audit
    tree = ast.parse(source)
    expected = ast.parse(ROW_GATE, mode='eval').body
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
               and ast.dump(node.test, include_attributes=False) == ast.dump(expected, include_attributes=False)]
    if len(matches) != 1 or len(matches[0].body) != 1 or not isinstance(matches[0].body[0], ast.Continue):
        raise ValueError('Expected exactly one public row-deficit continue gate')
    matches[0].test = ast.Constant(value=False)
    ast.fix_missing_locations(tree)
    # Install all observation/mutation hooks before this call. Snapshotting the
    # current module globals preserves those reviewed hooks in the copied worker.
    namespace = dict(original.__globals__)
    exec(compile(tree, '<explicit-ftmc-row-gate-adaptation>', 'exec'), namespace)
    audit['adapted_worker_sha256'] = hashlib.sha256(ast.unparse(tree).encode()).hexdigest()
    return namespace[original.__name__], audit


def install_refill_gate(module, enabled=False, source_text=None):
    function, audit = make_worker(module, enabled, source_text)
    module.worker = function
    return audit
