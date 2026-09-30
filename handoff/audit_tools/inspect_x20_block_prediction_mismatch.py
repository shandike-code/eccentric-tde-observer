"""Interim reverse-triangle lower bound; terminal full-field audit remains required."""
import hashlib
import json
from pathlib import Path


def main():
    root=Path('outputs/review-20260925')
    path=root/'x20-82503-full-interim-blocks.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()=='33f96622562169e69cef53dc6093fc6bba05f5b8f7b8637a91e3b3d99bbe8917'
    data=json.loads(path.read_text())
    audit=json.loads(Path('handoff/evidence/20261001-x20-boundary-prediction-82486-review.json').read_text())
    prediction_path=root/'x20-boundary-prediction-82486-received/prediction.json'
    claim=next(r for r in audit['receipt']['files'] if r['path']=='prediction.json')
    assert hashlib.sha256(prediction_path.read_bytes()).hexdigest()==claim['sha256']
    slabs=json.loads(prediction_path.read_text())['slabs']
    assert len(slabs)==301
    state=data['full_state'];assert len(state['history'])==1 and state['active_map'] is None
    normalizer=audit['linf'][0];assert normalizer>0
    rows=[]
    for i,r in enumerate(data['blocks']):
        assert r['block_index']==i and (r['core_group_start'],r['core_group_stop'])==(128*i,min(128*(i+1),9632))
        assert r['input_state_sha256']==state['history'][0]['input_sha256']
        p=max(s['linf'][1] for s in slabs if s['first_group']//128==i)
        actual=r['maximum_absolute_radiation_change']
        rows.append(dict(block=i,actual_defect_linf=actual,predicted_defect_linf=p,
                         prediction_mismatch_linf_lower_bound=abs(actual-p),
                         lower_bound_over_anchor_linf=abs(actual-p)/normalizer))
    assert len(rows)==76
    result=dict(job_id=82503,interim=True,terminal_audit_complete=False,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                formula='||T(q)-p||_inf >= abs(||T(q)-q||_inf-||p-q||_inf) on each block',
                anchor_linf=normalizer,blocks=rows,full_map=state['history'][0],source_map=data['source_row'],
                strongest_lower_bound_over_anchor_linf=max(r['lower_bound_over_anchor_linf'] for r in rows),
                physical_cause_established=False,new_maps=0,new_material_steps=0)
    target=Path('handoff/evidence/20261001-x20-82503-interim-mismatch.json')
    with target.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(strongest_lower_bound_over_anchor_linf=result['strongest_lower_bound_over_anchor_linf'],top=sorted(rows,key=lambda r:r['lower_bound_over_anchor_linf'],reverse=True)[:6]),indent=2))


if __name__=='__main__':main()
