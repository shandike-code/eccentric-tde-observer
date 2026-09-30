import copy
import numpy as np
import pytest
from handoff.audit_tools.review_x20_long_chord import gram_review


def fixture():
    rows=[dict(first_group=i,group_count=32,gram=np.eye(5).tolist(),minima=[0.]*8) for i in range(0,9632,32)]
    return rows,301*np.eye(5)


def test_full_frequency_gram_audit_preserves_all_directions():
    rows,g=fixture();r=gram_review(rows,g)
    assert len(r['positive_hessian_ldl_pivots'])==4 and r['all_groups']==9632


@pytest.mark.parametrize('damage',['frequency','nonfinite','negative_field','sum','nonpositive_direction'])
def test_gram_audit_rejects_damaged_science_evidence(damage):
    rows,g=fixture()
    if damage=='frequency':rows[-1]['first_group']=0
    elif damage=='nonfinite':rows[0]['gram'][0][0]=float('nan')
    elif damage=='negative_field':rows[0]['minima'][-1]=-1e-300
    elif damage=='sum':g[-1,-1]+=1
    else:
        for row in rows:row['gram'][-1][-1]=0
        g[-1,-1]=0
    with pytest.raises(AssertionError):gram_review(rows,g)
