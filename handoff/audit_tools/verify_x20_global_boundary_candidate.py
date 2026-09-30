"""Independent finite candidate check; does not invoke SLSQP or its derivatives."""
from fractions import Fraction as F
from pathlib import Path
import json,math
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT,read,digest
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def main():
    cp=Path('handoff/evidence/20261001-x20-global-boundary-candidate.json');c=read(cp)
    bp=ROOT/'x20-latest-basis-82441-received/basis.json';assert digest(bp)==c['basis_sha256']
    assert c['source_job']==82441 and c['solver_success'] and c['small_prediction_passed']
    assert c['selected_coefficients']==[float(F(9,10)*F(v)) for v in c['raw_coefficients']]
    rows=read(bp)['slabs'];alpha=c['selected_coefficients'];raw=c['raw_coefficients']
    assert all(math.isfinite(v) for v in alpha+raw)
    assert abs(1-sum(map(F,alpha)))+sum(abs(F(v)) for v in alpha)<=17
    raw_eval=expected_from_basis(rows,[raw]*76)
    assert math.isclose(raw_eval['squared_l2'][1]/raw_eval['squared_l2'][0],c['objective'],rel_tol=3e-10)
    e=expected_from_basis(rows,[alpha]*76);gates=dict(full_l2=e['squared_l2'][1]<=.64*e['squared_l2'][0],half_l2=e['squared_l2'][2]<=e['squared_l2'][0])
    boundary=[]
    for i in range(3):
        den=max(e['boundary_flux'][2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=e['boundary_l1_numerator'][i]/den,boundary_bolometric=abs(e['boundary_signed'][i])/den))
    for i,name in ((1,'full'),(2,'half')):
        for key in boundary[i]:gates[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]
    assert all(gates.values())
    result=dict(source_job=82441,candidate_sha256=digest(cp),basis_sha256=digest(bp),selected_coefficients=alpha,
                exact_cap_and_safety_checked=True,raw_objective_independently_checked=True,checks=gates,
                passed=True,global_optimality_claimed=False,full_field_positivity_checked=False,full_field_linf_checked=False,
                l2_ratios=[math.sqrt(v/e['squared_l2'][0]) for v in e['squared_l2']],boundary=boundary,
                new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False)
    p=Path('handoff/evidence/20261001-x20-global-boundary-candidate-review.json')
    with p.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
