"""Reproduce the real missing witness-serialization coverage in the first scan."""
import json
import numpy as np
import pytest
from operations import scan_step21_block_short_step as legacy
from operations import scan_step21_block_short_step_v2 as repaired


def exercise(module,tmp_path,monkeypatch,delta):
    monkeypatch.setattr(module,'BLOCKS',(0,1));monkeypatch.setattr(module.reused,'checkpoint',lambda:None)
    shape=(384,1,1);x=np.full(shape,2.);y=x+.1;q=x.copy();q[:256]+=.5
    tq=q+.08;tq[0]=q[0]+delta
    paths=[]
    for i,a in enumerate((x,y,q,tq)):
        p=tmp_path/f'{i}.dat';a.tofile(p);paths.append(p)
    return module.scan(paths,shape,lambda a,start:a[:,0,0],{'boundary_l1':.1,'boundary_bolometric':.1})


def test_legacy_reproduces_int64_error_after_completed_scan(tmp_path,monkeypatch):
    r=exercise(legacy,tmp_path,monkeypatch,.3)
    assert r['witness'] is not None and r['linf_upper']==0
    with pytest.raises(TypeError,match='int64'):json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('delta',[.3,-.3,.08])
def test_repaired_entire_result_roundtrips_strict_json(tmp_path,monkeypatch,delta):
    r=exercise(repaired,tmp_path,monkeypatch,delta)
    decoded=json.loads(json.dumps(r,allow_nan=False))
    assert decoded==r
    if r['witness'] is not None:
        assert all(type(i) is int for i in r['witness']['index'])
    assert not r['candidate_written'] and not r['actual_map_performed'] and not r['accepted_material_step']
    assert r['passes']<=3


def test_repair_only_changes_index_representation_and_registered_paths():
    from pathlib import Path
    old=Path(legacy.__file__).read_text().replace('index=[start+i,j,k]','index=[int(start+i),int(j),int(k)]')
    old=old.replace('operations/scan_step21_block_short_step.sbatch','operations/scan_step21_block_short_step_v2.sbatch').replace('tests/test_scan_step21_block_short_step.py','tests/test_scan_step21_block_short_step_serialization.py').replace('handoff/protocols/step21-block-short-step-scan-v1.md','handoff/protocols/step21-block-short-step-scan-v2.md')
    assert old==Path(repaired.__file__).read_text()
