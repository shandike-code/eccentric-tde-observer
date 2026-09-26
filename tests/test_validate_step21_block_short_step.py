from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_block_short_step as valid
from operations import short_step_global_fields as fields
from test_validate_step21_heating_blocks import arrays


def bundle():
    pair=[{'path':'x'},{'path':'y'}];decl={'paths':pair+[{},{}],'controls':valid.scan.CONTROLS}
    pred=dict(rd=-.5,dd=1.,linf_upper=.1,choice={'fraction':.09},checks={'a':True},eligible_for_independent_review=True,
              actual_map_performed=False,candidate_written=False,accepted_material_step=False)
    pred['choice']['fraction']=.9*.1
    audit={k:deepcopy(pred[k]) for k in ('choice','checks','linf_upper','eligible_for_independent_review')}
    return pair,decl,pred,audit


def test_reviewed_fraction_is_exactly_registered():
    pair,d,p,a=bundle();assert valid.reviewed_fraction(d,p,a,pair)==.9*.1


@pytest.mark.parametrize('case',['source','controls','audit','ineligible','optimum','already_run'])
def test_changed_source_coefficient_or_authorization_rejected(case):
    pair,d,p,a=bundle();d=deepcopy(d)
    if case=='source':d['paths']=[{},{}]
    if case=='controls':d['controls']['step_safety']=1.
    if case=='audit':a['choice']['fraction']=.2
    if case=='ineligible':p['eligible_for_independent_review']=False
    if case=='optimum':p['rd']=-.001
    if case=='already_run':p['actual_map_performed']=True
    with pytest.raises(RuntimeError):valid.reviewed_fraction(d,p,a,pair)


def test_written_short_step_and_half_preserve_all_untouched_subnormal_values(tmp_path):
    shape,x,p,repl=arrays(tmp_path);q=tmp_path/'short.dat';h=tmp_path/'half.dat';t=.008802697738053965
    fields.write_candidates(p,repl,q,h,shape,fraction=t,blocks=(0,1))
    qa=np.fromfile(q).reshape(shape);ha=np.fromfile(h).reshape(shape)
    assert np.array_equal(qa[:256],(1-t)*x[:256]+t*2.)
    assert np.array_equal(ha[:256],.5*x[:256]+.5*qa[:256])
    assert np.array_equal(qa[256:],x[256:]) and np.array_equal(ha[256:],x[256:])


@pytest.mark.parametrize('t',[0.,-1.,1.01,np.nan,np.inf])
def test_bad_fraction_never_writes(t,tmp_path):
    with pytest.raises(ValueError,match='fraction'):fields.write_candidates(None,{},tmp_path/'x',tmp_path/'h',(1,1,1),fraction=t)


def test_conditional_budget_and_failed_gate():
    events=[]
    def first():events.extend([('control',1),('half',1)]);return True
    status=valid.conditional_sequence(first,lambda n:events.append(('control',n)),lambda n:events.append(('feedback',n)) or True)
    assert status=='short_step_validation_complete_requires_review'
    assert len([x for x in events if x[0]!='feedback'])==11
    assert [n for k,n in events if k=='feedback']==[2,10]
    no=lambda *_:pytest.fail('work after failed validation')
    assert valid.conditional_sequence(lambda:False,no,no)=='true_map_not_validated'
