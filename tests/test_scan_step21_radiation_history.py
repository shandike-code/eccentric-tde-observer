import numpy as np
import pytest
from operations import scan_step21_radiation_history as scan


def test_stream_matches_legacy_scan_and_metrics_and_preserves_bytes(tmp_path):
    shape=(16,4,3);root=np.arange(np.prod(shape),dtype=float).reshape(shape)+10
    cfg={'scan_frequency_chunk':4,'diagnostic_frequency_block':8,'minimum_forward_picard_fraction':1.,'maximum_forward_picard_fraction':96.}
    paths=[]
    for i,a in zip((9,10,11),(root+3,root+1.5,root+.75)):
        p=tmp_path/str(i);a.tofile(p);cfg[f'x{i}_state_path']=str(p);paths.append(p)
    before=[p.read_bytes() for p in paths];edges=np.arange(17,dtype=float)+1
    d=scan.algebra._scan_direction(cfg,shape);m=scan.algebra._candidate_metrics(cfg,shape,d['selected_forward_fraction'],edges)
    original=scan.algebra._open_states
    with scan.streaming_states():
        ds=scan.algebra._scan_direction(cfg,shape);ms=scan.algebra._candidate_metrics(cfg,shape,ds['selected_forward_fraction'],edges)
    for k in d:np.testing.assert_equal(ds[k],d[k])
    assert ms==m and scan.algebra._open_states is original
    assert [p.read_bytes() for p in paths]==before
    assert ds['selected_forward_fraction']==pytest.approx(2.)
    assert ms['predicted_global_original_operator_residual']<1e-12


@pytest.mark.parametrize('bad',['negative','nan','short','long'])
def test_stream_rejects_invalid_basis(tmp_path,bad):
    a=np.ones((2,4,3));p=tmp_path/'state'
    if bad=='negative':a[0,0,0]=-1
    if bad=='nan':a[0,0,0]=np.nan
    data=a.tobytes()
    if bad=='short':data=data[:-8]
    if bad=='long':data+=b'12345678'
    p.write_bytes(data)
    with pytest.raises(ValueError):scan.StreamState(p,(2,4,3))[:]


def test_stream_wrapper_restored_on_error():
    old=scan.algebra._open_states
    with pytest.raises(RuntimeError):
        with scan.streaming_states():raise RuntimeError('expected')
    assert scan.algebra._open_states is old


def test_retained_basis_rejects_unsettled_or_wrong_lineage():
    a={'input_sha256':'a','output_sha256':'b'};b={'input_sha256':'b','output_sha256':'c'}
    s={'history':[{}]*6+[a,b],'active_map':None}
    r={'history_rows':[a,b],'endpoints':{n:{'sha256':h} for n,h in zip(('previous','final','mapped_final'),'abc')}}
    assert len(scan.retained_basis(s,r))==3
    s['active_map']={}
    with pytest.raises(ValueError):scan.retained_basis(s,r)
    s['active_map']=None;r['endpoints']['final']['sha256']='wrong'
    with pytest.raises(ValueError):scan.retained_basis(s,r)
