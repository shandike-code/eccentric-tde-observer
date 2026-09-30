import json
from pathlib import Path
import numpy as np
import pytest
from operations.x20_window_validation_fields import write_candidates,prediction_error
from operations.x20_window_fields import basis_fields
from operations.x20_window_validation import validate_prediction
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction


def fixture(tmp_path):
    shape=(34,2,2);x=np.linspace(1.,5.,np.prod(shape)).reshape(shape)
    op=lambda a:.7*a+.2
    aa=[z for v in (x,x+1,x*.8,x*.6) for z in (v,op(v))]
    paths=[]
    for i,z in enumerate(aa):
        p=tmp_path/f'{i}.dat';z.tofile(p);paths.append(p)
    return shape,aa,paths,op


def test_written_full_half_and_true_affinity(tmp_path):
    shape,aa,paths,op=fixture(tmp_path);co=[.1,-.2,.05]
    full,half=tmp_path/'full.dat',tmp_path/'half.dat'
    write_candidates(paths,shape,co,full,half)
    q,p=basis_fields(aa,co)
    np.testing.assert_array_equal(np.fromfile(full).reshape(shape),q)
    np.testing.assert_array_equal(np.fromfile(half).reshape(shape),.5*aa[0]+.5*q)
    outputs=[]
    for i,v in enumerate((q,.5*aa[0]+.5*q)):
        dest=tmp_path/f'out{i}.dat';op(v).tofile(dest);outputs.append(dest)
    r=prediction_error(paths+outputs,shape,co)
    assert r['passed'] and [z['group_count'] for z in r['slabs']]==[32,2]
    with pytest.raises(FileExistsError):write_candidates(paths,shape,co,full,half)


def test_true_prediction_mismatch_is_not_hidden(tmp_path):
    shape,aa,paths,op=fixture(tmp_path);co=[.1,-.2,.05];q,p=basis_fields(aa,co);outputs=[]
    for i,v in enumerate((p+1e-3,.5*aa[1]+.5*p)):
        dest=tmp_path/f'out{i}.dat';v.tofile(dest);outputs.append(dest)
    r=prediction_error(paths+outputs,shape,co)
    assert not r['passed'] and not r['checks']['full_l2_affinity'] and r['checks']['half_l2_affinity']


def test_negative_candidate_never_committed(tmp_path):
    shape,aa,paths,op=fixture(tmp_path);full=tmp_path/'full.dat';half=tmp_path/'half.dat'
    with pytest.raises(ValueError):write_candidates(paths,shape,[-10,0,0],full,half)
    assert not full.exists() and not half.exists()


@pytest.mark.parametrize('damage',['fields','coefficient','gate','scope'])
def test_prediction_source_guard(damage):
    a=json.loads(Path('handoff/evidence/20260930-x20-82187-review.json').read_text())
    d=dict(fields=a['fields'],selected_coefficients=a['selected_coefficients'],raw_coefficients=a['raw_coefficients'])
    validate_prediction(a,d)
    if damage=='fields':d['fields']=[]
    elif damage=='coefficient':d['selected_coefficients']=[]
    elif damage=='gate':a['checks']['full_l2_benefit']=False
    else:a['new_material_steps']=1
    with pytest.raises(ValueError):validate_prediction(a,d)


def test_independent_reduction_rejects_negative_and_missing_coverage():
    row=dict(first_group=0,group_count=1,squared_l2=[1,.25,.64],linf=[1,.5,.8],scales=[1e6]*3,
        minima=[0]*4,boundary_flux=[1,1,1,1,1,1],boundary_l1_numerator=[1e-5,5e-6,8e-6],boundary_signed=[1e-6,5e-7,8e-7])
    assert reduce_prediction([row])['passed']
    row['minima'][0]=-1
    assert not reduce_prediction([row])['passed']
    row['first_group']=1
    with pytest.raises(ValueError):reduce_prediction([row])
