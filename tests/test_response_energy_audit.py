import numpy as np
import pytest
from operations.response_energy_audit import energy_defect


def test_defect_retains_sign_when_target_energy_is_negative():
    # target = 10-30 = -20: never decode/floor; candidate 12 gives defect 32.
    np.testing.assert_array_equal(energy_defect([12.,12.],[10.,10.],[-30.,2.]),[32.,0.])


@pytest.mark.parametrize('bad', [[np.nan], [1.,2.]])
def test_nonfinite_or_mismatched_input_is_rejected(bad):
    with pytest.raises(ValueError):energy_defect([1.],[1.],bad)
