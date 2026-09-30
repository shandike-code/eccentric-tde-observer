"""One three-coefficient global search with original boundary constraints.

Uses the input flux as a conservative denominator (max(input,output)>=input).
No proof of optimality is inferred from a numerical optimizer's exit code.
"""
import itertools,json,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT,read,digest
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def main():
    bp=ROOT/'x20-latest-basis-82441-received/basis.json'
    analysis=read('handoff/evidence/20261001-x20-82441-bounded-gram-analysis.json')
    assert digest(bp)==analysis['basis_sha256']
    rows=read(bp)['slabs']
    g=np.array([[float(sum((F(r['gram'][i][j]) for r in rows),F(0))) for j in range(4)] for i in range(4)])
    normalized=g/g[0,0]
    transform=np.linalg.solve(np.linalg.cholesky(normalized[1:,1:]).T,np.eye(3))
    b=normalized[0,1:]@transform
    spectra=np.concatenate([np.asarray(r['boundary_spectra'],np.longdouble) for r in rows],axis=1)
    x,y=spectra[:2];dx=(spectra[2::2]-x).T;dy=(spectra[3::2]-y).T
    r=y-x;dr=dy-dx
    flux=max(np.sum(x),np.sum(y));n=np.sum(abs(r));m=abs(np.sum(r))
    assert min(flux,n,m,np.sum(x))>0
    r1=np.asarray(r/n,float);d1=np.asarray(dr/n,float)@transform
    rbol=float(np.sum(r)/m);dbol=np.asarray(np.sum(dr,axis=0)/m,float)@transform
    den0=float(np.sum(x)/flux);dend=np.asarray(np.sum(dx,axis=0)/flux,float)@transform
    signs=np.array(list(itertools.product((-1.,1.),repeat=4)))
    cap_matrix=signs[:,1:]-signs[:,0,None];cap_rhs=17-signs[:,0]
    cap_z=cap_matrix@transform
    def objective(z):return 1+2*np.dot(b,z)+np.dot(z,z)
    def grad(z):return 2*b+2*z
    def constraints(z):
        den=.98*(den0+np.dot(dend,z));v=r1+d1@z;bol=rbol+np.dot(dbol,z)
        return np.r_[den-np.sum(abs(v)),den-bol,den+bol,cap_rhs-cap_z@z]
    def jac(z):
        v=r1+d1@z
        return np.vstack([.98*dend-np.sign(v)@d1,.98*dend-dbol,.98*dend+dbol,-cap_z])
    result=minimize(objective,np.zeros(3),jac=grad,method='SLSQP',
                    constraints=[dict(type='ineq',fun=constraints,jac=jac)],
                    options=dict(maxiter=200,ftol=1e-11,disp=False))
    raw=transform@result.x
    # Declared 0.9 safety interpolation towards the original anchor.
    selected=[float(F(9,10)*F(float(v))) for v in raw]
    e=expected_from_basis(rows,[selected]*76)
    ratios=[math.sqrt(v/e['squared_l2'][0]) for v in e['squared_l2']]
    boundary=[]
    for i in range(3):
        den=max(e['boundary_flux'][2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=e['boundary_l1_numerator'][i]/den,boundary_bolometric=abs(e['boundary_signed'][i])/den))
    checks=dict(solver_success=bool(result.success),cap17=abs(1-sum(map(F,selected)))+sum(abs(F(v)) for v in selected)<=17,
                full_l2=ratios[1]<=.8,half_l2=ratios[2]<=1+1e-10)
    for i,name in ((1,'full'),(2,'half')):
        for key in boundary[i]:checks[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]*(1+1e-10)
    q=x+dx@np.asarray(selected,np.longdouble);p=y+dy@np.asarray(selected,np.longdouble)
    checks['boundary_spectra_nonnegative']=bool(np.all(q>=0) and np.all(p>=0))
    out=dict(source_job=82441,basis_sha256=digest(bp),raw_coefficients=raw.tolist(),selected_coefficients=selected,
             method='one SLSQP start at zero, 200 iterations, Cholesky variable scaling without truncation',
             solver_success=bool(result.success),solver_message=str(result.message),iterations=int(result.nit),
             raw_constraint_slack=constraints(result.x).tolist(),objective=float(result.fun),step_safety=.9,
             internal_boundary_target=.98,l2_ratios=ratios,boundary=boundary,checks=checks,
             small_prediction_passed=all(checks.values()),full_field_positivity_checked=False,full_field_linf_checked=False,
             global_optimality_claimed=False,strict_error_bound=False,candidate_written=False,
             new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    target=Path('handoff/evidence/20261001-x20-global-boundary-candidate.json')
    with target.open('x') as f:f.write(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
