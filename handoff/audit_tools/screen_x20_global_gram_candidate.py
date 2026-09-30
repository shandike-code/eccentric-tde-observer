"""Screen the already certified global coefficients; no new optimization or maps."""
from fractions import Fraction as F
import hashlib,json,math
from pathlib import Path
from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis


def main():
    source=Path('handoff/evidence/20261001-x20-82441-bounded-gram-analysis.json')
    proof=json.loads(Path('handoff/evidence/20261001-x20-82441-bounded-gram-verification.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==proof['analysis_sha256']
    analysis=json.loads(source.read_text())
    basis=Path('outputs/review-20260925/x20-latest-basis-82441-received/basis.json')
    assert hashlib.sha256(basis.read_bytes()).hexdigest()==analysis['basis_sha256']
    raw=[F(int(v['numerator']),int(v['denominator'])) for v in analysis['global_result']['coefficients_exact']]
    c=list(map(float,[F(9,10)*v for v in raw]))
    assert abs(1-sum(map(F,c)))+sum(abs(F(v)) for v in c)<=17
    prediction=expected_from_basis(json.loads(basis.read_text())['slabs'],[c]*76)
    norms=[math.sqrt(v/prediction['squared_l2'][0]) for v in prediction['squared_l2']]
    boundary=[]
    for i in range(3):
        den=max(prediction['boundary_flux'][2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=prediction['boundary_l1_numerator'][i]/den,
                             boundary_bolometric=abs(prediction['boundary_signed'][i])/den))
    gates=dict(full_l2=norms[1]<=.8,half_l2=norms[2]<=1+1e-10)
    for i,name in ((1,'full'),(2,'half')):
        for key in boundary[i]:gates[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]*(1+1e-10)
    result=dict(source_job=82441,analysis_sha256=proof['analysis_sha256'],basis_sha256=analysis['basis_sha256'],
                selected_coefficients=c,l2_ratios=norms,boundary=boundary,checks=gates,
                small_prediction_passed=all(gates.values()),full_field_positivity_checked=False,full_field_linf_checked=False,
                strict_error_bound=False,candidate_written=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    p=Path('handoff/evidence/20261001-x20-global-gram-candidate-screen.json')
    with p.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
