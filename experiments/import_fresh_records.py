"""Import a separately pinned fresh certificate screen without changing old pins."""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

import mpmath as mp
from import_records import float_sanity

sys.set_int_max_str_digits(0)


def sha(path):
    with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rational(s):
    x=Fraction(s);return mp.mpf(x.numerator)/x.denominator


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalogue',type=Path,required=True)
    ap.add_argument('--screen',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();root=args.catalogue;source=json.loads((root/'sources.json').read_text())
    commit=source['commit']
    if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Invalid pinned source commit')
    for rec in source['files']:
        if sha(root/rec['path'])!=rec['sha256']:raise ValueError('Pinned catalogue metadata changed')
    upper=json.loads((root/'upper_bounds.json').read_text())['entries']
    finite=json.loads((root/'certified_bounds.json').read_text())['entries']
    witnesses=json.loads((root/'certificates/best/manifest.json').read_text())['witnesses']
    screen_path=args.screen or root/'improvement-screen.json';screen=json.loads(screen_path.read_text())
    jobs=[]
    for case in screen['cases']:
        n=case['n'];f=finite[str(n)];v=upper[str(n)]['verified'];m=witnesses[str(n)]
        if f.get('construction'):raise ValueError('New construction recipe requires explicit implementation')
        path=f['certificate']
        if not re.fullmatch(r'certificates/best/n[1-9][0-9]*\.cert',path):raise ValueError('Unexpected certificate path')
        expected=f['certificate_sha256']
        if m['certificate']!=path or m['certificate_sha256']!=expected:raise ValueError('Certificate metadata disagrees')
        if v.get('sha256')not in (None,expected):raise ValueError('Verified catalogue hash disagrees')
        jobs.append((n,path,expected,case))
    def fetch(job):
        n,relative,expected,case=job;p=root/relative
        url='https://raw.githubusercontent.com/franciscouzo/square-packing/'+commit+'/'+relative
        if not p.exists():
            p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.cert.incoming')
            data=urllib.request.urlopen(url,timeout=45).read()
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Downloaded certificate hash mismatch')
            temp.write_bytes(data);temp.replace(p)
        if sha(p)!=expected:raise ValueError('Frozen certificate hash mismatch')
        return n,p,url,expected,case
    with ThreadPoolExecutor(max_workers=3)as pool:fetched=list(pool.map(fetch,jobs))
    result={};summary=[]
    with mp.workdps(100):
        dilation=1+mp.mpf('1e-40')
        render=lambda v:mp.nstr(v,75,strip_zeros=False,min_fixed=-10000,max_fixed=10000)
        for n,path,url,expected,case in fetched:
            lines=[line.split()for line in path.read_text().splitlines()if line.strip()and not line.lstrip().startswith('#')]
            source_n=int(lines[0][0]);bound=rational(lines[0][1])
            if source_n!=n or len(lines)!=n+1:raise ValueError('Source certificate row count mismatch')
            rows=[(rational(x)*dilation,rational(y)*dilation,2*mp.atan(rational(t)))for x,y,t in lines[1:]]
            xmin=ymin=mp.inf;xmax=ymax=-mp.inf
            for x,y,a in rows:
                h=(abs(mp.cos(a))+abs(mp.sin(a)))/2
                xmin=min(xmin,x-h);xmax=max(xmax,x+h);ymin=min(ymin,y-h);ymax=max(ymax,y+h)
            length=max(xmax-xmin,ymax-ymin)
            if length>bound+mp.mpf('1e-30'):raise ValueError('Certificate pose exceeds its declared bound')
            gap=float_sanity(rows)
            provenance={'repository':'https://github.com/franciscouzo/square-packing','commit':commit,
                'certificate':str(path.relative_to(root)),'certificate_url':url,'certificate_sha256':expected,
                'catalogue_sources':source,'upper_bound_record':upper[str(n)]['verified'],
                'witness_manifest_record':witnesses[str(n)],'finite_record':finite[str(n)],
                'credit':upper[str(n)]['verified'].get('credit'),'working_dps':100,'decimal_digits':75,
                'centre_dilation':'1+1e-40','screen_sha256':sha(screen_path)}
            result[str(n)]={'side':render(length),'squares':[[render(v)for v in row]for row in rows],
                'source':f'Fresh public exact certificate {commit[:12]} n={n}','provenance':provenance,
                'float_minimum_sat_gap':gap,'validation':'Hash-verified source certificate; float sanity passed; independent interval admission required.'}
            gain=(case['current_side']-float(length))/(n**.5)
            summary.append({'n':n,'side':render(length),'estimated_gain_vs_screen':gain,'certificate_sha256':expected})
            print(f'Imported n={n}; estimated gain {gain:.12g}',flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result)+'\n')
    report={'output':str(args.output),'sha256':sha(args.output),'commit':commit,'cases':len(result),
        'estimated_gain_vs_screen':sum(r['estimated_gain_vs_screen']for r in summary),'case_details':summary,
        'source_metadata':source,'screen_sha256':sha(screen_path)}
    args.output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ['case_details','source_metadata']}),flush=True)

if __name__=='__main__':main()
