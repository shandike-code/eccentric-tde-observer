from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_wide_plane as valid
from test_recover_step21_control_windows import templates,endpoints


def test_schedule_is_exactly_eleven_maps_and_two_pairs():
    events=[]
    def validate():events.append(('map',1));return True
    result=valid.conditional_sequence(validate,lambda n:events.append(('map',n)),lambda n:events.append(('feedback',n)) or True)
    assert events==[('map',n) for n in (1,2,3)]+[('feedback',3)]+[('map',n) for n in range(4,12)]+[('feedback',11)]
    assert result=='wide_plane_validation_complete_requires_review'


def test_failed_true_map_forbids_feedback_and_more_maps():
    bad=lambda *_:pytest.fail('unexpected downstream work')
    assert valid.conditional_sequence(lambda:False,bad,bad)=='true_map_not_validated'


def test_failed_first_feedback_forbids_second_window():
    maps=[];feedback=[]
    def pair(n):feedback.append(n);return False
    assert valid.conditional_sequence(lambda:True,maps.append,pair)=='first_control_pair_not_stable'
    assert maps==[2,3] and feedback==[3]


def test_partial_map_exception_forbids_feedback():
    def fail(n):raise valid.reused.Stopped('partial')
    with pytest.raises(valid.reused.Stopped):
        valid.conditional_sequence(lambda:True,fail,lambda n:pytest.fail('partial map feedback'))


def test_unchanged_real_factory_builds_forbidden_acceptance_control():
    finite,zero=templates();es,rows=endpoints();saved=deepcopy(zero)
    p=valid.recovery.control_protocol(finite,zero,valid.ROOT/'outputs/hpc/test-wide',es,rows,{'path':'right-trial'}, {}, {})
    assert p['sources']['trial_material']['path']=='right-trial'
    assert zero==saved and p['authorization']['zero_displacement_control'] is True
    assert p['authorization']['accept_material_step'] is False
    assert p['acceptance_gates']==zero['acceptance_gates'] and p['formal_state_gates']==zero['formal_state_gates']


def prediction(r):
    return dict(feasible=True,actual_map_performed=False,candidate_written=False,accepted_material_step=False,
        rounds=[dict(result=dict(predicted_ratio=r,uv=[0.,0.],coefficients=[0.,0.,1.],gates={'positive':True}))])


def test_selects_audited_best_not_first_or_failed_candidate():
    ps={'bad':{'feasible':False},'b':prediction(.75),'a':prediction(.7)}
    audit=dict(selected='a',cases={n:dict(cost_eligible=True,effective_uv=[0.,0.],predicted_ratio=r) for n,r in [('b',.75),('a',.7)]})
    assert valid.select_case(ps,audit)=='a'
    audit['selected']='b'
    with pytest.raises(RuntimeError,match='selection differs'):valid.select_case(ps,audit)


def test_no_cost_eligible_candidate_refused():
    with pytest.raises(RuntimeError,match='no audited'):valid.select_case({'weak':prediction(.98)},{})


def test_six_state_writer_and_actual_map_comparison(tmp_path,monkeypatch):
    monkeypatch.setattr(valid.reused,'checkpoint',lambda:None)
    shape=(18,2,3);operator=np.array([.8,.9,.95]);fixed=np.array([3.,4.,5.]);rng=np.random.default_rng(11)
    xs=[fixed+rng.uniform(.1,.5,shape) for _ in range(3)]
    ys=[fixed+operator*(x-fixed) for x in xs];paths=[]
    for i,x in enumerate(xs+ys):
        p=tmp_path/f'{i}.dat';x.tofile(p);paths.append(p)
    uv=np.array([.1,.2]);dest=tmp_path/'candidate.dat';valid.write_candidate(paths,dest,shape,uv)
    q=np.fromfile(dest).reshape(shape);expected,predicted=valid.positive_pair(xs+ys,uv)
    np.testing.assert_array_equal(q,expected)
    actual=fixed+operator*(q-fixed);mapped=tmp_path/'actual.dat';actual.tofile(mapped)
    report=valid.compare_fields(paths+[dest,mapped],shape,uv)
    assert report['max_error_over_field']<1e-15 and len(report['slabs'])==2
    q[0,0,0]+=1e-3;q.tofile(dest)
    with pytest.raises(RuntimeError,match='stored candidate differs'):valid.compare_fields(paths+[dest,mapped],shape,uv)
    with pytest.raises(FileExistsError):valid.write_candidate(paths,dest,shape,uv)


def test_six_state_negative_candidate_never_published(tmp_path,monkeypatch):
    monkeypatch.setattr(valid.reused,'checkpoint',lambda:None);paths=[];shape=(1,2,3)
    for i,n in enumerate((1.,2.,4.,2.,3.,5.)):
        p=tmp_path/f'{i}.dat';np.full(shape,n).tofile(p);paths.append(p)
    out=tmp_path/'candidate.dat'
    with pytest.raises(ArithmeticError,match='negative'):valid.write_candidate(paths,out,shape,[3.,0.])
    assert not out.exists()


def test_map_limit_enforced_before_dispatch(monkeypatch):
    monkeypatch.setattr(valid.recovery.original,'map_once',lambda *args:pytest.fail('over-budget map'))
    with pytest.raises(RuntimeError,match='eleven-map'):valid.map_once(None,None,{'history':[{}]*11})
