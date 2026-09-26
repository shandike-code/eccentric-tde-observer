import math
import numpy as np
import pytest
from operations.scan_step21_five_block_arrays import frequency_stats

def test_all_angles_depths_and_signs_contribute():
    a=np.array([[1.,2.],[3.,4.]])
    b=np.array([[2.,1.],[3.,6.]])
    got=frequency_stats(a,b)
    assert got==dict(square=6.,maximum=2.,minimum_input=1.,minimum_output=1.)
    assert math.sqrt(got['square'])!=abs(float((b-a).sum()))

@pytest.mark.parametrize('bad',[np.array([[np.nan]]),np.array([[-1.]]),np.ones((2,2))])
def test_nonphysical_or_wrong_shape_rejected(bad):
    with pytest.raises(ValueError):frequency_stats(np.ones((1,1)),bad)
