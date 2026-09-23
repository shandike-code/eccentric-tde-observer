import numpy as np
import pytest
from operations import formal_source_split as split


def test_component_selection_preserves_radiation_and_does_not_mutate_material():
    f={key:np.full((3,2),i+1.) for i,key in enumerate(split.FIELDS.values())}
    f['outer']=np.arange(12.).reshape(3,2,2);before={k:v.copy() for k,v in f.items()}
    for component,active in split.FIELDS.items():
        r=split.component_fields(f,component)
        assert r['outer'] is f['outer'] and r[active] is f[active]
        assert all(np.count_nonzero(r[k])==0 for k in split.FIELDS.values() if k!=active)
    assert all(np.array_equal(v,before[k]) for k,v in f.items())
    with pytest.raises(ValueError,match='undeclared'):split.component_fields(f,'renormalized')


def test_operator_restored_even_on_worker_failure():
    m=split.native.phase7b7f.phase7b7e;old=m._local_fields
    with pytest.raises(RuntimeError):
        with split.component_operator('emission'):
            assert m._local_fields is not old
            raise RuntimeError('injected')
    assert m._local_fields is old
