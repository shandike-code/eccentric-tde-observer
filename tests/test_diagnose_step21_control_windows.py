import numpy as np
import pytest
from operations import diagnose_step21_control_windows as s

def test_long_window_uses_vector_difference_not_equal_norms():
    a=np.ones(8);b=-a;r={'previous':a,'final':a};q={'previous':b,'final':b}
    d=s.window_comparison(q,r,a,[1.,1.]);assert not d['passed']
    np.testing.assert_allclose(d['vector_difference_over_frozen_r20_norms']['final_vs_final'],[2,2,2])

def test_cross_endpoint_pair_cannot_hide_large_change():
    a=np.ones(8);old={'previous':a,'final':a*1.1};new={'previous':a,'final':a}
    assert not s.window_comparison(new,old,a,[1,1])['passed']
    assert s.window_comparison(new,new,a,[1,1])['passed']

@pytest.mark.parametrize('bad',[{}, {'final':np.ones(8)}])
def test_missing_endpoint_rejected(bad):
    with pytest.raises(ValueError):s.window_comparison(bad,{'previous':np.ones(8),'final':np.ones(8)},np.ones(8),[1,1])

def test_budget_and_stop_before_map(monkeypatch,tmp_path):
    monkeypatch.setattr(s.driver,'run_one_map',lambda *a:pytest.fail('unexpected work'))
    with pytest.raises(RuntimeError,match='hard limit'):s.map_once(tmp_path,{}, {'history':[{}]*16})
    monkeypatch.setattr(s.pipeline,'STOP',True)
    with pytest.raises(s.reused.Stopped):s.map_once(tmp_path,{}, {'history':[]})

def test_reference_remains_frozen_and_no_promotion():
    a=np.ones(8);old={'previous':a,'final':a};new={k:x*1.0001 for k,x in old.items()}
    before=a.copy();d=s.window_comparison(new,old,a,[1,2]);assert d['passed'] and not d['baseline_replaced'] and not d['strict_error_bound'];np.testing.assert_array_equal(a,before)
