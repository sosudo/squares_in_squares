import csv, hashlib, json, math, sys, time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parent))
import official_metric as metric

if __name__=='__main__':
    start=time.perf_counter();path=Path(sys.argv[1] if len(sys.argv)>1 else 'artifacts/submission.csv')
    puzzles=defaultdict(list)
    with path.open(newline='') as f:
        rows=list(csv.DictReader(f))
    assert [int(r['id']) for r in rows]==list(range(len(rows)))
    for r in rows:puzzles[int(r['n'])].append(r)
    with ProcessPoolExecutor(max_workers=8) as ex:
        results=list(ex.map(metric._evaluate_puzzle_worker,sorted(puzzles.items())))
    rejected=[r for r in results if r[3]!='ok']
    total=sum(r[1] for r in results)+sum(metric.infeasible_score(n) for n in range(1,1001) if n not in puzzles)
    record={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'file':str(path),'metric_version':17,'rows':len(rows),'puzzles':len(puzzles),'rejected':rejected,'score':total,'grid_score':sum(metric.infeasible_score(n) for n in range(1,1001)),'elapsed_seconds':time.perf_counter()-start}
    report=Path(sys.argv[2] if len(sys.argv)>2 else 'artifacts/validation.json')
    report.write_text(json.dumps(record,indent=2))
    report.with_name(report.stem+'_puzzle_scores.json').write_text(json.dumps(results))
    print(json.dumps({**record,'rejected':rejected[:3],'rejected_count':len(rejected)},indent=2),flush=True)
    assert not rejected,f'{len(rejected)} rejected puzzles'
