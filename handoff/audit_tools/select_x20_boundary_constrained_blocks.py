"""One bounded 76-variable SLSQP search, followed by independent Decimal screening.

Only interpolate each block between the anchor and the measured nonnegative
82472 mixed endpoint (block 65 uses its old half). No claim of global optimality.
"""
import json
from pathlib import Path
import math
import numpy as np
from scipy.optimize import minimize
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT, read, digest
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def model(rows, coefficients):
    grams = np.zeros((76,4,4), dtype=np.longdouble)
    spectra = np.concatenate([np.asarray(r['boundary_spectra'], dtype=np.longdouble) for r in rows], axis=1)
    for row in rows:
        grams[row['block']] += np.asarray(row['gram'], dtype=np.longdouble)
    cs = np.asarray(coefficients, dtype=np.longdouble)
    a = grams[:,0,0]
    b = np.einsum('bi,bi->b', grams[:,0,1:], cs)
    h = np.einsum('bi,bij,bj->b', cs, grams[:,1:,1:], cs)
    assert np.all(h>=0) and np.sum(a)>0
    scale = np.sum(a)
    group_block = np.arange(9632)//128
    changes = np.zeros((2,9632), dtype=np.longdouble)
    for i in range(2):
        changes[i] = sum(cs[group_block,j]*(spectra[2*j+2+i]-spectra[i]) for j in range(3))
    anchor = spectra[:2]
    endpoint = anchor + changes
    assert np.isfinite(endpoint).all() and np.all(endpoint>=0)
    baseline_den = max(np.sum(anchor[0]), np.sum(anchor[1]))
    # Valid lower bound for BOTH flux integrals for any independent block t in [0,1].
    # Round downward by 1e-12 before using a stricter 0.95 safety target.
    lower_den = max(np.sum(np.minimum(anchor[0],endpoint[0])), np.sum(np.minimum(anchor[1],endpoint[1])))*(1-np.longdouble('1e-12'))
    r = anchor[1]-anchor[0]
    dr = changes[1]-changes[0]
    l1 = np.sum(abs(r))/baseline_den
    bol = abs(np.sum(r))/baseline_den
    assert min(lower_den, l1, bol)>0
    l1_target = .95*l1*lower_den
    bol_target = .95*bol*lower_den
    b, h = np.asarray(b/scale,float), np.asarray(h/scale,float)
    r1, d1 = np.asarray(r/l1_target,float), np.asarray(dr/l1_target,float)
    rbol = float(np.sum(r)/bol_target)
    dbol = np.bincount(group_block,weights=np.asarray(dr/bol_target,float),minlength=76)
    def objective(t): return 1+float(np.dot(2*b,t)+np.dot(h,t*t))
    def gradient(t): return 2*b+2*h*t
    def constraints(t):
        v=r1+d1*t[group_block]
        z=rbol+np.dot(dbol,t)
        return np.array([1-np.sum(abs(v)),1-z,1+z])
    def jacobian(t):
        v=r1+d1*t[group_block]
        first=-np.bincount(group_block,weights=np.sign(v)*d1,minlength=76)
        return np.array([first,-dbol,dbol])
    return objective,gradient,constraints,jacobian,float(lower_den)


def main():
    proposal_path=Path('handoff/evidence/20261001-x20-block65-half-proposal.json')
    proposal=read(proposal_path)
    assert proposal['source_job']==82472 and proposal['changed_blocks']==[65]
    basis_path=ROOT/'x20-latest-basis-82441-received/basis.json'
    rows=read(basis_path)['slabs']
    cs=np.asarray(proposal['selected_coefficients'])
    objective,gradient,constraints,jacobian,lower_den=model(rows,cs)
    bounds=[(0.,0.) if not np.any(row) else (0.,1.) for row in cs]
    # One declared start and iteration budget; unsuccessful result is retained.
    result=minimize(objective,np.full(76,.5),jac=gradient,bounds=bounds,
        constraints=[dict(type='ineq',fun=constraints,jac=jacobian)],
        method='SLSQP',options=dict(maxiter=200,ftol=1e-12,disp=False))
    t=result.x
    selected=cs*t[:,None]
    assert np.isfinite(t).all() and np.isfinite(selected).all()
    in_bounds=bool(np.all(t>=0) and np.all(t<=1))
    expected=expected_from_basis(rows,selected.tolist())
    boundary=[]
    for i in range(3):
        den=max(expected['boundary_flux'][2*i:2*i+2])
        assert den>0
        boundary.append(dict(boundary_l1=expected['boundary_l1_numerator'][i]/den,
                             boundary_bolometric=abs(expected['boundary_signed'][i])/den))
    ratios=[math.sqrt(v/expected['squared_l2'][0]) for v in expected['squared_l2']]
    checks=dict(solver_success=bool(result.success),bounded=in_bounds,
                full_l2_benefit=ratios[1]<=.8,half_l2_nonincrease=ratios[2]<=1+1e-10)
    for i,name in ((1,'full'),(2,'half')):
        for key in boundary[i]:
            checks[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]*(1+1e-10)
    checks['cap17']=all(abs(1-math.fsum(c))+math.fsum(map(abs,c))<=17 for c in selected)
    evidence=dict(source_job=82472,proposal_sha256=digest(proposal_path),basis_sha256=digest(basis_path),
        method='SLSQP; 76 scalar block interpolants in [0,1]; one start 0.5; maxiter 200; ftol 1e-12',
        scope='candidate selection only; no certified optimum, no field positivity or Linf proof',
        solver_success=bool(result.success),solver_message=str(result.message),iterations=int(result.nit),
        objective=float(result.fun),block_factors=t.tolist(),selected_coefficients=selected.tolist(),
        boundary_target_fraction=.95,conservative_flux_denominator=lower_den,
        normalized_constraint_slack=constraints(t).tolist(),independent_decimal_prediction=expected,
        predicted_l2_ratios=ratios,boundary=boundary,checks=checks,
        eligible_for_full_field_scan=all(checks.values()),new_maps=0,new_feedback_pairs=0,new_material_steps=0,
        baseline_replaced=False,candidate_written=False)
    target=Path('handoff/evidence/20261001-x20-boundary-constrained-selection.json')
    with target.open('x') as f:f.write(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('block_factors','selected_coefficients','independent_decimal_prediction')},indent=2))


if __name__=='__main__':main()
