"""Independent 85778 complete-slab audit, including rejected-candidate scope."""
import hashlib,json,subprocess,tarfile
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction
from handoff.audit_tools.solve_x20_85744_joint import inputs,locate,OLD
from handoff.audit_tools.solve_x20_85744_boundary import verify_candidate

ROOT=Path('outputs/review-20260925')
JOB=85778
COMMIT='741e7eb0634680b82d582d511da84bdb8c122e85'
def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(path):
    if path=='outputs/hpc/common-feedback-bridge-v2-20260923/inputs/physical_old_time_level.npz':return OLD
    return locate(path)

def measured_scope(p,s):
    rows=p['slabs'];assert len(rows)==301
    assert [(r['first_group'],r['group_count']) for r in rows]==[(32*i,32) for i in range(301)]
    z=reduce_prediction(rows)
    assert z['checks']==p['checks']==s['checks'] and z['passed']==p['passed']==s['passed']
    if z['checks']['full_field_nonnegative']:
        assert len(z['checks'])==11
        for key,other in [('l2_ratios','fixed_scale_l2_ratios'),('linf_ratios','fixed_scale_linf_ratios')]:
            np.testing.assert_allclose(z[key],p[other],rtol=3e-12,atol=0)
        for i in range(3):
            for k,v in z['boundary'][i].items():np.testing.assert_allclose(v,p['boundary'][i][k],rtol=3e-12,atol=0)
    else:
        # 非负失败时其它门未求值，不能把缺失门填成通过或选择性忽略负点。
        assert p['status']=='negative_field_rejected' and p['other_gates_evaluated'] is False
        z['negative_slabs']=[dict(first_group=r['first_group'],minima=r['minima']) for r in rows if min(r['minima'])<0]
    return z

def run():
    rec=read(ROOT/f'{JOB}-boundary-prediction-review.json');arc=ROOT/f'{JOB}-boundary-prediction-review.tar.gz'
    assert arc.stat().st_size==rec['size_bytes'] and digest(arc)==rec['sha256']
    out=ROOT/f'x20-boundary-prediction-{JOB}-received';out.mkdir(exist_ok=False)
    ix={r['path']:r for r in rec['files']}
    assert len(ix)==len(rec['files'])==9
    assert set(ix)=={'declaration.json','prediction.json','summary.json','status.json','batch-exit.json','scheduler-terminal.json','execution-terminal.json','stdout.log','stderr.log'}
    with tarfile.open(arc) as tar:
        members=tar.getmembers();assert len(members)==len(ix)==len({m.name for m in members})
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d,p,s,t=[read(out/(n+'.json')) for n in ('declaration','prediction','summary','scheduler-terminal')]
    b=read(out/'batch-exit.json')
    assert d['job_id']==str(JOB) and d['git_commit']==COMMIT and d['source_job']==85744
    assert d['source_feedback_jobs']==[84026,82989,82518] and d['known_sign_constraints']==0
    assert t['job_id']==JOB and t['state']=='COMPLETED' and t['summary']==s
    for token in ('ExitCode=0:0','NumCPUs=4','QOS=qos_stu_default','TimeLimit=01:00:00'):assert token in t['scontrol']
    assert b['job_id']==str(JOB) and b['child_exit_status']==0 and b['scheduler_terminal_verified'] is False
    assert t['batch_exit']==b and read(out/'execution-terminal.json')==t
    assert not (out/'stderr.log').read_bytes()
    for c in d['code']:
        data=subprocess.check_output(['git','show',COMMIT+':'+c['path']]);assert len(data)==c['size_bytes'] and hashlib.sha256(data).hexdigest()==c['sha256'],c['path']
    for c in d['source_claims']:
        path=local(c['path']);assert path.stat().st_size==c['size_bytes'] and digest(path)==c['sha256'],c['path']
    g,gr,gh,cap,_,basis,source=inputs()
    candidate=read('handoff/evidence/20261005-x20-85744-boundary-candidate.json')
    c=verify_candidate(candidate,g,gr,gh,cap,basis)
    assert d['global_coefficients']==c==[-6.846213173701946,-.3537868262980542,.0659556218584672]
    assert d['fields']==candidate['fields']==source['fields'] and d['geometry']==source['geometry'] and d['shape']==[9632,32,4096]
    assert d['coefficient_l1_cap']==17 and d['step_safety']==.9 and d['known_constraints']==len(candidate['constraints'])
    assert d['surface_denominator_branch']==candidate['surface_denominator_branch']
    z=measured_scope(p,s)
    expected='prediction_passed_requires_review' if z['passed'] else 'prediction_rejected_requires_review'
    assert s['status']==read(out/'status.json')['status']==expected
    for x in (d,s):
        assert all(x[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))
        assert all(x[k] is False for k in ('candidate_written','baseline_replaced','strict_error_bound','exact_full_domain_sign_certificate'))
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    # 全部统计即使负点存在也保留；不从未求值门推断通过。
    with localcontext() as ctx:
        ctx.prec=80
        squared=[str(sum((Decimal.from_float(float(r['squared_l2'][i])) for r in p['slabs']),Decimal(0))) for i in range(3)]
    result=dict(job_id=JOB,commit=COMMIT,receipt=rec,scheduler_terminal_verified=True,source_and_code_verified=True,
        code_claims_verified=len(d['code']),source_claims_verified=len(d['source_claims']),independent_slab_reduction=True,
        small_qp_certificate_verified=True,result=z,summary=s,coefficients=c,fields=d['fields'],squared_l2_80digit=squared,
        full_field_recomputed_on_mac=False,strict_error_bound=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    with Path('handoff/evidence/20261006-x20-boundary-prediction-85778-review.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:result[k] for k in ('job_id','code_claims_verified','source_claims_verified','result','summary')},indent=2))

if __name__=='__main__':run()
