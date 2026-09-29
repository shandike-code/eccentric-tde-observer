"""Check the independent certificate geometry and rejection of altered evidence."""
import copy
from decimal import localcontext
import pytest
from handoff.audit_tools.review_x20_spectral import D,vertices,cap_halfspaces,audit_numbers,arrays,read,OUT


def test_independent_cap_slice_has_all_six_known_vertices():
    with localcontext() as ctx:
        ctx.prec=70
        points=vertices(list(map(D,[0,0,1,0])),cap_halfspaces())
    assert {tuple(map(float,p)) for p in points}=={(9,0,0),(9,0,-8),(0,0,-8),(-8,0,0),(-8,0,9),(0,0,9)}


@pytest.mark.parametrize('damage',['lower_bound','spectral_cut'])
def test_independent_audit_rejects_changed_evidence(damage):
    if not OUT.exists():pytest.skip('Mac received artifacts')
    data=arrays(OUT/'boundary-spectra.npz');saved=copy.deepcopy(read(OUT/'feasibility.json'))
    if damage=='lower_bound':saved['iterations'][-1]['bound']['squared_support_lower']+=.01
    else:saved['iterations'][0]['cuts'][0]['a'][1]+=1
    with pytest.raises(AssertionError):audit_numbers(data['gram'],data['spectra'],saved)
