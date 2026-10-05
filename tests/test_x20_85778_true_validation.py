import copy,json
from pathlib import Path
import numpy as np
import pytest
from operations.x20_85778_true_validation import validate_prediction,previous_pair_row
from operations.x20_boundary_validation_fields import write_candidates
from operations.x20_window_fields import basis_fields


def audit():
    return json.loads(Path('handoff/evidence/20261006-x20-boundary-prediction-85778-review.json').read_text())


def declaration():
    return dict(global_coefficients=[-6.846213173701946,-.3537868262980542,.0659556218584672],step_safety=.9,
                source_job=85744,source_feedback_jobs=[84026,82989,82518],known_sign_constraints=0,shape=[9632,32,4096],fields=audit()['fields'])


@pytest.mark.parametrize('damage',['none','job','gate','missing','coefficient','phase_source','scope','fields','scheduler','certificate'])
def test_prediction_permission_requires_every_original_gate(damage):
    a,d=audit(),declaration()
    if damage=='none':validate_prediction(a,d);return
    if damage=='job':a['job_id']=82686
    elif damage=='gate':a['result']['checks']['half_boundary_l1']=False
    elif damage=='missing':del a['result']['checks']['full_l2_benefit']
    elif damage=='coefficient':d['global_coefficients'][0]*=.5
    elif damage=='phase_source':d['source_job']=82512
    elif damage=='fields':d['fields'][0]['sha256']='wrong'
    elif damage=='scheduler':a['scheduler_terminal_verified']=False
    elif damage=='certificate':a['small_qp_certificate_verified']=False
    else:a['new_material_steps']=1
    with pytest.raises(ValueError):validate_prediction(a,d)


def test_previous_to_final_uses_the_first_map_row_not_the_last():
    ep={k:dict(path=k,sha256=v) for k,v in [('previous','a'),('final','b'),('mapped_final','c')]}
    m=dict(endpoints=ep,history_rows=[dict(iteration=15,input_sha256='a',output_sha256='b'),dict(iteration=16,input_sha256='b',output_sha256='c')])
    assert previous_pair_row(m,[ep['previous'],ep['final']])['iteration']==15
    with pytest.raises(ValueError):previous_pair_row(m,[ep['final'],ep['mapped_final']])
    broken=copy.deepcopy(m);broken['history_rows'][0]['output_sha256']='c'
    with pytest.raises(ValueError):previous_pair_row(broken,[ep['previous'],ep['final']])


def test_written_candidate_matches_screen_expression_across_block_boundary(tmp_path):
    shape=(130,2,2);b=np.linspace(1,2,np.prod(shape)).reshape(shape)
    aa=[b*(1+i*.001) for i in range(8)];paths=[]
    for i,x in enumerate(aa):
        p=tmp_path/f's{i}.dat';x.tofile(p);paths.append(p)
    c=[-6.846213173701946,-.3537868262980542,.0659556218584672];q,_=basis_fields(aa,c)
    full,half=tmp_path/'full.dat',tmp_path/'half.dat'
    write_candidates(paths,shape,[c]*2,full,half)
    np.testing.assert_array_equal(np.fromfile(full).reshape(shape),q)
    np.testing.assert_array_equal(np.fromfile(half).reshape(shape),.5*aa[0]+.5*q)
