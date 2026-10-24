"""Independent retained-packet and dense-energy audit; never optimize/certify."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from packer_hop_physical_energy import physical_energy

SOURCE_SHA = 'd350aebf10c9bcd07eab3088fd33778cb2e9b55e114eb95bbf0b51a9883f070f'
ORACLE_SHA = '9a5fbbe931559f94dbc7f7080629939fa2d9523113b294f37be5ffba2aa09fd5'
SAMPLE_CHAINS = (4, 14, 20, 30)
POSE_ENERGY = dict(current_before_reset='pre_reset_energy', current_before='current_energy',
    best_before='best_energy_before', proposal_input='input_energy',
    proposal_quenched='proposal_energy', current_after='next_energy', best_after='best_energy_after')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_files(directory):
    receipt_path = directory/'download-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['status']=='complete' and receipt['source_sha256']==SOURCE_SHA
    assert receipt['private_source_verified'] and receipt['version']==1
    result = {}
    for name, record in receipt['files'].items():
        path = directory/'outputs'/name
        assert sha(path)==record['sha256'] and path.stat().st_size==record['bytes']
        result[name] = path
    return result, dict(path=str(receipt_path), sha256=sha(receipt_path), files=len(result))


def audit(run, packet_directories):
    began = time.monotonic()
    aggregate, receipt = verified_files(run)
    files = dict(aggregate); receipts = [receipt]
    for directory in packet_directories:
        added, receipt = verified_files(directory)
        for name, path in added.items():
            if name in files: assert sha(files[name])==sha(path)
            files[name] = path
        receipts.append(receipt)
    assert sha(Path(__file__).with_name('packer_hop_physical_energy.py'))==ORACLE_SHA
    manifest = json.loads(aggregate['job_manifest.json'].read_text())
    assert manifest['files']['experiments/packer_hop_physical_energy.py']==ORACLE_SHA
    energy_checks = []; cases = {}; cache = {}
    def dense(pose, side, recorded, label):
        observed = physical_energy(pose, float(side))
        assert observed['unordered_pairs']==len(pose)*(len(pose)-1)//2
        error = abs(observed['energy']-float(recorded))
        assert error <= 1e-11+1e-8*abs(observed['energy']), (label, error)
        energy_checks.append(dict(label=label, energy=observed['energy'], recorded=float(recorded),
                                  absolute_error=error, n=len(pose)))
    for n in (453, 693):
        prefix = f'case-{n}/'
        load = lambda name: json.loads(aggregate[prefix+name].read_text())
        index = load('raw-index.json'); design = load('chain-design.json')
        events = [json.loads(line) for line in aggregate[prefix+'hop-events.jsonl'].read_text().splitlines()]
        completed = [row for row in index['packets'] if row['status']=='completed']
        ledger = {row['packet']['index']:row for row in events}
        reset = next(row for row in events if row['before_reset']['periodic'])
        boundary = next(row for row in events if row['before_reset']['cooling'] or row['after_reset']['cooling'])
        chosen = [('first_periodic_reset', reset['packet']), ('cooling_boundary', boundary['packet']),
                  ('terminal_completed', completed[-1])]
        by_index = {row['index']:row for row in index['packets']}
        def packet(entry):
            identity = (n, entry['index'])
            if identity in cache: return cache[identity]
            path = files[prefix+entry['path']]
            assert sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes']
            with np.load(path, allow_pickle=False) as z:
                metadata = json.loads(z['metadata_json'].tobytes())
                arrays = {key:z[key].copy() for key in z.files if key!='metadata_json'}
            assert metadata['status']==entry['status'] and metadata['design']==design
            for key, value in arrays.items():
                assert hashlib.sha256(value.tobytes()).hexdigest()==metadata['array_sha256'][key]
            if entry['status']=='completed':
                assert dict(metadata['event'], packet=entry)==ledger[entry['index']]
            cache[identity] = arrays, metadata
            return arrays, metadata
        reset_rows = []
        for label, entry in chosen:
            arrays, metadata = packet(entry); event = metadata['event']
            before = np.array(event['before_reset']['mask'], dtype=bool)
            after = np.array(event['after_reset']['mask'], dtype=bool)
            expected = np.where(before[:,None,None], arrays['best_before'], arrays['current_before_reset'])
            assert np.array_equal(expected, arrays['current_before'])
            previous, _ = packet(by_index[entry['index']-1])
            assert np.array_equal(previous['current_after'], arrays['current_before_reset'])
            assert np.array_equal(previous['best_after'], arrays['best_before'])
            assert np.array_equal(previous['sides'], arrays['sides'])
            choices = np.array(event['best_origin_choice'])
            expected_best = arrays['best_before'].copy()
            for choice, name in ((1,'proposal_input'), (2,'proposal_quenched')):
                expected_best[choices==choice] = arrays[name][choices==choice]
            assert np.array_equal(expected_best, arrays['best_after'])
            accepted = np.array(event['accepted'], dtype=bool)
            mh = np.where(accepted[:,None,None], arrays['proposal_quenched'], arrays['current_before'])
            assert np.array_equal(np.where(after[:,None,None], arrays['best_after'], mh), arrays['current_after'])
            for name, energy_name in POSE_ENERGY.items():
                assert arrays[name].shape==(32,n,3) and arrays[name].dtype==np.float64
                for chain in SAMPLE_CHAINS:
                    dense(arrays[name][chain], arrays['sides'][chain], arrays[energy_name][chain],
                          f'n{n}/packet{entry["index"]}/{name}/chain{chain}')
            reset_rows.append(dict(label=label, packet_index=entry['index'], sha256=entry['sha256'],
                predecessor_index=entry['index']-1, predecessor_current_and_best_exact=True,
                before_reset_chains=np.flatnonzero(before).tolist(), after_reset_chains=np.flatnonzero(after).tolist(),
                all_32_own_best_and_commit_links_exact=True))
        terminal, _ = packet(completed[-1])
        final_path = aggregate[prefix+'final-current-best.npz']
        recovery = load('recovery.json')
        assert sha(final_path)==recovery['recovered_final_archive_sha256']
        with np.load(final_path, allow_pickle=False) as z:
            final = {key:z[key] for key in z.files}
        for key in ('current_after','best_after','sides','next_energy','best_energy_after'):
            assert np.array_equal(final[key], terminal[key])
        for chain in range(32):
            for name, energy_name in (('current_after','next_energy'),('best_after','best_energy_after')):
                dense(final[name][chain],final['sides'][chain],final[energy_name][chain],f'n{n}/final/{name}/chain{chain}')
        pending_checked = []
        for entry in index['packets']:
            if entry['status']!='pending_quench' or prefix+entry['path'] not in files: continue
            arrays, metadata = packet(entry)
            assert entry['index']==completed[-1]['index']+1
            assert np.array_equal(arrays['current_before_reset'], final['current_after'])
            assert np.array_equal(arrays['best_before'], final['best_after'])
            before = np.array(metadata['before_reset']['mask'], dtype=bool)
            assert np.array_equal(arrays['current_before'], np.where(before[:,None,None], arrays['best_before'],arrays['current_before_reset']))
            pending_checked.append(entry['index'])
        cases[str(n)] = dict(selected_packets=reset_rows, final_archive_sha256=sha(final_path),
            final_all_32_current_and_best_exact=True, pending_input_indices_checked=pending_checked,
            pending_inputs_never_counted_as_acceptance=True, final_minimum_physical_energy=float(final['best_energy_after'].min()))
    assert len(energy_checks)==296
    result = dict(passed=True, source_sha256=SOURCE_SHA, audit_source_sha256=sha(__file__),
        independent_oracle_sha256=ORACLE_SHA, receipts=receipts, cases=cases,
        predeclared_sample_chains=list(SAMPLE_CHAINS), dense_energy_evaluations=len(energy_checks),
        maximum_absolute_energy_error=max(row['absolute_error'] for row in energy_checks),
        energy_checks=energy_checks, seconds=time.monotonic()-began,
        new_certificates=0, native_executions=0, cuda_executions=0,
        scope='Exact selected reset/boundary/terminal state links and dense physical diagnostics; no feasibility or gain inferred from low energy.')
    path = run/'independent-packet-energy-review.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,receipt=str(path),sha256=sha(path),energy_checks=len(energy_checks),
                         maximum_absolute_energy_error=result['maximum_absolute_energy_error'],seconds=result['seconds'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--raw',type=Path,action='append',required=True)
    args=parser.parse_args(); audit(args.run,args.raw)
