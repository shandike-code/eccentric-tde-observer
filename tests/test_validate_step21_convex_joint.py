from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_convex_joint as valid
from operations import convex_joint_fields as fields
from test_recover_step21_control_windows import templates,endpoints


def test_sequence_full_half_then_ten_control_maps():
    events=[]
    def probe():events.extend([('control',1),('half',1)]);return True
    result=valid.conditional_sequence(probe,lambda n:events.append(('control',n)),lambda n:events.append(('pair',n)) or True)
    assert events==[('control',1),('half',1),('control',2),('pair',2)]+[('control',n) for n in range(3,11)]+[('pair',10)]
    assert result=='convex_joint_validation_complete_requires_review'


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


def data(tmp_path):
    shape=(256,2,3);x=np.ones(shape);x[200]=np.nextafter(0.,1.);q=x.copy();z=x.copy();q[:128]=2.;z[:128]=3.;paths=[]
    for i,a in enumerate((x,q,z)):
        p=tmp_path/f'{i}.dat';a.tofile(p);paths.append(p)
    return shape,x,q,z,paths


def test_audited_convex_writer_and_half_identity(tmp_path):
    shape,x,q,z,paths=data(tmp_path);fp=tmp_path/'full.dat';hp=tmp_path/'half.dat';uv=[.2232383685126496,.2344820251208071]
    fields.write_candidates(paths,uv,fp,hp,shape,selected=(0,));f=np.fromfile(fp).reshape(shape);h=np.fromfile(hp).reshape(shape)
    np.testing.assert_array_equal(f[:128],(1-sum(uv))*x[:128]+uv[0]*q[:128]+uv[1]*z[:128]);np.testing.assert_array_equal(h[:128],.5*x[:128]+.5*f[:128]);np.testing.assert_array_equal(f[128:],x[128:]);np.testing.assert_array_equal(h[128:],x[128:])


@pytest.mark.parametrize('bad',['coefficient','outside','negative','nan','truncate','existing','stop'])
def test_writer_never_publishes_invalid_half(tmp_path,bad):
    shape,x,q,z,paths=data(tmp_path);fp=tmp_path/'full.dat';hp=tmp_path/'half.dat';uv=[.2,.3];callback=lambda:None
    if bad=='coefficient':uv=[-.1,.3]
    if bad in ('outside','negative','nan'):
        q[200 if bad=='outside' else 0,0,0]={'outside':1.,'negative':-1.,'nan':np.nan}[bad];q.tofile(paths[1])
    if bad=='truncate':paths[1].write_bytes(b'')
    if bad=='existing':fp.write_bytes(b'keep')
    if bad=='stop':
        def callback():raise valid.reused.Stopped('stop')
    with pytest.raises((ValueError,FileExistsError,valid.reused.Stopped)):fields.write_candidates(paths,uv,fp,hp,shape,selected=(0,),checkpoint=callback)
    assert not hp.exists()
    if bad=='existing':assert fp.read_bytes()==b'keep'
    else:assert not fp.exists()


def test_prediction_discrepancy_cannot_pass():
    pred={'l2_ratio':.7477,'linf_ratio':.9946};c={'fixed_scale_l2_ratios':[1,.7477], 'fixed_scale_linf_ratios':[1,.9946]}
    assert all(fields.prediction_checks(c,pred).values());c['fixed_scale_linf_ratios'][1]+=.001
    assert not fields.prediction_checks(c,pred)['predicted_full_linf_reproduced']
