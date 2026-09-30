"""Find one interior spectral candidate; original scientific gates remain intact."""
import argparse
import json
import math
import subprocess
import time
from decimal import Decimal, localcontext
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from operations import x20_expanded_feasibility as small

ROOT=small.ROOT
PAIRS=((0,1),(3,4),(4,5),(6,7))


def spectral_witness(gram,spectra,point):
    """Evaluate all available original gates without relying on optimizer status."""
    p=np.asarray(point,float)
    if p.shape!=(4,) or not np.isfinite(p).all():raise ValueError('four finite coefficients required')
    fs=np.asarray(spectra,np.longdouble)
    if fs.shape[0]!=8 or not np.isfinite(fs).all() or np.any(fs<0):raise ValueError('eight physical spectra required')
    b,c=fs[1:3];original=max(np.sum(b,dtype=np.longdouble),np.sum(c,dtype=np.longdouble))
    if original<=0:raise ValueError('positive original flux required')
    base_l1=np.sum(abs(c-b),dtype=np.longdouble)/original
    base_bol=abs(np.sum(c-b,dtype=np.longdouble))/original
    if min(base_l1,base_bol)<=0:raise ValueError('positive reference boundary differences required')
    result=[]
    with localcontext() as ctx:
        ctx.prec=70;D=small.D;gd=[[D(v)/D(gram[0,0]) for v in row] for row in gram]
        for fraction in (.9,.45):
            fin=b.copy();fout=c.copy()
            for z,(i,j) in zip(p,PAIRS):
                fin+=np.longdouble(fraction)*np.longdouble(z)*(fs[i]-b)
                fout+=np.longdouble(fraction)*np.longdouble(z)*(fs[j]-c)
            physical=bool(np.isfinite(fin).all() and np.isfinite(fout).all() and min(fin.min(),fout.min())>=0)
            den=max(np.sum(abs(fin),dtype=np.longdouble),np.sum(abs(fout),dtype=np.longdouble))
            if den<=0:raise ValueError('positive candidate flux required')
            l1=float(np.sum(abs(fout-fin),dtype=np.longdouble)/den)
            bol=float(abs(np.sum(fout-fin,dtype=np.longdouble))/den)
            u=[D(1)]+[D(fraction)*D(z) for z in p]
            squared=sum(u[i]*gd[i][j]*u[j] for i in range(5) for j in range(5))
            if squared<0:raise ValueError('negative quadratic norm')
            result.append(dict(fraction=fraction,l2_ratio=float(squared.sqrt()),squared_l2_70digit=str(squared),
                boundary_l1=l1,boundary_bolometric=bol,boundary_l1_ratio=l1/float(base_l1),boundary_bolometric_ratio=bol/float(base_bol),
                minimum_input=float(fin.min()),minimum_output=float(fout.min()),positive_spectra=physical))
    weights=np.r_[p[0],1-math.fsum(p),p[1:]];weight_l1=math.fsum(abs(weights))
    checks=dict(raw_weight_cap=weight_l1<=17,full_l2_benefit=result[0]['l2_ratio']<=.8,half_l2_nonincrease=result[1]['l2_ratio']<=1+1e-10)
    for name,row in zip(('full','half'),result):
        checks[name+'_positive_spectra']=row['positive_spectra']
        for key in ('boundary_l1','boundary_bolometric'):
            checks[name+'_'+key]=row[key]<1e-3 and row[key+'_ratio']<=1+1e-10
    return dict(raw_coefficients=p.tolist(),raw_weights=weights.tolist(),raw_weight_l1=weight_l1,
        selected_coefficients=(.9*p).tolist(),full_fraction=.9,half_fraction=.45,
        endpoints=result,checks=checks,available_gates_passed=all(checks.values()),
        full_field_positivity_and_linf_evaluated=False,true_maps_evaluated=False,candidate_written=False)


def propose(gram,spectra,start):
    small.positive_hessian(gram);sys=small.system(spectra,PAIRS);_,a,b=small.cap_geometry(4)
    # 仅把内部搜索域收紧；最终仍按原上限17验收，不放宽任何科学门。
    b=b-1e-7
    den=[small.denominator_upper(sys,t) for t in (.9,.45)]
    lower=[math.nextafter(float(min(Decimal(v) for row in d['vertex_fluxes_70digit'] for v in row)),-math.inf) for d in den]
    if min(lower)<=0:raise ValueError('no positive global flux lower bound')
    l1_limit=[.98*sys['limit']*z for z in lower]
    bol_limit=[.98*abs(math.fsum(sys['r']))*(1+1e-10)*z for z in lower]
    if min(bol_limit)<=0:raise ValueError('positive bolometric search bound required')
    g=gram/gram[0,0];trace=[]
    def value(c):u=np.r_[1.,.9*c];return float(u@g@u)
    def jac(c):return 1.8*(g[1:,0]+.9*g[1:,1:]@c)
    def limits(c):
        values=[]
        for t,l1,bol in zip((.9,.45),l1_limit,bol_limit):
            r=sys['r']+t*(sys['dr']@c)
            values.extend((1-math.fsum(abs(r))/l1,1-math.fsum(r)/bol,1+math.fsum(r)/bol))
        return np.array(values)
    def limits_jac(c):
        rows=[];total=np.array([math.fsum(x) for x in sys['dr'].T])
        for t,l1,bol in zip((.9,.45),l1_limit,bol_limit):
            sign=np.sign(sys['r']+t*(sys['dr']@c))
            rows.extend((-t*(sign@sys['dr'])/l1,-t*total/bol,t*total/bol))
        return np.array(rows)
    def record(c):trace.append(dict(point=c.tolist(),quadratic=value(c),minimum_search_constraint=float(min(limits(c)))))
    opt=minimize(value,np.asarray(start,float),jac=jac,method='SLSQP',constraints=[
        dict(type='ineq',fun=lambda c:b-a@c,jac=lambda c:-a),dict(type='ineq',fun=limits,jac=limits_jac)],
        callback=record,options=dict(ftol=1e-12,maxiter=200))
    witness=spectral_witness(gram,spectra,opt.x)
    witness.update(optimizer=dict(success=bool(opt.success),message=opt.message,iterations=int(opt.nit)),
        conservative_flux_lower_bounds=lower,search_margin=.98,internal_cap_margin=1e-7,trace=trace,
        minimum_search_constraint=float(min(limits(opt.x))),search_limits_pass=bool(min(limits(opt.x))>=-1e-10),
        original_science_gates_changed=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20)
    witness['status']='small_candidate_requires_full_field_scan' if witness['available_gates_passed'] else 'small_candidate_rejected'
    return witness


def execute(source,previous,out):
    started=time.monotonic();out.relative_to(ROOT/'outputs');out.mkdir(exist_ok=False)
    audit=ROOT/'handoff/evidence/20260930-x20-expanded-feasibility-review.json';review=json.loads(audit.read_text())
    if not review['independent_dual_and_cut_audit'] or review['no_20pct_candidate_in_full_registered_cap']:raise ValueError('reviewed unresolved four-direction source required')
    if small.claim(previous/'result.json')['sha256']!=review['result_sha256']:raise ValueError('previous result changed')
    declaration=json.loads((previous/'declaration.json').read_text())
    source_claims=declaration['source_files']+[declaration[k] for k in ('source_audit','source_archive','source_manifest')]
    claims=source_claims+[small.claim(p) for p in (audit,previous/'result.json',previous/'declaration.json')]
    code=[small.claim(ROOT/p) for p in ('operations/x20_expanded_candidate.py','operations/x20_expanded_feasibility.py','tests/test_x20_expanded_candidate.py','handoff/protocols/x20-expanded-candidate-v1.md')]
    for c in claims+code:
        if small.claim(ROOT/c['path'])!=c:raise ValueError('source or code changed')
    small.write(out/'declaration.json',dict(source_claims=claims,code=code,source_job=81647,source_basis=json.loads((source/'expanded-basis.json').read_text()),
        git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        fixed_phase=1367,fixed_dt_s=889.419892762322,maximum_iterations=200,raw_weight_l1_cap=17,full_fraction=.9,half_fraction=.45,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20))
    with np.load(source/'expanded-system.npz',allow_pickle=False) as z:gram=z['gram'];spectra=z['spectra']
    before=json.loads((previous/'result.json').read_text());result=propose(gram,spectra,before['trace'][-1]['point']);result['wall_s']=time.monotonic()-started
    for c in claims+code:
        if small.claim(ROOT/c['path'])!=c:raise RuntimeError('input changed during diagnostic')
    small.write(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='trace'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    execute(ROOT/'outputs/review-20260925/x20-long-chord-81647-received',ROOT/'outputs/review-20260925/x20-expanded-feasibility-20260930',(ROOT/args.out).resolve())
