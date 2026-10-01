"""Independent current basis reduction and comparison to actual quarter arithmetic."""
import hashlib,json,subprocess,tarfile
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_window_basis import reduce_rows,minimum
from handoff.audit_tools.review_x20_matched_proposal import boundary
from handoff.audit_tools.review_x20_83080_quarter import local,ROOT,read,digest


def run():
    job=83104;commit='79b2118c6501708d0d6efcfbef7e7b8cfcaec4e0'
    receipt=read(ROOT/f'{job}-constrained-basis-review.json');arc=ROOT/f'{job}-constrained-basis-review.tar.gz'
    assert arc.stat().st_size==receipt['size_bytes'] and digest(arc)==receipt['sha256']
    out=ROOT/f'x20-constrained-basis-{job}-received';out.mkdir(exist_ok=False)
    ix={r['path']:r for r in receipt['files']}
    assert set(ix)=={'declaration.json','basis.json','summary.json','status.json','scheduler-terminal.json','stdout.log','stderr.log'}
    with tarfile.open(arc) as tar:
        members=tar.getmembers();assert len(members)==len(ix)
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d,p,s,t=[read(out/(n+'.json')) for n in ('declaration','basis','summary','scheduler-terminal')]
    assert d['job_id']==str(job) and d['git_commit']==commit and d['source_job']==83080 and d['original_direction_job']==83063 and d['sign_audit_job']==83075
    assert t['job_id']==job and t['state']=='COMPLETED' and t['summary']==s
    for token in ('ExitCode=0:0','NumCPUs=4','QOS=qos_stu_default','TimeLimit=01:00:00'):assert token in t['scontrol']
    assert not (out/'stderr.log').read_bytes()
    for c in d['code']:
        b=subprocess.check_output(['git','show',commit+':'+c['path']]);assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
    for c in d['source_claims']:
        mapped=None
        for prefix,folder in [('x20-83063-quarter-prediction-20261001','x20-quarter-prediction-83080-received'),('x20-82989-heating-prediction-20261001','x20-historical-heating-prediction-83063-received')]:
            key='outputs/hpc/'+prefix+'/'
            if c['path'].startswith(key):mapped=ROOT/folder/c['path'][len(key):]
        f=mapped or local(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],c['path']
    od=read(ROOT/'x20-quarter-prediction-83080-received/declaration.json')
    assert d['fields']==od['fields'] and d['geometry']==od['geometry'] and d['shape']==[9632,32,4096]
    assert d['field_order']==['82989H16_previous','82989H16_final','82989H8_previous','82989H8_final','82518H16_previous','82518H16_final','82273H16_previous','82273H16_final']
    assert d['basis_order']==['r_82989H16','r_82989H8-r_82989H16','r_82518H16-r_82989H16','r_82273H16-r_82989H16']
    assert all(c['size_bytes']==10099884032 for c in d['fields']) and p['all_eight_sha256_verified']
    g,f=reduce_rows(p['slabs'])
    for other in (p['gram'],s['gram']):np.testing.assert_allclose(g,other,rtol=3e-12,atol=0)
    peaks=[max(r['basis_linf'][i] for r in p['slabs']) for i in range(4)];mins=[min(r['field_minima'][i] for r in p['slabs']) for i in range(8)]
    assert peaks==p['basis_linf'] and mins==p['field_minima'] and f.shape==(8,9632) and s['slabs']==301
    # 80位逐片归并及二次型；不是将不同浮点表达式强行视作逐位相等。
    actual=read(ROOT/'x20-quarter-prediction-83080-received/prediction.json');comparison=[]
    with localcontext() as ctx:
        ctx.prec=80;D=lambda x:Decimal.from_float(float(x))
        wide=[[sum((D(r['gram'][i][j]) for r in p['slabs']),Decimal(0)) for j in range(4)] for i in range(4)]
        for step,column in [(0,0),(.125,2),(.25,1)]:
            w=[Decimal(1)]+[D(step)*D(v) for v in od['original_coefficients']]
            predicted=sum(w[i]*wide[i][j]*w[j] for i in range(4) for j in range(4))
            measured=sum((D(r['squared_l2'][column]) for r in actual['slabs']),Decimal(0))
            comparison.append(dict(step=step,gram_squared=str(predicted),measured_squared=str(measured),relative_difference=float((predicted-measured)/measured)))
        flux_totals=[str(sum((D(v) for v in row),Decimal(0))) for row in f]
    for z in (d,s):
        assert all(z[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) and not z['baseline_replaced'] and not z['strict_error_bound'] and not z['candidate_written']
    assert not p['candidate_written'] and d['maximum_statistic_scans']==1 and d['longdouble_mantissa_bits']>=52
    assert s['status']==read(out/'status.json')['status']=='basis_complete_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    result=dict(job_id=job,commit=commit,receipt=receipt,independent_audit=True,code_claims_verified=len(d['code']),source_claims_verified=len(d['source_claims']),
        gram=g,unconstrained_diagnostic=minimum(g),comparison_to_83080=comparison,boundary_flux_totals_80digit=flux_totals,
        boundary_metrics=[boundary(f[i],f[i+1]) for i in range(0,8,2)],fields=d['fields'],basis_linf=peaks,field_minima=mins,
        slabs=301,peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
        strict_rounding_error_bound=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    with Path('handoff/evidence/20261002-x20-constrained-basis-83104-review.json').open('x') as o:json.dump(result,o,indent=2,allow_nan=False);o.write('\n')
    print(json.dumps({k:result[k] for k in ('job_id','unconstrained_diagnostic','comparison_to_83080','code_claims_verified')},indent=2))

if __name__=='__main__':run()
