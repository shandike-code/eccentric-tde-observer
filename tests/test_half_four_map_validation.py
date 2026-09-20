from copy import deepcopy
import numpy as np
import pytest
from operations.half_four_map_candidate import (
    EXPECTED_CHECKS, verify_scan, candidate_chunk, write_candidate, full_field_error,
)
from operations.scan_half_four_map_subspace import fields


def plan():
    pairs = [[{'path': str(2*i+j),'sha256':'h'+str(2*i+j)} for j in range(2)] for i in range(4)]
    d = {'pairs':pairs,'pair_order':['73929_last','73888_last','74057_previous','74057_last'],
         'new_maps':0,'candidate_write_budget':0,'coefficient_l1_cap':32.,'rank_requirement':3,
         'relative_rank_cutoff':1e-12,'maximum_cut_passes':6,'maximum_cuts':4096,
         'same_material_all_fields':True,'same_operator_and_old_time_level':True,
         'best_measured_residual':3e-5,'anchor_weights':[0.,0.,0.,1.]}
    p = {'checks':dict.fromkeys(EXPECTED_CHECKS,True),'algebraic_feasibility':True,
         'actual_map_performed':False,'candidate_written':False,'accepted_material_step':False,
         'best_measured_residual':3e-5,'anchor_weights':[0.,0.,0.,1.],
         'effective_weights':[.25,.25,.25,.25],'raw_weights':[.25,.25,.25,.25],'coefficient_step':1.,
         'system':{'eigenvalues':[1e-4,1e-3,1.],'retained_rank':3,'relative_cutoff':1e-12},
         'prediction':{'predicted_residual':2e-5,'predicted_residual_squared_l2':1e-4,
                       'predicted_boundary_l1':1e-5,'predicted_boundary_bolometric':1e-5,
                       'minimum_fields':[0.,0.],'negative_counts':[0,0]},
         'rounds':[{'statistics':{'negative_counts':[0,0]}}]}
    return p,d,pairs,3e-5


def test_complete_finite_scan_is_accepted_for_validation_only():
    np.testing.assert_array_equal(verify_scan(*plan()), [.25]*4)


@pytest.mark.parametrize('fault',['gate','truthy','pair','order','rank','cap','sum','expression','negative','nan','best','budget','rounds','improvement'])
def test_inconsistent_scan_cannot_create_a_candidate(fault):
    p,d,b,best = plan()
    if fault=='gate':p['checks'].pop('resolved_rank')
    if fault=='truthy':p['checks']['resolved_rank']=1
    if fault=='pair':d['pairs']=list(reversed(b))
    if fault=='order':d['pair_order'].reverse()
    if fault=='rank':p['system']['eigenvalues'][0]=1e-15
    if fault=='cap':p['effective_weights']=[17.,-16.,0.,0.]
    if fault=='sum':p['effective_weights']=[.25,.25,.25,.5]
    if fault=='expression':p['raw_weights']=[1.,0.,0.,0.]
    if fault=='negative':p['prediction']['minimum_fields'][0]=-5e-324
    if fault=='nan':p['prediction']['predicted_residual']=np.nan
    if fault=='best':best=4e-5
    if fault=='budget':d['maximum_cut_passes']=7
    if fault=='rounds':p['rounds'][-1]['statistics']['negative_counts']=[1,0]
    if fault=='improvement':p['prediction']['predicted_residual']=3e-5
    with pytest.raises(ValueError):verify_scan(p,d,b,best)


def basis(tmp_path):
    rng=np.random.default_rng(13);shape=(3,2,4);arrays=[];paths=[]
    for i in range(4):
        x=1+rng.random(shape)*.01
        arrays.extend([x,.8*x+.5])
    for i,a in enumerate(arrays):
        p=tmp_path/f'b{i}.bin';a.tofile(p);paths.append(p)
    return shape,arrays,paths


def test_exact_scan_order_is_preserved_even_with_signed_coefficients(tmp_path):
    shape,arrays,paths=basis(tmp_path);w=np.array([.01925459292288146,-1.9539925233402755e-14,-15.499999999999895,16.480745407077034])
    got=candidate_chunk(arrays,w);expected=fields(arrays,w)
    for a,b in zip(got,expected):assert np.array_equal(a,b)
    dest=tmp_path/'candidate.dat';write_candidate(paths,dest,shape,w)
    assert np.array_equal(np.fromfile(dest).reshape(shape),expected[0])
    with pytest.raises(FileExistsError):write_candidate(paths,dest,shape,w)


def test_tiny_negative_not_repaired():
    arrays=[np.ones((2,2,2))*1e-300 for _ in range(8)];arrays[0][0,0,0]=3e-300
    with pytest.raises(ArithmeticError):candidate_chunk(arrays,np.array([-1.,0.,0.,2.]))


def test_affine_reference_operator_and_full_candidate_reconstruction(tmp_path):
    shape,arrays,paths=basis(tmp_path);w=np.array([.25]*4)
    candidate=tmp_path/'candidate.dat';write_candidate(paths,candidate,shape,w)
    x=np.fromfile(candidate).reshape(shape);actual=.8*x+.5
    output=tmp_path/'mapped.dat';actual.tofile(output)
    err=full_field_error([candidate,output]+paths,shape,w,np.arange(1.,5.))
    assert err['candidate_reconstruction_exact'] and err['prediction_error_resolved']
    assert err['error_over_actual_defect_l2']<1e-12
    x[0,0,0]=np.nextafter(x[0,0,0],np.inf);x.tofile(candidate)
    with pytest.raises(RuntimeError,match='operation order'):full_field_error([candidate,output]+paths,shape,w,np.arange(1.,5.))


def test_wrong_physical_map_does_not_pass_a_small_field_relative_error(tmp_path):
    shape,arrays,paths=basis(tmp_path);w=np.array([.25]*4)
    candidate=tmp_path/'candidate.dat';write_candidate(paths,candidate,shape,w)
    _,predicted=candidate_chunk(arrays,w);output=tmp_path/'mapped.dat';(predicted+.01).tofile(output)
    err=full_field_error([candidate,output]+paths,shape,w,np.arange(1.,5.))
    assert not err['prediction_error_resolved']
