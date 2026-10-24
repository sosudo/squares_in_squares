#!/usr/bin/env python3
"""Freeze final night-seed banks with exact derived component gain bounds."""
import argparse
from collections import Counter
from decimal import Decimal,localcontext
import json
from pathlib import Path
import shutil

import numpy as np
from fq_active_pilot import digest
from extract_broad_active_frontier import geometry_sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    current=json.loads((args.run/'current.json').read_text());snapshot=Path(current['snapshot'])
    supervisor=json.loads((args.run/'supervisor.json').read_text())
    manifest=json.loads((args.run/'manifest.json').read_text())
    assert digest(args.run/'manifest.json')==current['manifest_sha256']
    for file,field in [('donors.npz','donors_sha256'),('best_bank.npz','best_bank_sha256'),('records.json','records_sha256')]:
        assert digest(snapshot/file)==current[field]
        shutil.copyfile(snapshot/file,args.out/file)
    assert digest(args.run/'inputs/reference-proofs.json')==manifest['reference_proofs_sha256']
    records=json.loads((args.out/'records.json').read_text())
    refs=json.loads((args.run/'inputs/reference-proofs.json').read_text())
    proof_by_hash={r['canonical_geometry_sha256']:r for r in refs}
    for record in records:
        if record['status']!='certified':continue
        assert record['certificate']['valid']
        if record['mode']=='soft15':assert record['rigid_return_trace']['valid']
        proof_by_hash[record['geometry_sha256']]=record
    poses=0
    with np.load(args.out/'donors.npz',allow_pickle=False) as z:
        for key in z.files:
            p=z[key];typ=key.split('__')[0];w,h,d=map(int,typ.split('_'))
            assert p.shape==(w*h+d,3)
            record=proof_by_hash[geometry_sha(p)]
            assert record['key']==typ and record['certificate']['valid']
            assert Decimal(record['excess_interval']['upper'])<1
            poses+=1
    rows=[];by_type={r['key']:r for r in refs}
    with np.load(args.out/'best_bank.npz',allow_pickle=False) as z,localcontext() as context:
        context.prec=100
        for key in z.files:
            p=z[key];record=proof_by_hash[geometry_sha(p)];before=by_type[key]['excess_interval'];after=record['excess_interval']
            rows.append(dict(key=key,geometry_sha256=geometry_sha(p),reference_excess_interval=before,
                final_excess_interval=after,gain_lower=str(Decimal(before['lower'])-Decimal(after['upper'])),
                final_mode=record.get('mode','historical-reference')))
    material=[r for r in rows if Decimal(r['gain_lower'])>Decimal('1e-8')]
    result=dict(supervisor=supervisor,manifest_sha256=digest(args.run/'manifest.json'),
        source_snapshot=str(snapshot),snapshot_report_sha256=digest(snapshot/'report.json'),
        trials=len(records),status_counts=dict(Counter(r['status'] for r in records)),
        strict_geometry_count=poses,complete_type_count=len(rows),materially_improved_type_count=len(material),
        exact_gain_rows=rows,donors_sha256=digest(args.out/'donors.npz'),best_bank_sha256=digest(args.out/'best_bank.npz'),
        records_sha256=digest(args.out/'records.json'),reference_proofs_sha256=manifest['reference_proofs_sha256'],
        certificate_reuse='All emitted binary64 arrays match their previously completed strict certificates by exact SHA256.',
        fresh_geometry_certificates=0,reused_geometry_certificates=poses,
        precision_note='Derived gains are exact decimal subtraction at precision100; original online display used precision28.',
        scope='Component excess gains only. Full composition must independently establish any competition score gain.',no_submission=True)
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k!='exact_gain_rows'}))
    print(json.dumps(sorted(material,key=lambda x:-float(x['gain_lower']))[:8]))


if __name__=='__main__':main()
