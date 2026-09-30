"""Feasibility screening of a finite optimizer iterate, never an optimality claim.

The original search exhausted its budget and remains unsuccessful. This separate
record asks only whether that stored point satisfies the original prediction
thresholds. Full-field validation is still required before any true mapping.
"""
from fractions import Fraction
import json
import math
from pathlib import Path
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT, read, digest
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def main():
    path=Path('handoff/evidence/20261001-x20-boundary-constrained-selection.json')
    parent=Path('handoff/evidence/20261001-x20-block65-half-proposal.json')
    selection,proposal=read(path),read(parent)
    assert selection['proposal_sha256']==digest(parent)
    assert selection['solver_success'] is False and selection['iterations']==200
    assert selection['eligible_for_full_field_scan'] is False
    coefficients=selection['selected_coefficients'];factors=selection['block_factors']
    assert len(coefficients)==len(factors)==76
    for c,p,t in zip(coefficients,proposal['selected_coefficients'],factors):
        assert math.isfinite(t) and 0<=t<=1 and c==[v*t for v in p]
        exact=list(map(Fraction,c))
        assert abs(1-sum(exact))+sum(map(abs,exact))<=17
    basis=ROOT/'x20-latest-basis-82441-received/basis.json'
    assert digest(basis)==selection['basis_sha256']
    e=expected_from_basis(read(basis)['slabs'],coefficients)
    boundary=[]
    for i in range(3):
        den=max(e['boundary_flux'][2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=e['boundary_l1_numerator'][i]/den,
                             boundary_bolometric=abs(e['boundary_signed'][i])/den))
    checks=dict(full_l2=e['squared_l2'][1]<=.64*e['squared_l2'][0],half_l2=e['squared_l2'][2]<=e['squared_l2'][0])
    for i,name in ((1,'full'),(2,'half')):
        for key in boundary[i]:checks[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]
    assert all(checks.values())
    result=dict(source_job=82472,selection_sha256=digest(path),proposal_sha256=digest(parent),basis_sha256=digest(basis),
                selection_solver_success=False,selection_eligible_for_full_field_scan=False,
                separate_decision='finite point satisfies original small-artifact thresholds; permit one full-field test only',
                original_science_thresholds_changed=False,global_optimality_claimed=False,
                full_field_positivity_verified=False,full_field_linf_verified=False,
                predicted_l2_ratios=[math.sqrt(v/e['squared_l2'][0]) for v in e['squared_l2']],boundary=boundary,
                checks=checks,selected_coefficients=coefficients,permit_one_full_field_prediction=True,
                new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,candidate_written=False)
    target=Path('handoff/evidence/20261001-x20-boundary-candidate-feasibility.json')
    with target.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='selected_coefficients'},indent=2))


if __name__=='__main__':main()
