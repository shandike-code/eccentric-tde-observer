from copy import deepcopy
import numpy as np
import pytest
from operations.radiation_history_diagnostic import identical_material, require_ownership, difference_metrics


def test_identical_norms_can_hide_large_vector_difference():
    a=np.ones(8); r=difference_metrics(a,-a,np.array([1.,3.]))
    assert r['norms']['l2']==pytest.approx(np.sqrt(32))
    assert r['norms']['mass_weighted']==pytest.approx(4)
    assert sum(r['cell_squared_l2'])==pytest.approx(r['norms']['l2']**2)
    assert sum(r['component_squared_mass_norm'])==pytest.approx(r['norms']['mass_weighted']**2)
    assert not r['strict_error_bound']


def test_matching_all_material_fields_including_metadata():
    a={'encoded_state':np.ones(8),'temperature_k':np.ones(2),'phase_index':np.array(1367)}
    identical_material(a,deepcopy(a))
    b=deepcopy(a);b['temperature_k'][1]+=1
    with pytest.raises(ValueError,match='temperature_k'):identical_material(a,b)
    b=deepcopy(a);b['extra']=np.array(0)
    with pytest.raises(ValueError,match='inventory'):identical_material(a,b)


def test_matching_nonfinite_material_is_rejected():
    a={'encoded_state':np.array([np.inf])}
    with pytest.raises(ValueError,match='nonfinite'):identical_material(a,a)


def blocks():
    return [{'block_index':0,'core_group_start':0,'core_group_stop':3},
            {'block_index':1,'core_group_start':3,'core_group_stop':5}]


def test_exact_frequency_ownership():
    require_ownership(blocks(),groups=5,count=2)


@pytest.mark.parametrize('index,start,stop',[(1,2,5),(1,4,5),(1,3,6),(0,3,5)])
def test_overlap_gap_out_of_range_or_duplicate_block_rejected(index,start,stop):
    b=blocks();b[1]={'block_index':index,'core_group_start':start,'core_group_stop':stop}
    with pytest.raises(ValueError):require_ownership(b,groups=5,count=2)


@pytest.mark.parametrize('bad',[np.nan,np.inf])
def test_nonfinite_residual_is_not_sanitized(bad):
    a=np.ones(8);a[0]=bad
    with pytest.raises(ValueError):difference_metrics(a,np.zeros(8),np.ones(2))


def test_feedback_reassembly_rejects_wrong_half_grid(tmp_path):
    from operations.audit_half_step_histories import verify_feedback, assembly
    full=assembly._zero(4096)
    path=tmp_path/'zero.npz';np.savez(path,**full)
    class Snap:
        def save(self,path,sha):return tmp_path/'zero.npz'
    rows=[{'block_index':i,'core_group_start':128*i,'core_group_stop':min(128*(i+1),9632),
           'partial_path':'zero.npz','partial_sha256':'synthetic'} for i in range(76)]
    fb={}
    for k,v in full.items():
        parent=v.reshape(256,16,*v.shape[1:]).mean(axis=1)
        fb.update({k:v,'parent_'+k:parent,'half_'+k:parent[:128].copy()})
    verify_feedback({'completed_blocks':rows},fb,Snap())
    fb['half_atomic_rate_heating_erg_s_cm3'][96]=1
    with pytest.raises(RuntimeError,match='depth mapping'):
        verify_feedback({'completed_blocks':rows},fb,Snap())
