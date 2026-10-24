"""Small isolated derivation of the reviewed cold finisher for twelve cases.

The native finishing function changes only its seed expression. Upstream
helpers, numerical options, gates and production files remain untouched.
"""
from __future__ import annotations
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import fq_cold_hop_finish as cold
import fq_restart_hop_finish as terminal

COLD_SHA = '17f0fdf314fbe652f193e76b4101c1e14e688a0632642bd7b180f695959aafb9'
TERMINAL_SHA = 'aab5ea32adc59fe26d1379879f8d4efc53cd1c157b6a02269c7d1dc9e400f543'
SUPPORTED_CASES = frozenset((412,544,742,591,744,641,411,462,978,541,629,341))
SUPPORTED_BATCHES = frozenset((32,64,128))
CUTS = (.0005,.002)
CONTROL_SEED = 9710000


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _replace_once(source,old,new,label):
    if source.count(old) != 1:
        raise ValueError('unexpected_frozen_source_structure:'+label)
    return source.replace(old,new,1)


def _derive():
    if _file_sha(cold.__file__) != COLD_SHA or _file_sha(terminal.__file__) != TERMINAL_SHA:
        raise ValueError('frozen_finishing_helper_changed')
    old_slot = inspect.getsource(terminal._finish_slot)
    seed_old = "str(9710000+DELTAS.index(slot['delta']))"
    seeded_slot = _replace_once(old_slot,seed_old,'str(9710000)','native_seed_only')
    slot_namespace = dict(vars(terminal),NATIVE_SECONDS=60.,CERTIFICATE_SECONDS=8.)
    exec(compile(seeded_slot,'<sustained seed-only terminal clone>','exec'),slot_namespace)
    proxy = SimpleNamespace(**vars(terminal));proxy._finish_slot = slot_namespace['_finish_slot']
    source = Path(cold.__file__).read_text()
    substitutions = [
        ('import fq_restart_hop_finish as original','# original is the isolated seed-only proxy','isolated_terminal_proxy'),
        ('DELTAS = (.002, .008)','DELTAS = (.0005, .002)','two_authorized_cuts'),
        ('if n not in (803,861)','if n not in SUPPORTED_CASES','twelve_case_guard'),
        ('if B != 32','if B not in SUPPORTED_BATCHES','diagnostic_selected_batch_guard'),
        ("sum(r['delta'] == delta for r in design) != 16","sum(r['delta'] == delta for r in design) != B//2",'half_batch_per_cut'),
        ('def finish_case(','def _derived_finish_case(','public_wrapper_binding'),
        ("seed_policy='Same native seed for best/diverse states at a given delta; no adaptive crosscase allocation.'",
         "seed_policy='Native seed9710000 for BOTH cuts and all selected states, matching the single original control; no adaptive allocation.'",'matched_control_seed_metadata'),
        ('source_sha256=_sha(__file__),binary_sha256=original.BINARY_SHA,',
         'source_sha256=_sha(__file__),binary_sha256=original.BINARY_SHA,derivation=DERIVATION,batch_size=B,','derivation_metadata')]
    for old,new,label in substitutions:
        source = _replace_once(source,old,new,label)
    audit = dict(original_cold_helper_sha256=COLD_SHA,original_terminal_helper_sha256=TERMINAL_SHA,
        original_terminal_function_sha256=hashlib.sha256(old_slot.encode()).hexdigest(),
        seeded_terminal_function_sha256=hashlib.sha256(seeded_slot.encode()).hexdigest(),
        terminal_function_changes=1,terminal_change='Only seedexpression→constant9710000; no numerical options or gates changed.',
        selection_loader_changes=[label for _,_,label in substitutions],
        generated_finisher_sha256=hashlib.sha256(source.encode()).hexdigest(),cuts=list(CUTS),
        supported_cases=sorted(SUPPORTED_CASES),supported_batches=sorted(SUPPORTED_BATCHES))
    namespace = dict(vars(cold),original=proxy,DERIVATION=audit,SUPPORTED_CASES=SUPPORTED_CASES,
        SUPPORTED_BATCHES=SUPPORTED_BATCHES,__name__=__name__,__file__=__file__)
    exec(compile(source,'<hash-bound sustained cold-finisher derivation>','exec'),namespace)
    return namespace,audit


_DERIVED,DERIVATION = _derive()
# These names are installed in the actual module so multiprocessing can pickle
# the two worker functions by module/name. All numerical state stays isolated.
for _name in ('histogram_orbit','histogram_distance','select_slots','_configure_worker','_finish_slot','_derived_finish_case'):
    globals()[_name] = _DERIVED[_name]


def finish_case(root:Path,case_config:dict,deadline:float)->dict:
    """Four committed BEST slots; caller supplies the reviewed selected batch."""
    case = dict(case_config);batch = case.get('batch_size')
    if batch not in SUPPORTED_BATCHES:
        raise ValueError('explicit_diagnostic_selected_batch_size_required')
    root = Path(root).resolve()
    design = json.loads((root/'chain-design.json').read_text())
    if len(design) != batch:
        raise ValueError('design_does_not_match_selected_batch_size')
    return _derived_finish_case(root,case,deadline)
