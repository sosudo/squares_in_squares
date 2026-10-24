#!/usr/bin/env python3
"""Keep exact original803/861 starts after certified reference controls lose."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/fq-transfer803861-reference-controls-v2'
OUT=ROOT/'artifacts/fq-cold-transfer-inputs-v1'
PINS={'inputs/restart-inputs.npz':'79ea2bf403b7f6ca82d6662ffe5bf0128ce5a250be4138efc26061e6649b2e1b',
      'case-handoff.json':'e927a399bf81f0e03fcd5372f67a402abe477cda8b517ff2b9c55156d35c0c31',
      'results.json':'149b2a5c444ff752d7e8ac3ea5d27ca71a03d3e67ecd55951756ece7dae99526'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def main():
    for name,digest in PINS.items():assert sha(SOURCE/name)==digest
    proof=json.loads((SOURCE/'inputs/restart-input-proof.json').read_bytes())
    config=json.loads((SOURCE/'inputs/restart-config.json').read_bytes())
    pointer=json.loads((SOURCE/'inputs/portfolio-pointer.json').read_bytes())
    handoff=json.loads((SOURCE/'case-handoff.json').read_bytes())
    assert sha(SOURCE/'inputs/portfolio-pointer.json')==proof['pointer_sha256']
    assert config['inputs_sha256']==proof['inputs_sha256']==PINS['inputs/restart-inputs.npz']
    assert config['baseline']==proof['baseline']==pointer['raw']
    assert sha(pointer['raw']['path'])==pointer['raw']['sha256']
    assert sha(pointer['raw']['official_report'])==proof['official_report_sha256']
    assert sha(pointer['independent_report']['path'])==proof['independent_report_sha256']
    assert set(config['cases'])=={'803','861'}
    with np.load(SOURCE/'inputs/restart-inputs.npz',allow_pickle=False)as z:
        assert set(z.files)==set(proof['arrays'])
        for name in z.files:
            p=z[name];row=proof['arrays'][name]
            assert list(p.shape)==row['shape']and p.dtype.str==row['dtype']and hashlib.sha256(p.tobytes()).hexdigest()==row['sha256']
        for n in ('803','861'):
            row=proof['cases'][n];case=config['cases'][n];control=handoff[n]
            assert not control['strict_gain_vs_current']and control['certificate']['valid']
            assert Decimal(control['control_side'])>Decimal(case['reference_side'])
            assert control['original_side']==case['reference_side']==row['original_case_official']['side']
            assert sha(control['certified_archive'])==control['certified_archive_sha256']
            expected=z[row['original_key']].copy();expected[:,:2]-=np.array(row['translation_subtracted'])
            assert np.array_equal(expected,z[row['reference_key']])and not row['scaling_applied']
            row['reference_side']=case['reference_side']
    proof.update(original_input_proof_sha256=sha(SOURCE/'inputs/restart-input-proof.json'),
        original_configuration_sha256=sha(SOURCE/'inputs/restart-config.json'),reference_control_file_pins=PINS,
        reference_control_handoff=handoff,source_selection='Keep exact original references; both native controls certified but worse.',
        cold_preparation_source_sha256=sha(__file__))
    config.update(seed=105833501,chains=32,temperature=.3,cuts=[.002,.008],amplitudes=[1.,1.5],
        search_seconds=600,cooling_seconds=150,quench_steps=2000,max_packets=3000,max_bytes=6*1024**3,
        finish_native_seconds=60,finish_certificate_seconds=8,finish_workers_per_case=2,finish_slots_per_case=4)
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(SOURCE/'inputs/restart-inputs.npz',OUT/'cold-inputs.npz')
    shutil.copyfile(SOURCE/'inputs/restart-input-proof.json',OUT/'original-input-proof.json')
    shutil.copyfile(SOURCE/'inputs/portfolio-pointer.json',OUT/'portfolio-pointer.json')
    shutil.copyfile(__file__,OUT/'prepare-cold-inputs.py')
    save(OUT/'cold-config.json',config);save(OUT/'cold-input-proof.json',proof)
    print(json.dumps(dict(directory=str(OUT),inputs_sha256=sha(OUT/'cold-inputs.npz'),
        configuration_sha256=sha(OUT/'cold-config.json'),proof_sha256=sha(OUT/'cold-input-proof.json'))))

if __name__=='__main__':main()
