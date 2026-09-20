import numpy as np
import pytest
from operations.validate_recent_subspace import (
    mix_parameters, subspace_chunk, write_candidate, full_field_error, validated_plan,
)
from operations.scan_multihistory_subspace import fields


def files(tmp_path, arrays):
    paths = [tmp_path/str(i) for i in range(len(arrays))]
    for p, a in zip(paths, arrays): np.asarray(a, dtype=np.float64).tofile(p)
    return paths


def case():
    arrays = [np.full((2, 4, 3), v) for v in (1., 1.02, 1.04, 1.04, 1.06, 1.08)]
    return arrays, np.array([0., 0., 0., 1.]), np.array([1., 0., -15.5, 15.5]), .999999999999995


def test_writer_matches_preregistered_expression_and_preserves_basis(tmp_path):
    arrays, a, t, step = case(); paths = files(tmp_path, arrays); before = [p.read_bytes() for p in paths]
    out = tmp_path/'candidate.dat';write_candidate(paths, out, arrays[0].shape, a, t, step)
    ax, _ = fields(arrays, a); tx, _ = fields(arrays, t)
    assert np.array_equal(np.fromfile(out).reshape(ax.shape), ax+step*(tx-ax))
    assert [p.read_bytes() for p in paths] == before
    with pytest.raises(FileExistsError):write_candidate(paths, out, arrays[0].shape, a, t, step)


def test_short_source_cannot_publish_candidate(tmp_path):
    arrays, a, t, step = case();paths=files(tmp_path, arrays)
    paths[3].write_bytes(paths[3].read_bytes()[:-8]);out=tmp_path/'candidate.dat'
    with pytest.raises(RuntimeError, match='short'):write_candidate(paths,out,arrays[0].shape,a,t,step)
    assert not out.exists()


@pytest.mark.parametrize('target,step', [([1., 0., -16., 16.], 1.), ([1.,0.,np.nan,0.],1.), ([1.,0.,0.,0.],1.1)])
def test_coefficient_guards(target, step):
    with pytest.raises(ValueError):mix_parameters([0.,0.,0.,1.],target,step)


def test_negative_candidate_rejected_without_clipping():
    arrays=[np.full((1,4,2),v) for v in (1.,1.,1.,10.,10.,10.)]
    with pytest.raises(ArithmeticError):subspace_chunk(arrays,[0.,1.,0.,0.],[0.,2.,0.,-1.],1.)


def test_full_field_exact_prediction_and_candidate_byte_check(tmp_path):
    arrays,a,t,step=case();x,y=subspace_chunk(arrays,a,t,step)
    paths=files(tmp_path,[x,y,*arrays]);r=full_field_error(paths,x.shape,a,t,step,np.array([1.,2.,3.]))
    assert r['error_l2']==r['boundary_prediction_l1_error']==0 and r['prediction_error_resolved']
    x.flat[0]+=1e-6;x.tofile(paths[0])
    with pytest.raises(RuntimeError,match='candidate bytes'):full_field_error(paths,x.shape,a,t,step,np.array([1.,2.,3.]))


def test_equal_scalar_residual_does_not_hide_wrong_field(tmp_path):
    x=np.ones((1,4,2));pred=x.copy();pred[0,0,0]+=.1
    actual=x.copy();actual[0,1,0]+=.1
    arrays=[x,x,pred,x,x,x];a=np.array([0.,1.,0.,0.])
    r=full_field_error(files(tmp_path,[x,actual,*arrays]),x.shape,a,a,1.,np.array([1.,2.]))
    assert r['error_over_actual_defect_l2']==pytest.approx(np.sqrt(2.))
    assert not r['prediction_error_resolved']


def test_scan_pass_flag_cannot_override_missing_gate_or_new_best():
    a=[0.,0.,0.,1.];p={'algebraic_feasibility':True,'checks':{},'prediction':{'predicted_residual':.5},
                       'anchor_weights':a,'raw_weights':a,'step':1.}
    d={'anchor_weights':a}
    with pytest.raises(RuntimeError,match='missing'):validated_plan(p,d,1.)
    p['checks']={k:True for k in ('positive_step','coefficient_cap','full_field_nonnegative',
                                'improves_latest_measured_maximum_norm','boundary_l1','boundary_bolometric')}
    validated_plan(p,d,1.)
    with pytest.raises(RuntimeError,match='current measured baseline'):validated_plan(p,d,.4)
