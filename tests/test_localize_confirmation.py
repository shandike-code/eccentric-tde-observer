import numpy as np
import pytest
from operations.localize_confirmation import attribution, ownership
from diagnostics.material_energy_ledger import parent_layer_contributions, fold_to_material_layers


def test_signed_attribution_retains_frequency_cancellation():
    p=np.array([[10.,10.],[10.,10.]])
    f=p+np.array([[3.,-3.],[-2.,2.]])
    a=attribution(p,f,np.array([1.,2.]))
    assert a['signed_blocks'][1] < 0
    assert np.isclose(a['signed_blocks'].sum(),a['ratio'])
    assert np.isclose(a['gross_blocks'].sum()/a['ratio'],5.)


def test_fold_uses_mirrored_sixteen_subcells_not_contiguous_thirty_two():
    v=np.zeros(4096);v[106*16]=2;v[(255-106)*16+15]=3
    c=fold_to_material_layers(parent_layer_contributions(v))
    assert c[106]==5 and c.sum()==5


@pytest.mark.parametrize('rows',[
 [{'block_index':0,'core_group_start':0,'core_group_stop':2}],
 [{'block_index':0,'core_group_start':0,'core_group_stop':3},{'block_index':1,'core_group_start':2,'core_group_stop':4}],
 [{'block_index':0,'core_group_start':0,'core_group_stop':2},{'block_index':0,'core_group_start':2,'core_group_stop':4}],
])
def test_rejects_missing_overlapping_or_duplicate_ownership(rows):
    with pytest.raises(ValueError):ownership(rows,4)


def test_valid_ownership():
    ownership([{'block_index':0,'core_group_start':0,'core_group_stop':2},{'block_index':1,'core_group_start':2,'core_group_stop':4}],4)


@pytest.mark.parametrize('width',[[0.,1.],[1.],[np.nan,1.]])
def test_invalid_width_rejected(width):
    with pytest.raises(ValueError):attribution(np.ones((2,2)),np.ones((2,2)),width)


def test_single_process_audit_fits_default_allocation(monkeypatch):
    from operations.localize_confirmation import require_audit_allocation
    monkeypatch.setenv('SLURM_JOB_ID','synthetic')
    monkeypatch.setenv('SLURM_CPUS_PER_TASK','4')
    monkeypatch.setenv('SLURM_MEM_PER_NODE','16384')
    require_audit_allocation()
    monkeypatch.setenv('SLURM_MEM_PER_NODE','4096')
    with pytest.raises(RuntimeError):require_audit_allocation()
