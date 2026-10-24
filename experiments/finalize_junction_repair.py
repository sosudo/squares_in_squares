#!/usr/bin/env python3
"""Unite strict full-count junction repairs without admitting invalid starts."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import numpy as np
from fq_active_pilot import digest
from extract_broad_active_frontier import geometry_sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,action='append',required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    arrays={};proofs={};inputs=[];priority={};timeouts=[]
    for root in args.run:
        report=json.loads((root/'report.json').read_text());records=json.loads((root/'records.json').read_text())
        assert digest(root/'valid-repairs.npz')==report['repairs_sha256']
        assert digest(root/'records.json')==report['records_sha256']
        by_hash={r['geometry_sha256']:r for r in records if r['status']=='certified'}
        for r in records:
            if r['status']=='whole-stage-timeout':
                output=Path(r['output_path']);timeouts.append(dict(run=str(root),mode=r['mode'],output=str(output),output_exists=output.is_file()))
        with np.load(root/'valid-repairs.npz') as z:
            for key in z.files:
                p=z[key];g=geometry_sha(p);record=by_hash[g]
                assert p.shape==(498,3) and record['certificate']['valid']
                if 'rigid_return_trace'in record:assert record['rigid_return_trace']['valid']
                arrays['n498__strict_'+g]=p
                proofs.setdefault(g,[]).append(dict(run=str(root),record=record,records_sha256=report['records_sha256']))
                if Decimal(record['side'])<23:priority['22_22_14__junction_'+g]=p
        inputs.append(dict(run=str(root),report_sha256=digest(root/'report.json'),
            manifest_sha256=report['manifest_sha256'],repairs_sha256=report['repairs_sha256'],
            supervisor=json.loads((root/'supervisor.json').read_text()),summary=report))
    np.savez_compressed(args.out/'all-strict-repairs.npz',**arrays)
    np.savez_compressed(args.out/'composition-eligible.npz',**priority)
    (args.out/'proofs.json').write_text(json.dumps(proofs,indent=2)+'\n')
    best=min((Decimal(v[0]['record']['side'])for v in proofs.values()),default=None)
    result=dict(inputs=inputs,strict_unique_geometries=len(arrays),composition_eligible_geometries=len(priority),
        best_side=str(best),whole_case_improvements=0,all_strict_sha256=digest(args.out/'all-strict-repairs.npz'),
        composition_eligible_sha256=digest(args.out/'composition-eligible.npz'),proofs_sha256=digest(args.out/'proofs.json'),
        certificate_reuse='Exact binary64 hashes bind every emitted pose to a completed unit-square raw/default-pandas/interval certificate.',
        fresh_certificates=0,reused_certified_geometries=len(arrays),timeout_outputs=timeouts,
        invalid_starts_excluded=True,no_submission=True)
    assert all(Decimal(x[0]['record']['side'])>=Decimal(str(inputs[0]['summary']['reference_side'])) for x in proofs.values())
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','timeout_outputs')}))


if __name__=='__main__':main()
