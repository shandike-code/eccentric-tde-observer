from copy import deepcopy
import numpy as np
import pytest
from operations.scan_late_population_arrays import frequency_stats, check_population_source


def source():
    pair=[dict(sha256=s) for s in ('a6addd2bd50f55ebc222bfbcc4d992f8c34d518ddc96e65f1b37b3e074a41151','b37287a5418eb6c34bb8cd1e83f2509f630ca69d9b3f27fa39c962a2ecdc3c8a')]
    return dict(source_job_id=79151,refreshed_halo=True,source_run='outputs/hpc/step21-late-direction-windows-20260928',
        frozen_material_case='population',material_relaxation=1/256,original_r20_unchanged=True,physical_dt_unchanged=True,
        cases={'population':dict(input=pair[0],output=pair[1])},blocks=[37,44],source_pair=pair)


def test_scan_uses_full_signed_difference_not_difference_of_norms():
    a=np.array([[1.,2.],[3.,4.]]);b=np.array([[2.,1.],[3.,6.]])
    assert frequency_stats(a,b)==dict(square=6.,maximum=2.,minimum_input=1.,minimum_output=1.)


@pytest.mark.parametrize('bad',[np.array([[np.nan]]),np.array([[np.inf]]),np.array([[-1.]]),np.ones((2,2))])
def test_invalid_arrays_are_rejected(bad):
    with pytest.raises(ValueError):frequency_stats(np.ones((1,1)),bad)


@pytest.mark.parametrize('key,value',[('source_job_id',78161),('refreshed_halo',False),('source_run','old'),('frozen_material_case','control'),('material_relaxation',0.),('original_r20_unchanged',False),('physical_dt_unchanged',False),('blocks',[24,48])])
def test_only_this_population_experiment_is_allowed(key,value):
    d=source();saved=deepcopy(d);check_population_source(d);assert d==saved
    d[key]=value
    with pytest.raises(RuntimeError):check_population_source(d)


def test_crossed_actual_pair_or_wrong_material_label_is_rejected():
    d=source();d['cases']['population']['input'],d['cases']['population']['output']=d['cases']['population']['output'],d['cases']['population']['input']
    with pytest.raises(RuntimeError):check_population_source(d)
    d=source();d['cases']['control']=d['cases'].pop('population')
    with pytest.raises(RuntimeError):check_population_source(d)
