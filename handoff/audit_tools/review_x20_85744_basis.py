"""Independent 85744 source binding and 80-digit small-statistic reduction."""
import hashlib,json,subprocess,tarfile
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_window_basis import reduce_rows,minimum
from handoff.audit_tools.review_x20_matched_proposal import boundary
from handoff.audit_tools.review_x20_83080_quarter import local as old_local,ROOT,read,digest

JOB=85744
COMMIT='74b1cccf119d1215a271c7bc4a125d05cc6858f6'
ORDER=((84026,16),(84026,8),(82989,16),(82518,16))
FOLDERS={84026:'x20-83514-feedback-84026-received',82989:'x20-historical-seed-feedback-82989-received',82518:'x20-global-feedback-82518-complete-received'}

def local(path):
    for run,folder in [('x20-83514-seed-feedback-20261002',FOLDERS[84026]),('x20-83111-half-prediction-20261002','x20-half-prediction-83131-received'),('x20-83131-true-validation-20261002','x20-83131-true-83514-received')]:
        prefix='outputs/hpc/'+run+'/'
        if path.startswith(prefix):
            rel=path[len(prefix):]
            return ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/folder/rel
    return old_local(path)

def terminal_check(t,b,s):
    assert t['job_id']==JOB and t['state']=='COMPLETED' and t['summary']==s
    for token in ('ExitCode=0:0','NumCPUs=4','QOS=qos_stu_default','TimeLimit=01:00:00'):
        assert token in t['scontrol']
    assert b['job_id']==str(JOB) and b['child_exit_status']==0 and b['scheduler_terminal_verified'] is False
    assert t['batch_exit']==b

def source_fields():
    fields=[]
    for job,n in ORDER:
        m=read(ROOT/FOLDERS[job]/f'historical/endpoints-map{n:02d}/manifest.json')
        r0,r1=m['history_rows'];e=m['endpoints']
        assert [r0['iteration'],r1['iteration']]==[n-1,n]
        assert r0['input_sha256']==e['previous']['sha256']
        assert r0['output_sha256']==r1['input_sha256']==e['final']['sha256']
        fields.extend(e[k] for k in ('previous','final'))
    return fields

def run():
    receipt=read(ROOT/f'{JOB}-current-basis-review.json');arc=ROOT/f'{JOB}-current-basis-review.tar.gz'
    assert arc.stat().st_size==receipt['size_bytes'] and digest(arc)==receipt['sha256']
    out=ROOT/f'x20-current-basis-{JOB}-received';out.mkdir(exist_ok=False)
    ix={r['path']:r for r in receipt['files']}
    assert len(ix)==len(receipt['files'])==9
    assert set(ix)=={'declaration.json','basis.json','summary.json','status.json','batch-exit.json','scheduler-terminal.json','execution-terminal.json','stdout.log','stderr.log'}
    with tarfile.open(arc) as tar:
        members=tar.getmembers();assert len(members)==len(ix)
        assert len({m.name for m in members})==len(ix)
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d,p,s,t=[read(out/(n+'.json')) for n in ('declaration','basis','summary','scheduler-terminal')]
    assert d['job_id']==str(JOB) and d['git_commit']==COMMIT
    assert d['source_job']==84026 and d['source_jobs']==[84026,82989,82518] and d['source_scheduler_terminal_verified'] is False
    terminal_check(t,read(out/'batch-exit.json'),s)
    assert read(out/'execution-terminal.json')==t and not (out/'stderr.log').read_bytes()
    for c in d['code']:
        b=subprocess.check_output(['git','show',COMMIT+':'+c['path']]);assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
    for c in d['source_claims']:
        f=local(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],c['path']
    assert d['fields']==source_fields() and d['shape']==[9632,32,4096]
    assert d['field_order']==[f'{j}H{n}_{e}' for j,n in ORDER for e in ('previous','final')]
    assert d['basis_order']==['r_84026H16','r_84026H8-r_84026H16','r_82989H16-r_84026H16','r_82518H16-r_84026H16']
    assert all(c['size_bytes']==10099884032 for c in d['fields']) and p['all_eight_sha256_verified']
    # 几何来源必须穿过84026归档声明和83514已审声明，不能只检查孤立的SHA。
    vd=read(ROOT/'x20-83131-true-83514-received/declaration.json')
    sd=read(ROOT/FOLDERS[84026]/'declaration.json')
    vp='outputs/hpc/x20-83131-true-validation-20261002/declaration.json'
    assert next(c for c in d['source_claims'] if c['path']==vp) in sd['claims']
    gp='outputs/hpc/x20-83111-half-prediction-20261002/declaration.json'
    assert next(c for c in d['source_claims'] if c['path']==gp) in vd['claims']
    assert d['geometry'] in vd['claims'] and d['geometry']==read(local(gp))['geometry']
    g,f=reduce_rows(p['slabs'])
    for other in (p['gram'],s['gram']):np.testing.assert_allclose(g,other,rtol=3e-12,atol=0)
    peaks=[max(r['basis_linf'][i] for r in p['slabs']) for i in range(4)]
    mins=[min(r['field_minima'][i] for r in p['slabs']) for i in range(8)]
    assert peaks==p['basis_linf'] and mins==p['field_minima'] and f.shape==(8,9632) and s['slabs']==301
    with localcontext() as ctx:
        ctx.prec=80;D=lambda x:Decimal.from_float(float(x))
        wide=[[str(sum((D(r['gram'][i][j]) for r in p['slabs']),Decimal(0))) for j in range(4)] for i in range(4)]
        flux_totals=[str(sum((D(v) for v in row),Decimal(0))) for row in f]
    for z in (d,s):
        assert all(z[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) and not z['baseline_replaced'] and not z['strict_error_bound'] and not z['candidate_written']
    assert not p['candidate_written'] and d['maximum_statistic_scans']==1 and d['longdouble_mantissa_bits']>=52
    assert s['status']==read(out/'status.json')['status']=='basis_complete_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    try:diagnostic=minimum(g)
    except ValueError as exc:diagnostic=dict(matrix_failure=str(exc),directions_removed=False,regularization_applied=False)
    result=dict(job_id=JOB,commit=COMMIT,receipt=receipt,independent_audit=True,scheduler_terminal_verified=True,
        source_84026_scheduler_terminal_verified=False,code_claims_verified=len(d['code']),source_claims_verified=len(d['source_claims']),
        gram=g,gram_80digit=wide,unconstrained_diagnostic=diagnostic,boundary_flux_totals_80digit=flux_totals,
        boundary_metrics=[boundary(f[i],f[i+1]) for i in range(0,8,2)],fields=d['fields'],basis_linf=peaks,field_minima=mins,
        slabs=301,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
        strict_rounding_error_bound=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    with Path('handoff/evidence/20261005-x20-current-basis-85744-review.json').open('x') as o:json.dump(result,o,indent=2,allow_nan=False);o.write('\n')
    print(json.dumps({k:result[k] for k in ('job_id','unconstrained_diagnostic','code_claims_verified','source_claims_verified')},indent=2))

if __name__=='__main__':run()
