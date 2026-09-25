from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_positive_plane as step


def prediction():
    return dict(actual_map_performed=False,candidate_written=False,accepted_material_step=False,feasible=True,
                rounds=[{'result':{'uv':[-2.,.5],'coefficients':[.5,-2.,2.5],'gates':{'positive':True}}}])


@pytest.mark.parametrize('kind',['measured','written','accepted','failed','negative','nan','shape','cap','weights'])
def test_rejects_wrong_prediction_identity_or_coefficients(kind):
    p=prediction();np.testing.assert_array_equal(step.coefficients(p),[-2.,.5])
    if kind=='measured':p['actual_map_performed']=True
    if kind=='written':p['candidate_written']=True
    if kind=='accepted':p['accepted_material_step']=True
    if kind=='failed':p['feasible']=False
    if kind=='negative':p['rounds'][0]['result']['gates']['positive']=False
    if kind=='nan':p['rounds'][0]['result']['uv'][0]=np.nan
    if kind=='shape':p['rounds'][0]['result']['uv'].append(1.)
    if kind=='cap':p['rounds'][0]['result'].update(uv=[-100.,0.],coefficients=[0.,-100.,101.])
    if kind=='weights':p['rounds'][0]['result']['coefficients'][0]+=.01
    with pytest.raises(ValueError):step.coefficients(p)


def fixture_states(tmp_path):
    shape=(3,2,4);x=np.arange(24,dtype=float).reshape(shape)+10
    values=[x+i*.125 for i in range(4)];paths=[tmp_path/f'x{i}.dat' for i in range(4)]
    for p,a in zip(paths,values):a.tofile(p)
    return shape,values,paths


def test_writes_exact_audited_formula_and_compares_true_affine_map(tmp_path):
    shape,values,paths=fixture_states(tmp_path);uv=[-2.,.5]
    q,p=step.positive_pair(values,uv);destination=tmp_path/'q.dat';actual=tmp_path/'actual.dat'
    before=[p.read_bytes() for p in paths]
    assert step.write_candidate(paths,destination,shape,uv,chunk=2)==q.min()
    np.testing.assert_array_equal(np.fromfile(destination).reshape(shape),q)
    p.tofile(actual);r=step.compare_fields(paths+[destination,actual],shape,uv,chunk=2)
    assert r['max_error_over_field']==r['l2_error_over_actual_field']==0
    assert r['actual_global_residual']==np.max(abs(p-q))/max(p.max(),q.max())
    assert [(s['start'],s['stop']) for s in r['slabs']]==[(0,2),(2,3)]
    assert [p.read_bytes() for p in paths]==before
    with pytest.raises(FileExistsError):step.write_candidate(paths,destination,shape,uv)


@pytest.mark.parametrize('field',['candidate','actual','basis'])
def test_modified_field_is_detected(tmp_path,field):
    shape,values,paths=fixture_states(tmp_path);uv=[-2.,.5];q,p=step.positive_pair(values,uv)
    qpath=tmp_path/'q.dat';apath=tmp_path/'actual.dat';q.tofile(qpath);p.tofile(apath)
    if field=='candidate':
        q.flat[0]+=.01;q.tofile(qpath)
        with pytest.raises(RuntimeError,match='stored candidate'):step.compare_fields(paths+[qpath,apath],shape,uv)
    elif field=='basis':
        values[0].flat[0]=np.nan;values[0].tofile(paths[0])
        with pytest.raises(ValueError):step.compare_fields(paths+[qpath,apath],shape,uv)
    else:
        p.flat[0]+=1;p.tofile(apath)
        r=step.compare_fields(paths+[qpath,apath],shape,uv)
        row=dict(residual=r['actual_global_residual'],boundary_l1=0.,boundary_bolometric=0.,maximum_worker_rss_mib=10)
        assert not step.measured_checks(row,1.,r)['prediction_error_below_tenth_actual_change']


@pytest.mark.parametrize('which',[0,3])
def test_negative_q_or_prediction_aborts_without_publishing(tmp_path,which):
    shape=(2,2,2);values=[np.ones(shape) for _ in range(4)];uv=[0.,-1.]
    if which==0:values[0]*=3 # q=2*x2-x0 <0
    else:values[3]*=.1 # p=2*x3-x1 <0
    paths=[tmp_path/f'x{i}' for i in range(4)]
    for p,a in zip(paths,values):a.tofile(p)
    dest=tmp_path/'q.dat'
    with pytest.raises(ArithmeticError,match='negative'):step.write_candidate(paths,dest,shape,uv)
    assert not dest.exists()


def test_stop_before_candidate_chunk_and_map_budget(monkeypatch,tmp_path):
    shape,_,paths=fixture_states(tmp_path)
    monkeypatch.setattr(step.pipeline,'STOP',True)
    with pytest.raises(step.reused.Stopped):step.write_candidate(paths,tmp_path/'q.dat',shape,[-2.,.5])
    assert not (tmp_path/'q.dat').exists()
    monkeypatch.setattr(step.pipeline,'STOP',False)
    monkeypatch.setattr(step.driver,'run_one_map',lambda *a:pytest.fail('unexpected worker'))
    with pytest.raises(RuntimeError,match='hard limit'):step.map_once(tmp_path,{}, {'history':[{}, {}, {}]})


def test_conditional_batch_and_control_failure():
    seen=[]
    def validate(n):seen.append('v:'+n);return n!='thermal'
    def feedback(n):seen.append('f:'+n);return 'baseline_stable' if n=='control' else 'diagnostic_complete'
    assert step.conditional_sequence(validate,feedback)=='bounded_positive_plane_diagnostic_complete_requires_review'
    assert seen==['v:control','v:thermal','v:population','f:control','f:population']
    seen.clear()
    step.conditional_sequence(lambda n:n!='control',feedback)
    assert not seen


def test_audited_file_replacement_rejected(monkeypatch,tmp_path):
    import json,tarfile,io
    for module in (step,step.pipeline,step.reused):monkeypatch.setattr(module,'ROOT',tmp_path)
    archive=tmp_path/'a.tar.gz';p=tmp_path/'state.json';p.write_text('{}')
    c=step.pipeline.claim(p);c['path']='state.json'
    with tarfile.open(archive,'w:gz') as t:
        b=json.dumps({'files':[c]}).encode();m=tarfile.TarInfo('ARCHIVE_MANIFEST.json');m.size=len(b);t.addfile(m,io.BytesIO(b))
    a=tmp_path/'audit.json';a.write_text(json.dumps({'archive':step.pipeline.claim(archive),'accepted_outer_steps':20}))
    t=tmp_path/'terminal.json';t.write_text(json.dumps({'job_id':77102,'state':'COMPLETED'}))
    step.audited_inputs(tmp_path,a,t,77102,['state.json'])
    p.write_text('{"changed":true}')
    with pytest.raises(RuntimeError,match='audited source changed'):step.audited_inputs(tmp_path,a,t,77102,['state.json'])
