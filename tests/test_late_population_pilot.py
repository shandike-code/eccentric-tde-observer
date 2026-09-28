import copy
import json
from pathlib import Path
import numpy as np
import pytest
from operations.pilot_late_population_blocks import core_interval, exact_replay, choose_cores, validate_source


def test_new_cores_are_disjoint_and_complete():
    assert core_interval(37)==(4352,5248)
    assert core_interval(44)==(5248,6144)
    for index in (True,37.,24,48,-1):
        with pytest.raises(ValueError):core_interval(index)


def test_pilot_requires_bytewise_operator_replay():
    x=np.ones(2);y=x+.1;changed=y.copy();changed[0]=np.nextafter(changed[0],np.inf)
    assert exact_replay(x,y,y)['array_equal']
    with pytest.raises(RuntimeError,match='bytewise'):exact_replay(x,y,changed)


def test_selection_requires_all_blocks_and_never_overlaps():
    rows=[dict(block=i,mass_norm=float(34<=i<=47)) for i in range(76)]
    assert choose_cores(rows)==(37,44)
    assert choose_cores(list(reversed(rows)))==(37,44)
    with pytest.raises(ValueError):choose_cores(rows[:-1])
    rows[0]['mass_norm']=float('nan')
    with pytest.raises(ValueError):choose_cores(rows)


def real_inputs():
    root=Path('outputs/review-20260925/late-direction-79151-complete-received')
    if not root.exists():pytest.skip('Mac received archive unavailable; run source preflight on school separately')
    read=lambda p:json.loads(Path(p).read_text())
    return [read('handoff/evidence/20260928-late-direction-complete-review.json'),
        read(root/'summary.json'),read('handoff/evidence/20260928-late-population-drift-decomposition.json'),
        read(root/'population/state.json'),read(root/'population/endpoints-map08/manifest.json')]


def test_actual_source_pair_and_immutability():
    args=real_inputs();saved=copy.deepcopy(args)
    pair=validate_source(*args)
    assert pair[0]['sha256']==args[3]['history'][-1]['input_sha256']
    assert pair[1]['sha256']==args[3]['history'][-1]['output_sha256']
    assert args==saved


@pytest.mark.parametrize('case',range(7))
def test_refuse_wrong_source_partial_lineage_or_diagnosis(case):
    a,s,l,state,ret=real_inputs()
    if case==0:a['job_id']=78950
    if case==1:s['new_material_steps']=1
    if case==2:state['active_map']={'unfinished':True}
    if case==3:ret['endpoints']['final']['sha256']=ret['endpoints']['mapped_final']['sha256']
    if case==4:l['source_archives']['new']['sha256']='changed'
    if case==5:a['pairs']['population08']['late_direction_pass']=True
    if case==6:l['channel_decomposition']['mass_weighted']['squared_fraction_by_channel'][0]=.5
    with pytest.raises(RuntimeError):validate_source(a,s,l,state,ret)
