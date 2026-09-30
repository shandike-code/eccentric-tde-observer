import numpy as np
from operations.x20_window_feasibility import convert,PAIRS
from operations.x20_expanded_feasibility import system,cap_geometry


def test_reordering_preserves_each_map_pair():
    f=np.array([np.full(9632,v) for v in (10,11,12,14,15,18,20,24)],float)
    rows=[dict(boundary_spectra=f[:,i:i+32].tolist()) for i in range(0,9632,32)]
    converted=convert(rows);s=system(converted,PAIRS)
    np.testing.assert_allclose(s['r'],np.full(9632,1/(11*9632)))
    np.testing.assert_allclose(s['dr'][0],np.array([1,2,3])/(11*9632))
    np.testing.assert_allclose(s['di'][0],np.array([2,5,10])/(11*9632))


def test_three_direction_cap_contains_only_registered_vertices():
    vv,a,b=cap_geometry(3)
    assert len(vv)==12 and np.max(vv@a.T-b)<1e-12
    for v in vv:assert np.sum(abs(np.r_[v[0],1-sum(v),v[1:]]))==17
