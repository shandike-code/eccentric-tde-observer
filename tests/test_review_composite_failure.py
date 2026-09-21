from pathlib import Path
import numpy as np
import pytest
from operations.review_composite_failure import stream_defects,summarize


def test_identity_outside_selected_blocks_and_measured_defects(tmp_path):
    shape=(1920,1,1);x=np.ones(shape)*2;y=x+.5;u=x.copy();u[1792:1920]+=.2;v=u+.25
    files=[]
    for i,a in enumerate([x,y,u,v]):
        p=tmp_path/f'{i}.dat';a.tofile(p);files.append(p)
    r=stream_defects(files,shape)
    assert r['full_l2_ratio']==.5 and r['full_linf_ratio']==.5
    assert r['predicted_fraction']==1 and r['prediction_has_fresh_map'] is False
    assert len(r['blocks'])==15
    assert sum(z['groups'][1]-z['groups'][0] for z in r['blocks'])==shape[0]


def test_undeclared_input_change_rejected(tmp_path):
    paths=[]
    for i,value in enumerate([1.,2.,3.,4.]):
        p=tmp_path/f'{i}.dat';np.full((128,1,1),value).tofile(p);paths.append(p)
    with pytest.raises(ValueError,match='unselected'):stream_defects(paths,(128,1,1))


def test_bounded_prediction_and_no_zero_denominator():
    row={'raw_squared_l2':1.,'fresh_squared_l2':4.,'change_squared_l2':9.,'raw_dot_change':-3.,'raw_linf':1.,'fresh_linf':2.}
    r=summarize([row]);assert r['predicted_fraction']==pytest.approx(1/3) and r['predicted_l2_ratio']==0
    row['raw_dot_change']=1.;assert summarize([row])['predicted_fraction']==0
    row['raw_squared_l2']=0.
    with pytest.raises(ValueError):summarize([row])
