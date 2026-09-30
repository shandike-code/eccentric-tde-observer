import copy,json,hashlib
from pathlib import Path
import numpy as np
import pytest
from operations.x20_block_window_fields import measure_candidates
from operations.x20_block_window_prediction import require_candidate


def test_coefficients_switch_only_at_natural_block_boundary(tmp_path):
    shape=(132,2,2);x=np.full(shape,5.);h=np.full(shape,8.)
    fields=[x,.8*x+1.5,h,.8*h+1.5,x,.8*x+1.5,x,.8*x+1.5];paths=[]
    for i,v in enumerate(fields):
        p=tmp_path/str(i);v.tofile(p);paths.append(p)
    geo=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(132))
    r=measure_candidates(paths,shape,[[.75,0,0],[0,0,0]],geo)
    expected=np.sqrt((128*.05**2+4*.5**2)/(132*.5**2))
    assert r['fixed_scale_l2_ratios'][1]==pytest.approx(expected)
    assert r['slabs'][-1]['group_count']==4
    bad=measure_candidates(paths,shape,[[-7.2,0,0],[0,0,0]],geo)
    assert not bad['passed'] and bad['status']=='negative_field_rejected' and min(bad['slabs'][0]['minima'])<0
    with pytest.raises(ValueError,match='cap'):measure_candidates(paths,shape,[[20,0,0],[0,0,0]],geo)


def records():
    p=Path('handoff/evidence/20261001-x20-82441-bounded-gram-analysis.json')
    return json.loads(p.read_text()),json.loads(Path('handoff/evidence/20261001-x20-82441-bounded-gram-verification.json').read_text()),hashlib.sha256(p.read_bytes()).hexdigest()


def test_exact_audited_coefficients_preserve_unresolved_blocks():
    c,a,s=records();rows=require_candidate(c,a,s);assert np.asarray(rows).shape==(76,3)
    assert all(rows[i]==[0,0,0] for i in a['unresolved_blocks'])


def test_changed_safety_rounding_or_source_rejected():
    c,a,s=records();bad=copy.deepcopy(c);bad['blocks'][24]['selected_coefficients_float'][0]+=1e-12
    with pytest.raises(ValueError,match='rounded'):require_candidate(bad,a,s)
    with pytest.raises(ValueError,match='certificate'):require_candidate(c,a,'0'*64)
    bad=copy.deepcopy(c);bad['source_job']=82166
    with pytest.raises(ValueError,match='scope'):require_candidate(bad,a,s)
