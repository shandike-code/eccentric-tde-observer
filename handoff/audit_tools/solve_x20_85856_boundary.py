"""Exact joint QP with original nonincrease conditions on affine surface spectra."""
import json,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from handoff.audit_tools import solve_x20_85856_joint as joint
from handoff.audit_tools.solve_x20_83104_constrained import constrained_qp,verify,dot
from handoff.audit_tools.verify_x20_bounded_gram import scalar,rational
from handoff.audit_tools.analyze_x20_latest_gram import cert

TARGET=Path('handoff/evidence/20261006-x20-85856-boundary-candidate.json')

def surface_model(p):
    f=np.concatenate([np.asarray(r['boundary_spectra']) for r in p['slabs']],axis=1)
    assert f.shape[0]==8 and np.isfinite(f).all() and np.all(f>=0)
    v=[[F(float(z)) for z in row] for row in f]
    q=[[v[0][k]]+[v[2*j+2][k]-v[0][k] for j in range(3)] for k in range(f.shape[1])]
    pred=[[v[1][k]]+[v[2*j+3][k]-v[1][k] for j in range(3)] for k in range(f.shape[1])]
    delta=[[b-a for a,b in zip(x,y)] for x,y in zip(q,pred)]
    totals=[[sum(row[j] for row in x) for j in range(4)] for x in (q,pred)]
    dominant=int(totals[1][0]>totals[0][0]);den=totals[dominant]
    assert den[0]>0
    bol=[sum(row[j] for row in delta) for j in range(4)]
    l1=sum(abs(row[0]) for row in delta)/den[0];beta=abs(bol[0])/den[0]
    # 固定锚点最大总通量所在分支，约束该通量继续不小于另一端；不替换原归一化。
    other=totals[1-dominant];branch=[b-a for a,b in zip(den,other)]
    faces=[(branch[1:],-branch[0])]
    for sign in (-1,1):
        row=[sign*b-beta*d for b,d in zip(bol,den)]
        faces.append((row[1:],-row[0]))
    return dict(q=q,pred=pred,delta=delta,den=den,dominant=dominant,l1=l1,bolometric=beta,faces=faces)

def surface_check(model,x):
    w=[F(1)]+x;den=dot(model['den'],w)
    if den<=0:raise ValueError('nonpositive surface denominator')
    values=[dot(row,w) for row in model['delta']]
    l1=sum(map(abs,values));bol=abs(sum(values))
    return dict(l1=l1/den,bolometric=bol/den,l1_pass=l1<=model['l1']*den,
        bolometric_pass=bol<=model['bolometric']*den,
        spectra_nonnegative=all(dot(row,w)>=0 for row in model['q']+model['pred']),
        branch_pass=all(dot(row,x)<=limit for row,limit in model['faces']),values=values)

def fit(g,cap,model,max_cuts=24):
    faces=cap+model['faces'];cuts=[]
    for iteration in range(max_cuts+1):
        r=constrained_qp(g,faces);verify(g,faces,r);z=surface_check(model,r['coefficients'])
        if z['l1_pass']:
            if not z['spectra_nonnegative']:raise ValueError('surface spectrum negative; no candidate')
            assert z['bolometric_pass'] and z['branch_pass']
            return r,faces,cuts
        if iteration==max_cuts:raise ValueError('surface cutting-plane budget exhausted')
        signs=[F((v>0)-(v<0)) for v in z['values']]
        # L1球的精确支持平面；每片保留所有频组，不按亮度删点。
        row=[sum(s*v[j] for s,v in zip(signs,model['delta']))-model['l1']*model['den'][j] for j in range(4)]
        face=(row[1:],-row[0]);assert face not in faces
        cuts.append(dict(normal=[cert(v) for v in face[0]],limit=cert(face[1]),violating_coefficients=[cert(v) for v in r['coefficients']]))
        faces.append(face)
    raise AssertionError('unreachable')

def verify_candidate(c,g,gr,gh,cap,p):
    assert c['source_job']==85856 and c['step_safety']==.9 and c['coefficient_l1_cap']==17 and c['known_sign_constraints']==0
    for name,mat in [('objective_gram',g),('radiation_gram',gr),('heating_gram',gh)]:
        assert [[rational(v) for v in row] for row in c[name]]==mat
    model=surface_model(p);faces=cap+model['faces']
    assert c['surface_denominator_branch']==model['dominant'] and len(c['cuts'])<=24
    for cut in c['cuts']:
        x=[rational(v) for v in cut['violating_coefficients']];z=surface_check(model,x);assert not z['l1_pass']
        signs=[F((v>0)-(v<0)) for v in z['values']]
        row=[sum(s*v[j] for s,v in zip(signs,model['delta']))-model['l1']*model['den'][j] for j in range(4)]
        face=(row[1:],-row[0]);assert face==([rational(v) for v in cut['normal']],rational(cut['limit']))
        faces.append(face)
    assert faces==[([rational(v) for v in z['normal']],rational(z['limit'])) for z in c['constraints']]
    r=dict(coefficients=[rational(v) for v in c['coefficients_exact']],multipliers=[rational(v) for v in c['multipliers_exact']],active=c['active'],value=rational(c['objective_value']))
    verify(g,faces,r)
    assert all(surface_check(model,r['coefficients'])[k] for k in ('l1_pass','bolometric_pass','spectra_nonnegative','branch_pass'))
    selected=c['selected_coefficients'];assert selected==[float(F(9,10)*v) for v in r['coefficients']]
    for step in (F(1),F(1,2)):
        x=[step*F(v) for v in selected]
        assert all(dot(row,x)<=limit for row,limit in cap)
        z=surface_check(model,x);assert all(z[k] for k in ('l1_pass','bolometric_pass','spectra_nonnegative','branch_pass'))
    assert c['exact_kkt_verified'] and all(c[k]==0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))
    assert all(c[k] is False for k in ('candidate_written','baseline_replaced','full_field_nonnegative_verified','true_map_verified'))
    return selected

def run():
    g,gr,gh,cap,claims,p,d=joint.inputs();model=surface_model(p);r,faces,cuts=fit(g,cap,model)
    selected=[float(F(9,10)*v) for v in r['coefficients']];diagnostics={}
    for label,step in [('full',F(1)),('half',F(1,2))]:
        x=[step*F(v) for v in selected];z=surface_check(model,x)
        diagnostics[label]=dict(ratios={name:math.sqrt(float(scalar(mat,[F(1)]+x)/mat[0][0])) for name,mat in [('radiation',gr),('heating',gh)]},
            boundary_l1=float(z['l1']),boundary_bolometric=float(z['bolometric']))
    c=dict(source_job=85856,source_claims=claims,fields=d['fields'],objective='equal sum of anchor-normalized radiation and heating squared defects',
        heating_definition='exact rational dt*Q/rho of stored binary64 values; mass weighting; erg/g',
        objective_gram=[[cert(v) for v in row] for row in g],radiation_gram=[[cert(v) for v in row] for row in gr],heating_gram=[[cert(v) for v in row] for row in gh],
        constraints=[dict(normal=[cert(v) for v in row],limit=cert(limit)) for row,limit in faces],known_sign_constraints=0,cuts=cuts,
        surface_denominator_branch=model['dominant'],surface_scope='exact nonincrease in stored affine boundary model on anchor denominator branch; not full-field arithmetic',
        coefficients_exact=[cert(v) for v in r['coefficients']],multipliers_exact=[cert(v) for v in r['multipliers']],active=r['active'],objective_value=cert(r['value']),
        exact_kkt_verified=True,coefficient_l1_cap=17,step_safety=.9,selected_coefficients=selected,diagnostics=diagnostics,
        anchor_boundary=dict(l1=float(model['l1']),bolometric=float(model['bolometric'])),
        candidate_written=False,baseline_replaced=False,full_field_nonnegative_verified=False,true_map_verified=False,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0)
    verify_candidate(c,g,gr,gh,cap,p)
    with TARGET.open('x') as f:json.dump(c,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(raw=list(map(float,r['coefficients'])),selected=selected,active=r['active'],cuts=len(cuts),diagnostics=diagnostics,anchor=c['anchor_boundary']),indent=2))

if __name__=='__main__':run()
