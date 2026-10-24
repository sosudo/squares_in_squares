#!/usr/bin/env python3
"""Freeze corrected omission labels and a small certified donor handoff.

Reuses strict certificates only when the complete binary64 array hash matches.
It leaves the original bounded search's pinned evidence untouched.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from audit_donor_retention import digest
from extract_broad_active_frontier import geometry_sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    original=args.audit/'inventory';corrected=args.audit/'inventory-corrected'
    validated=args.audit/'validated'
    old=json.loads((original/'report.json').read_text())
    new=json.loads((corrected/'report.json').read_text())
    proof=json.loads((validated/'report.json').read_text())
    assert digest(validated/'checks.json')==proof['checks_sha256']
    assert digest(validated/'all-validated-missing.npz')==proof['all_validated_sha256']
    assert old['descriptor_sha256']==new['descriptor_sha256']
    assert old['catalogue_sha256']==new['catalogue_sha256']
    checks=json.loads((validated/'checks.json').read_text())
    omitted=json.loads((corrected/'omitted-poses.json').read_text())
    missing={(e['geometry_sha256'],e['canonical_type']):e for e in omitted}
    novel=set(new['novel_types']);best={};arrays={};updated=[]
    with np.load(validated/'all-validated-missing.npz',allow_pickle=False) as z:
        for c in checks:
            if not c['certificate']['valid']:continue
            p=z[c['array_key']]
            assert geometry_sha(p)==c['geometry_sha256']
            e=missing[c['geometry_sha256'],c['canonical_type']]
            assert not e['represented']
            item=dict(c,novel_canonical_type=e['novel_canonical_type'],
                original_novel_canonical_type=c['novel_canonical_type'],
                corrected_inventory_report_sha256=digest(corrected/'report.json'))
            updated.append(item);arrays[c['array_key']]=p
            t=c['canonical_type']
            if t in novel and (t not in best or c['excess']<best[t]['excess']):best[t]=item
    assert set(best)==novel and len(novel)==26
    selected={c['array_key']:arrays[c['array_key']] for c in best.values()}
    np.savez_compressed(args.out/'novel-type-donors.npz',**selected)
    winner='0065689b4ce5998d2f3cad14cdbe75018b00df6783ec87869a5c238766d63ae2'
    winning=next(c for c in updated if c['geometry_sha256']==winner)
    selected[winning['array_key']]=arrays[winning['array_key']]
    np.savez_compressed(args.out/'priority-donors.npz',**selected)
    (args.out/'corrected-checks.json').write_text(json.dumps(updated,indent=2)+'\n')
    selected_proofs=[best[t] for t in sorted(best)]+[winning]
    (args.out/'priority-donor-proofs.json').write_text(json.dumps(selected_proofs,indent=2)+'\n')
    result=dict(original_inventory_report_sha256=digest(original/'report.json'),
        corrected_inventory_report_sha256=digest(corrected/'report.json'),
        original_validation_report_sha256=digest(validated/'report.json'),
        original_checks_sha256=proof['checks_sha256'],
        corrected_checks_sha256=digest(args.out/'corrected-checks.json'),
        correction='The initial inventory covered all baseline geometries but omitted baseline-only type labels and retained partners. '
                   'The corrected inventory adds both. The old search inputs and certificates are unchanged.',
        old_current_types=old['current_canonical_types'],current_types=new['current_canonical_types'],
        incorrectly_novel_types=sorted(set(old['novel_types'])-novel),novel_types=sorted(novel),
        strictly_validated_poses=len(updated),reused_exact_geometry_certificates=len(updated),fresh_certificates=0,
        selected_novel_type_poses=len(best),priority_poses=len(selected),
        novel_type_donors_sha256=digest(args.out/'novel-type-donors.npz'),
        priority_donors_sha256=digest(args.out/'priority-donors.npz'),
        priority_donor_proofs_sha256=digest(args.out/'priority-donor-proofs.json'),
        winning_donor_source=winning['source'],source_notices_directory=str(corrected/'source-notices'),
        source_notice_hashes=new['source_notice_hashes'],
        limitations=['Exact floating D4 normalization can conservatively retain aliases.',
                    'Novel means absent from the pinned GPU inputs, not a new mathematical packing record.',
                    'The completed pair search used the original bounded partner sample; added baseline-only partners were not searched.',
                    'Local-soft and bottleneck full archives are deliberately deferred into a separate input partition.'],
        no_submission=True)
    (args.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    (args.out/'source.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:v for k,v in result.items() if k!='source_notice_hashes'}))


if __name__=='__main__':main()
