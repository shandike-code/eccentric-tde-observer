from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_seven_refresh_short as valid
from operations import seven_short_global_fields as fields
from test_recover_step21_control_windows import templates,endpoints


def arrays(tmp_path):
    shape=(2304,2,3);x=np.ones(shape);x[2200]=np.nextafter(0.,1.)
    path=tmp_path/'source.dat';x.tofile(path);repl={}
    for i in (3,11):
        p=tmp_path/f'block{i}.npz';np.savez(p,candidate=np.full((896,2,3),2.));repl[i]=p
    return shape,x,path,repl


def test_saved_candidates_untouched_subnormal_and_affine_operator(tmp_path):
    shape,x,p,repl=arrays(tmp_path);qpath=tmp_path/'q.dat';hpath=tmp_path/'h.dat'
    fields.write_candidates(p,repl,qpath,hpath,shape,centers=(3,11),fraction=.63)
    q=np.fromfile(qpath).reshape(shape);h=np.fromfile(hpath).reshape(shape)
    assert np.array_equal(q[1920:],x[1920:]) and np.array_equal(h[1920:],x[1920:])
    assert np.array_equal(q[:896],(1-.63)*x[:896]+.63*2.)
    assert np.array_equal(h[:896],.5*x[:896]+.5*q[:896])
    # 使用已知线性全域算子，输出含邻频耦合；半步检验必须回收仿射性。
    op=lambda a:.25*a+.05*np.roll(a,1,axis=0)+1.
    paths=[]
    for i,a in enumerate((x,op(x),q,op(q),h,op(h))):
        target=tmp_path/f'field{i}.dat';a.tofile(target);paths.append(target)
    report=fields.validate(paths,shape,blocks=(0,1,2,3,4,5,6,8,9,10,11,12,13,14))
    assert report['all_groups_evaluated']==2304 and report['fixed_scale_l2_ratios'][3]<1e-14
    assert sum(row['group_count'] for row in report['slabs'])==2304
    assert report['slabs'][28]['output_change_linf']>0  # 未改输入的邻块输出会改变
    bad=np.fromfile(paths[2]).reshape(shape);bad[2200]=1.;bad.tofile(paths[2])
    with pytest.raises(ValueError,match='unselected'):fields.validate(paths,shape,blocks=(0,1,2,3,4,5,6,8,9,10,11,12,13,14))


@pytest.mark.parametrize('bad',['negative','nan','shape','inventory','existing','stop'])
def test_candidate_failure_preserves_source_and_never_completes(tmp_path,bad):
    shape,x,p,repl=arrays(tmp_path);original=p.read_bytes();q=tmp_path/'q.dat';h=tmp_path/'h.dat'
    callback=lambda:None
    if bad in ('negative','nan','shape'):
        a=np.ones((896,2,3) if bad!='shape' else (895,2,3));a.flat[0]=-1. if bad=='negative' else (np.nan if bad=='nan' else 1.)
        np.savez(repl[3],candidate=a)
    if bad=='inventory':repl.pop(3)
    if bad=='existing':q.write_bytes(b'keep')
    if bad=='stop':
        def callback():raise valid.reused.Stopped('stop')
    with pytest.raises((ValueError,FileExistsError,valid.reused.Stopped)):
        fields.write_candidates(p,repl,q,h,shape,centers=(3,11),fraction=.63,checkpoint=callback)
    assert p.read_bytes()==original and not h.exists()
    if bad=='existing':assert q.read_bytes()==b'keep'
    else:assert not q.exists()


def test_sequence_full_half_then_ten_control_maps():
    events=[]
    def probe():events.extend([('control',1),('half',1)]);return True
    result=valid.conditional_sequence(probe,lambda n:events.append(('control',n)),lambda n:events.append(('pair',n)) or True)
    assert events==[('control',1),('half',1),('control',2),('pair',2)]+[('control',n) for n in range(3,11)]+[('pair',10)]
    assert result=='seven_refresh_short_validation_complete_requires_review'


def test_failed_gate_never_dispatches_later_window():
    bad=lambda *_:pytest.fail('unauthorized downstream work')
    assert valid.conditional_sequence(lambda:False,bad,bad)=='true_map_not_validated'
    maps=[];pairs=[]
    assert valid.conditional_sequence(lambda:True,maps.append,lambda n:pairs.append(n) or False)=='first_control_pair_not_stable'
    assert maps==[2] and pairs==[2]
    assert valid.conditional_sequence(lambda:True,lambda n:None,lambda n:n==2)=='second_control_pair_not_stable'


def test_stop_prevents_feedback_and_map_budget_guard(monkeypatch):
    def stop(_):raise valid.reused.Stopped('partial')
    with pytest.raises(valid.reused.Stopped):valid.conditional_sequence(lambda:True,stop,lambda _:pytest.fail('partial feedback'))
    monkeypatch.setattr(valid.recovery.original,'map_once',lambda *a:pytest.fail('over budget'))
    with pytest.raises(RuntimeError,match='ten-map'):valid.map_once(None,None,{'history':[{}]*10})


def test_full_linf_neighbor_growth_and_half_nonlinearity_fail():
    report={'fixed_scale_l2_ratios':[1.,.8,.9,1e-8],'fixed_scale_linf_ratios':[1.,.9,.95,1e-8]}
    old={'residual':1e-5,'boundary_l1':1e-5,'boundary_bolometric':1e-5}
    assert all(fields.checks(report,old,old,old).values())
    report['fixed_scale_linf_ratios'][1]=1.01
    assert not fields.checks(report,old,old,old)['full_linf_nonincrease']
    report['fixed_scale_l2_ratios'][3]=2e-6
    assert not fields.checks(report,old,old,old)['independent_half_affinity']


def test_factory_uses_zero_trial_and_disallows_material_acceptance():
    finite,zero=templates();es,rows=endpoints();before=deepcopy(zero)
    p=valid.recovery.control_protocol(finite,zero,valid.ROOT/'outputs/hpc/test-block-global',es,rows,{'path':'right-trial'}, {}, {})
    assert zero==before and p['sources']['trial_material']['path']=='right-trial'
    assert p['authorization']['zero_displacement_control'] is True
    assert p['authorization']['accept_material_step'] is False


@pytest.mark.parametrize('centers',[(3,5),(0,11),(3,18),(3,3),(True,11)])
def test_overlapping_or_outside_joint_cores_rejected(centers):
    with pytest.raises(ValueError):fields.intervals(centers,2304)


def test_cost_gate_requires_twenty_percent():
    report={'fixed_scale_l2_ratios':[1.,.81,.9,1e-8],'fixed_scale_linf_ratios':[1.,.9,.95,1e-8]}
    old={'residual':1e-5,'boundary_l1':1e-5,'boundary_bolometric':1e-5}
    assert fields.GATES['full_l2_ratio_max']==.8
    assert not fields.checks(report,old,old,old)['full_l2_benefit']

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



@pytest.mark.parametrize('t',[0.,-1.,1.01,np.nan,np.inf])
def test_bad_fraction_never_writes(t,tmp_path):
    with pytest.raises(ValueError,match='fraction'):fields.write_candidates(None,{},tmp_path/'x',tmp_path/'h',(1,1,1),fraction=t)


