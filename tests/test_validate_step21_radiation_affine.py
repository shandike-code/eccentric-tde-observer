from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_radiation_affine as step


def prediction():
    return {'actual_map_performed':False,'actual_candidate_residual':None,'algebraic_feasibility':True,
            'algebraic_gates':{'positive':True},'direction':{'selected_forward_fraction':3.,'exact_positive_upper':100.}}


@pytest.mark.parametrize('kind',['measured','rejected','nan','lower','upper','positive'])
def test_rejects_unmeasured_scan_misclassification_and_invalid_coefficients(kind):
    p=prediction();assert step.fraction(p)==3.
    if kind=='measured':p['actual_map_performed']=True
    if kind=='rejected':p['algebraic_gates']['positive']=False
    if kind=='nan':p['direction']['selected_forward_fraction']=float('nan')
    if kind=='lower':p['direction']['selected_forward_fraction']=1.
    if kind=='upper':p['direction']['selected_forward_fraction']=97.
    if kind=='positive':p['direction']['exact_positive_upper']=3.
    with pytest.raises(ValueError):step.fraction(p)


def test_full_field_error_detects_mismatch_despite_equal_scalar_residual(tmp_path):
    shape=(4,2,3);b=np.ones(shape)*10;c=b+.1;q=b+.2;pred=c+2*(c-b)
    actual=pred.copy();actual[0,0,0]=q[0,0,0]-.1
    paths=[tmp_path/k for k in ('b','c','q','actual')]
    for p,a in zip(paths,(b,c,q,actual)):a.tofile(p)
    before=[p.read_bytes() for p in paths]
    report=step.compare_fields(paths,shape,3.,chunk=2)
    assert report['max_error_over_actual_change']>1.9
    row={'residual':report['actual_global_residual'],'boundary_l1':0.,'boundary_bolometric':0.,'maximum_worker_rss_mib':1000}
    assert not step.measured_checks(row,1.,report)['prediction_error_below_tenth_actual_change']
    assert [p.read_bytes() for p in paths]==before


def test_exact_affine_map_matches_all_cells_and_original_global_norm(tmp_path):
    shape=(3,4,2);b=np.arange(24,dtype=float).reshape(shape)+10;c=b+.25;q=b+.5;actual=c+2*(c-b)
    paths=[tmp_path/k for k in ('b','c','q','actual')]
    for p,a in zip(paths,(b,c,q,actual)):a.tofile(p)
    r=step.compare_fields(paths,shape,3.,chunk=2)
    assert r['max_error_over_field']==r['l2_error_over_actual_field']==0.
    assert r['actual_global_residual']==np.max(abs(actual-q))/max(actual.max(),q.max())
    assert [(s['start'],s['stop']) for s in r['slabs']]==[(0,2),(2,3)]


@pytest.mark.parametrize('bad',['negative','nan'])
def test_invalid_actual_field_is_rejected(tmp_path,bad):
    a=np.ones((2,2,2));paths=[tmp_path/str(i) for i in range(4)]
    for p in paths:a.tofile(p)
    a[0,0,0]=-1 if bad=='negative' else np.nan;a.tofile(paths[-1])
    with pytest.raises(ValueError):step.compare_fields(paths,a.shape,2.)


def test_all_validations_precede_feedback_and_failed_case_is_skipped():
    seen=[]
    def v(n):seen.append('v:'+n);return n!='thermal'
    def f(n):seen.append('f:'+n);return 'baseline_stable' if n=='control' else 'diagnostic_complete'
    assert step.conditional_sequence(v,f)=='bounded_affine_diagnostic_complete_requires_review'
    assert seen==['v:control','v:thermal','v:population','f:control','f:population']


@pytest.mark.parametrize('failure',['map','feedback','domain'])
def test_control_and_physical_domain_failures_stop_dependent_work(failure):
    seen=[]
    def v(n):return not(failure=='map' and n=='control')
    def f(n):
        seen.append(n)
        if n=='control':return 'baseline_unstable' if failure=='feedback' else 'baseline_stable'
        return 'physical_domain_rejected'
    step.conditional_sequence(v,f)
    assert seen==([] if failure=='map' else ['control'] if failure=='feedback' else ['control','thermal'])


def test_budget_and_stop_checked_before_dispatch(monkeypatch,tmp_path):
    assert step.LIMITS==dict.fromkeys(step.NAMES,3)
    monkeypatch.setattr(step.driver,'run_one_map',lambda *args:pytest.fail('unexpected new map'))
    with pytest.raises(RuntimeError,match='hard limit'):step.map_once(tmp_path,{}, {'history':[{}, {}, {}]})
    monkeypatch.setattr(step.pipeline,'STOP',True)
    with pytest.raises(step.reused.Stopped):step.map_once(tmp_path,{}, {'history':[]})
