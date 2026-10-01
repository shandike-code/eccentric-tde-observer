"""Independent small-artifact audit; no production field kernel or QP solve."""
import argparse,hashlib,json,tarfile,subprocess
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction
from handoff.audit_tools.solve_x20_83104_constrained import inputs
from operations.x20_83104_constrained_prediction import require_candidate

ROOT=Path('outputs/review-20260925')
MAP={'x20-83080-constrained-basis-20261001':'x20-constrained-basis-83104-received',
     'x20-83063-subnormal-audit-20261001':'x20-subnormal-audit-83075-received',
     'x20-historical-seed-feedback-20261001':'x20-historical-seed-feedback-82989-received',
     'x20-accelerated-feedback-windows-20260930':'x20-feedback-81769-complete-received',
     'x20-window-feedback-20260930':'x20-feedback-82273-complete-received',
     'x20-global-window-feedback-20261001':'x20-global-feedback-82518-complete-received'}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def local(path):
    for run,folder in MAP.items():
        prefix='outputs/hpc/'+run+'/'
        if path.startswith(prefix):
            rel=path[len(prefix):]
            return ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/folder/rel
    return Path(path)


def main(job,commit):
    assert job==83111 and commit=='a51dce6c3ab3c7cc508d7b2846a099f3b95d9ed2'
    base=f'{job}-constrained-prediction-review';receipt=read(ROOT/(base+'.json'));arc=ROOT/(base+'.tar.gz')
    assert digest(arc)==receipt['sha256'] and arc.stat().st_size==receipt['size_bytes']
    out=ROOT/f'x20-constrained-prediction-{job}-received';out.mkdir(exist_ok=False)
    with tarfile.open(arc) as tar:
        ix={v['path']:v for v in receipt['files']};members=tar.getmembers()
        assert len(members)==len(ix)==7
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d,p,s,t=[read(out/(n+'.json')) for n in ('declaration','prediction','summary','scheduler-terminal')]
    assert d['job_id']==str(job) and d['git_commit']==commit and d['source_job']==83104 and d['sign_audit_job']==83075
    assert t['job_id']==job and t['state']=='COMPLETED'
    for token in ('ExitCode=0:0','NumCPUs=4','QOS=qos_stu_default','TimeLimit=01:00:00'):assert token in t['scontrol']
    assert not (out/'stderr.log').read_bytes()
    assert read(out/'status.json')['status']==s['status']=='prediction_rejected_requires_review'
    assert t['summary']==s
    for claim in d['code']:
        data=subprocess.check_output(['git','show',commit+':'+claim['path']])
        assert len(data)==claim['size_bytes'] and hashlib.sha256(data).hexdigest()==claim['sha256']
    for claim in d['source_claims']:
        prefix='outputs/hpc/x20-82989-heating-prediction-20261001/'
        path=(ROOT/'x20-historical-heating-prediction-83063-received'/claim['path'][len(prefix):]
              if claim['path'].startswith(prefix) else local(claim['path']))
        assert path.stat().st_size==claim['size_bytes'] and digest(path)==claim['sha256']
    original=read(ROOT/'x20-constrained-basis-83104-received/declaration.json')
    assert d['fields']==original['fields'] and d['geometry']==original['geometry'] and d['shape']==[9632,32,4096]
    candidate=read('handoff/evidence/20261002-x20-83104-constrained-candidate.json')
    g,gr,gh,faces,tuples,claims=inputs()
    c=require_candidate(candidate,g,gr,gh,faces)
    assert d['global_coefficients']==c==[-5.171447326928601,-2.028552673071399,.9]
    assert d['coefficient_l1_cap']==17 and d['step_safety']==.9 and d['known_constraints']==21 and d['known_source_tuples']==9
    rows=p['slabs'];assert len(rows)==301
    assert [(r['first_group'],r['group_count']) for r in rows]==[(32*i,32) for i in range(301)]
    z=reduce_prediction(rows);assert z['checks']==p['checks']==s['checks'] and z['passed']==p['passed']==s['passed']
    if z['checks']['full_field_nonnegative']:
        np.testing.assert_allclose(z['l2_ratios'],p['fixed_scale_l2_ratios'],rtol=3e-12,atol=0)
        np.testing.assert_allclose(z['linf_ratios'],p['fixed_scale_linf_ratios'],rtol=3e-12,atol=0)
        for i in range(3):
            for k,v in z['boundary'][i].items():np.testing.assert_allclose(v,p['boundary'][i][k],rtol=3e-12,atol=0)
    else:
        assert p['status']=='negative_field_rejected' and p['other_gates_evaluated'] is False
        z['negative_slabs']=[dict(first_group=r['first_group'],minima=r['minima']) for r in rows if min(r['minima'])<0]
    assert [k for k,v in z['checks'].items() if not v]==['full_boundary_l1','full_boundary_bolometric']
    for obj in (d,s):
        assert all(obj[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) and obj['baseline_replaced'] is False and obj['exact_full_domain_sign_certificate'] is False
    assert d['candidate_written'] is False and s['candidate_written'] is False and s['peak_rss_bytes']<6*1024**3
    result=dict(job_id=job,receipt=receipt,independent_slab_reduction=True,source_and_code_verified=True,small_problem_kkt_reverified=True,full_field_recomputed_on_mac=False,
        source_job=d['source_job'],sign_audit_job=d['sign_audit_job'],coefficients=d['global_coefficients'],result=z,summary=s,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    target=Path(f'handoff/evidence/20261002-x20-constrained-prediction-{job}-review.json')
    with target.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(job_id=job,result=z,summary=s),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,required=True);p.add_argument('--commit',required=True);a=p.parse_args();main(a.job,a.commit)
