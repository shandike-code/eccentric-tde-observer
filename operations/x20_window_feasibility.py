"""Bounded small-data necessary-condition check for audited 82166 basis."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_expanded_feasibility as core

PAIRS=((0,3),(4,5),(6,7))


def convert(rows):
    f=np.concatenate([np.asarray(r['boundary_spectra'],float) for r in rows],axis=1)
    if f.shape!=(8,9632):raise ValueError('complete eight spectra required')
    # core.system baseline is rows 1,2; remaining pairs keep H16,A8,H8 direction order.
    return f[[2,0,1,3,4,5,6,7]]


def execute(out):
    out.relative_to(core.ROOT/'outputs');out.mkdir(exist_ok=False);start=time.monotonic()
    audit=core.ROOT/'handoff/evidence/20260930-x20-82166-review.json'
    a=json.loads(audit.read_text())
    if not a['independent_audit'] or a['job_id']!=82166:raise ValueError('independently audited 82166 required')
    source=core.ROOT/'outputs/review-20260925/x20-basis-82166-received'
    receipt=a['receipt'];arc=core.ROOT/receipt['path']
    if core.claim(arc)['sha256']!=receipt['sha256'] or arc.stat().st_size!=receipt['size_bytes']:raise ValueError('archive changed')
    claims=[core.claim(audit),core.claim(arc)]
    for c in receipt['files']:
        p=source/c['path'];claim=core.claim(p)
        if (claim['size_bytes'],claim['sha256'])!=(c['size_bytes'],c['sha256']):raise ValueError('artifact changed')
        claims.append(claim)
    code=[core.claim(core.ROOT/p) for p in ('operations/x20_window_feasibility.py','operations/x20_expanded_feasibility.py',
            'tests/test_x20_window_feasibility.py','handoff/protocols/x20-window-feasibility-v1.md')]
    raw=json.loads((source/'basis.json').read_text());g=np.asarray(a['gram']);f=convert(raw['slabs'])
    if not np.array_equal(g,raw['gram']):raise ValueError('audited Gram differs')
    core.write(out/'declaration.json',dict(source_job=82166,source_claims=claims,code=code,
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            tracked_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
            pairs=PAIRS,dimension=3,raw_weight_l1_cap=17,full_fraction=.9,half_fraction=.45,maximum_iterations=64,
            new_maps=0,new_feedback_pairs=0,new_material_steps=0,large_fields_read=0))
    result=core.solve(g,f,PAIRS,maximum_iterations=64)
    for c in claims+code:
        if core.claim(core.ROOT/c['path'])!=c:raise RuntimeError('source/code changed')
    result.update(source_job=82166,wall_s=time.monotonic()-start,new_maps=0,new_feedback_pairs=0,new_material_steps=0,
                  large_fields_read=0,baseline_replaced=False,candidate_written=False)
    core.write(out/'result.json',result)
    print(json.dumps(dict(status=result['status'],iterations=len(result['trace']),last=result['trace'][-1]['certificate'],point=result['trace'][-1]['point'],wall_s=result['wall_s']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();execute((core.ROOT/a.out).resolve())
