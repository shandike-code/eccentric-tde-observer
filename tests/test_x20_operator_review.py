import copy,json
from pathlib import Path
import numpy as np
import pytest
from handoff.audit_tools.review_x20_operator import gram_roundoff_check,scan_review


def test_subnormal_quantization_is_bounded_without_dropping_slab():
    u=np.nextafter(0.,1.)
    # 半ulp转存的Gram可能不严格PSD；允许的界由每元素误差推出。
    g=np.zeros((4,4));g[:2,:2]=[[2*u,3*u],[3*u,4*u]]
    r=gram_roundoff_check(g);assert r['normalized_min_eigenvalue']<0 and r['normalized_bound']==.5
    bad=np.eye(4);bad[0,1]=bad[1,0]=2
    with pytest.raises(AssertionError):gram_roundoff_check(bad)


def test_changed_prediction_or_omitted_tail_is_rejected():
    path=Path('outputs/review-20260925/x20-scan-80826-received/prediction.json')
    if not path.exists():pytest.skip('received audit input is Mac-only')
    p=json.loads(path.read_text());scan_review(p)
    bad=copy.deepcopy(p);bad['slabs'].pop()
    with pytest.raises(AssertionError):scan_review(bad)
    bad=copy.deepcopy(p);bad['choice']['alpha']*=2
    with pytest.raises(AssertionError):scan_review(bad)
