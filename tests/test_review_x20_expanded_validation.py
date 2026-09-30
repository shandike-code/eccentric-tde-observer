import copy,json
import numpy as np
import pytest
from handoff.audit_tools.review_x20_expanded_validation import gates,actual_numbers,prediction_numbers,OUT,ROOT,read,arrays


def test_gates_keep_original_thresholds_and_serialize_numpy_inputs():
    b=[dict(residual=1e-6,boundary_l1=1e-7,boundary_bolometric=1e-8)]*3
    assert all(gates(np.array([1,.79,.9]),np.array([1,.8,.9]),b).values())
    r=gates(np.array([1,.81,.9]),np.array([1,.8,.9]),b)
    assert not r['full_l2_benefit'];json.dumps(r,allow_nan=False)


@pytest.mark.parametrize('damage',['missing_frequency','affinity','claimed_gate','candidate'])
def test_audit_rejects_altered_actual_or_predicted_evidence(damage):
    if not OUT.exists():pytest.skip('Mac received archive')
    v=copy.deepcopy(read(OUT/'validation.json'));d=read(OUT/'declaration.json')
    if damage=='candidate':
        p=read(OUT/'prediction.json');p['selected_coefficients'][3]+=.1
        with pytest.raises(AssertionError):prediction_numbers(p,arrays(ROOT/'x20-long-chord-81647-received/expanded-system.npz')['gram'],read(__import__('pathlib').Path('handoff/evidence/20260930-x20-expanded-candidate-result.json')))
        return
    if damage=='missing_frequency':v['field_comparison']['slabs'][-1]['first_group']=0
    elif damage=='affinity':
        row=max(v['field_comparison']['slabs'],key=lambda r:r['squared_l2'][0]);assert row['squared_l2'][0]>0
        row['squared_l2'][3]=row['squared_l2'][0]
    else:v['checks']['full_l2_benefit']=False
    with pytest.raises(AssertionError):actual_numbers(v,d['source_row'])
