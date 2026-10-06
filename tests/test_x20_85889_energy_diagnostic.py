import hashlib
import numpy as np
import pytest
from handoff.audit_tools.diagnose_x20_85889_energy import arrays, log_secant, verify_file


def test_equal_energy_analytic_limit_and_canceling_terms():
    a=np.array([2.,4.]);g=log_secant(a,a)
    np.testing.assert_array_equal(g,1/a)
    np.testing.assert_array_equal(g*np.array([3.,-7.])-g*np.array([3.,-7.]),np.zeros(2))


def test_log_decomposition_and_reversal():
    a=np.array([2.,4.,100.]);heat=np.array([1.,-1.,1e-7]);ion=np.array([.5,.25,2e-8]);b=a+heat-ion
    g=log_secant(a,b)
    np.testing.assert_allclose(g*heat-g*ion,np.log(b)-np.log(a),rtol=1e-6,atol=1e-15)
    np.testing.assert_allclose(g,log_secant(b,a),rtol=2e-15,atol=0)


@pytest.mark.parametrize('bad',[0.,-1.,float('nan')])
def test_no_repair_of_nonpositive_or_nonfinite_energy(bad):
    with pytest.raises(ValueError):log_secant(np.array([1.]),np.array([bad]))


def test_changed_source_is_rejected(tmp_path):
    p=tmp_path/'source.npz';p.write_bytes(b'abc');claim=dict(size_bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())
    verify_file(p,claim);p.write_bytes(b'abd')
    with pytest.raises(ValueError):verify_file(p,claim)


def test_large_field_is_rejected_before_read(tmp_path):
    with pytest.raises(ValueError):verify_file(tmp_path/'absent.dat',{})


def test_text_metadata_is_retained_but_nonfinite_numeric_rejected(tmp_path):
    p=tmp_path/'old.npz';np.savez(p,source=np.array('physical_old'),energy=np.array([2.]))
    assert str(arrays(p)['source'])=='physical_old'
    np.savez(p,source=np.array('physical_old'),energy=np.array([np.nan]))
    with pytest.raises(ValueError):arrays(p)
