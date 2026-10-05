"""Fresh cap-constrained radiation/heating QP; no borrowed sign constraints."""
import hashlib,json,math,sys
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_85744_basis import local as prior_local,ROOT,ORDER,FOLDERS
from handoff.audit_tools.solve_x20_83104_constrained import constrained_qp,verify,dot
from handoff.audit_tools.verify_x20_bounded_gram import scalar,rational
from handoff.audit_tools.analyze_x20_latest_gram import cert
from handoff.audit_tools.review_x20_matched_proposal import boundary

# 精确除以128个存储密度会产生大分母。只提高有界文本转换额度，不近似有理数。
sys.set_int_max_str_digits(200000)

BASIS=Path('outputs/hpc/x20-84026-basis-20261005')
AUDIT=Path('handoff/evidence/20261005-x20-current-basis-85744-review.json')
TARGET=Path('handoff/evidence/20261005-x20-85744-joint-candidate.json')
RUNS={84026:'x20-83514-seed-feedback-20261002',82989:'x20-historical-seed-feedback-20261001',82518:'x20-global-window-feedback-20261001'}
OLD=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')

def locate(path):
    path=Path(path)
    if path.is_relative_to(BASIS):return ROOT/'x20-current-basis-85744-received'/path.relative_to(BASIS)
    return prior_local(str(path))

def read(path):return json.loads(Path(path).read_text())
def claim(path,actual):
    b=actual.read_bytes();return dict(path=str(path),size_bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def inputs(resolve=locate):
    a=read(AUDIT);assert a['job_id']==85744 and a['independent_audit'] and a['scheduler_terminal_verified']
    assert a['source_84026_scheduler_terminal_verified'] is False
    d=read(resolve(BASIS/'declaration.json'));p=read(resolve(BASIS/'basis.json'))
    index={c['path']:c for c in a['receipt']['files']};claims=[claim(AUDIT,AUDIT)]
    for name in ('declaration.json','basis.json'):
        c=claim(BASIS/name,resolve(BASIS/name));assert all(c[k]==index[name][k] for k in ('size_bytes','sha256'));claims.append(c)
    assert d['fields']==a['fields'] and d['source_jobs']==[84026,82989,82518]
    old=resolve(OLD);oc=claim(OLD,old)
    assert oc['sha256']=='33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455'
    claims.append(oc)
    with np.load(old,allow_pickle=False) as z:mass=z['cell_mass_g_cm2']
    assert mass.shape==(128,) and np.isfinite(mass).all() and np.all(mass>0)
    known={c['path']:c for c in d['source_claims']};pairs=[];first=None
    for job,n in ORDER:
        root=Path('outputs/hpc')/RUNS[job]/'historical';tp=root/'trial_material.npz'
        tc=claim(tp,resolve(tp));assert tc==known[str(tp)];claims.append(tc)
        with np.load(resolve(tp),allow_pickle=False) as z:t={k:z[k] for k in z.files}
        if first is None:first=t
        assert t.keys()==first.keys() and all(np.array_equal(t[k],first[k]) for k in t)
        dt=float(t['step_duration_s']);rho=t['density_g_cm3']
        assert dt==889.419892762322 and int(t['phase_index'])==1367
        assert rho.shape==(128,) and np.isfinite(rho).all() and np.all(rho>0)
        pair=[]
        for e in ('previous','final'):
            fp=root/f'pair{n:02d}/{e}_feedback.npz';fc=claim(fp,resolve(fp));assert fc==known[str(fp)];claims.append(fc)
            with np.load(resolve(fp),allow_pickle=False) as z:q=z['half_atomic_rate_heating_erg_s_cm3']
            assert q.shape==(128,) and np.isfinite(q).all()
            # 对存储的dt、Q、rho作精确有理诊断运算；不改变正式反馈或能量定义。
            pair.append([F(dt)*F(float(v))/F(float(r)) for v,r in zip(q,rho)])
        pairs.append(pair)
    raw=[[b-a for a,b in zip(*pair)] for pair in pairs]
    basis=[raw[0]]+[[b-a for a,b in zip(raw[0],r)] for r in raw[1:]]
    mw=[F(float(v)) for v in mass];den=sum(mw)
    gh=[[sum(w*a*b for w,a,b in zip(mw,vi,vj))/den for vj in basis] for vi in basis]
    gr=[[sum((F(r['gram'][i][j]) for r in p['slabs']),F(0)) for j in range(4)] for i in range(4)]
    assert gr[0][0]>0 and gh[0][0]>0
    g=[[(gr[i][j]/gr[0][0]+gh[i][j]/gh[0][0])/2 for j in range(4)] for i in range(4)]
    # 四个仿射权重[1-sum(c),*c]的L1上限；不加入旧场的非负约束。
    faces=[([F(s[j+1]-s[0]) for j in range(3)],F(17-s[0])) for s in product((-1,1),repeat=4) if len(set(s))>1]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    return g,gr,gh,faces,claims,p,d

def require_candidate(c,g,gr,gh,faces):
    assert c['source_job']==85744 and c['coefficient_l1_cap']==17 and c['step_safety']==.9
    assert c['exact_kkt_verified'] and c['known_sign_constraints']==0
    for name,mat in [('objective_gram',g),('radiation_gram',gr),('heating_gram',gh)]:
        assert [[rational(v) for v in row] for row in c[name]]==mat
    assert [([rational(v) for v in z['normal']],rational(z['limit'])) for z in c['constraints']]==faces
    r=dict(coefficients=[rational(v) for v in c['coefficients_exact']],multipliers=[rational(v) for v in c['multipliers_exact']],active=c['active'],value=rational(c['objective_value']))
    verify(g,faces,r)
    selected=c['selected_coefficients'];assert selected==[float(F(9,10)*v) for v in r['coefficients']]
    assert all(dot(row,list(map(F,selected)))<=limit for row,limit in faces)
    assert all(c[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))
    assert all(c[k] is False for k in ('candidate_written','baseline_replaced','full_field_nonnegative_verified','true_map_verified'))
    return selected

def run():
    g,gr,gh,faces,claims,p,d=inputs();r=constrained_qp(g,faces);verify(g,faces,r)
    selected=[float(F(9,10)*v) for v in r['coefficients']];x=list(map(F,selected))
    assert all(dot(row,x)<=limit for row,limit in faces)
    ratios={name:math.sqrt(float(scalar(mat,[F(1)]+x)/mat[0][0])) for name,mat in [('radiation',gr),('heating',gh)]}
    spectra=np.concatenate([np.asarray(row['boundary_spectra']) for row in p['slabs']],axis=1)
    anchor=boundary(*spectra[:2]);surfaces={}
    for label,step in [('full',1),('half',.5)]:
        q=spectra[0].copy();pred=spectra[1].copy()
        for j,c in enumerate(selected):
            q+=(step*c)*(spectra[2*j+2]-spectra[0]);pred+=(step*c)*(spectra[2*j+3]-spectra[1])
        surfaces[label]=dict(minima=[float(q.min()),float(pred.min())])
        if min(q.min(),pred.min())>=0:surfaces[label]['metrics']=boundary(q,pred)
    result=dict(source_job=85744,source_claims=claims,fields=d['fields'],objective='equal sum of anchor-normalized radiation and heating squared defects',
        heating_definition='exact rational dt*Q/rho of stored binary64 source values; mass-weighted adjacent differences; erg/g',
        objective_gram=[[cert(v) for v in row] for row in g],radiation_gram=[[cert(v) for v in row] for row in gr],heating_gram=[[cert(v) for v in row] for row in gh],
        constraints=[dict(normal=[cert(v) for v in row],limit=cert(limit)) for row,limit in faces],known_sign_constraints=0,
        coefficients_exact=[cert(v) for v in r['coefficients']],multipliers_exact=[cert(v) for v in r['multipliers']],active=r['active'],objective_value=cert(r['value']),
        faces_examined=r['examined'],exact_kkt_verified=True,coefficient_l1_cap=17,step_safety=.9,selected_coefficients=selected,selected_ratios=ratios,
        boundary_affine_diagnostic=dict(anchor=anchor,candidates=surfaces,full_field_rounding_not_reproduced=True),
        full_field_nonnegative_verified=False,true_map_verified=False,candidate_written=False,baseline_replaced=False,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0)
    require_candidate(result,g,gr,gh,faces)
    with TARGET.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(raw=list(map(float,r['coefficients'])),selected=selected,ratios=ratios,active=r['active'],boundary=result['boundary_affine_diagnostic']),indent=2))

if __name__=='__main__':run()
