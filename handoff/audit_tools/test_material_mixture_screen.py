import numpy as np
from handoff.audit_tools.screen_step21_material_mixture import norms,screen

def test_norms_include_mass_and_switching_maximum_cell():
    v=np.array([[[3.,0,0,0],[0,4,0,0]],[[0,5,0,0],[0,1,0,0]]]);n=norms(v,[1.,3.])
    np.testing.assert_allclose(n,[[5,np.sqrt(57/4),4],[np.sqrt(26),np.sqrt(28/4),5]])

def test_all_endpoints_and_original_denominator_are_retained():
    c=np.ones((2,2,4));t=c*.8;p=c*.9;t[1]=c[1]*1.2
    rows=screen(c,t,p,[1.,1.],c[0]*.5)
    r=next(x for x in rows if x['thermal_weight']==1 and x['population_weight']==0)
    assert r['score']==2.4
    assert len(rows)==833 and max(r['worst_matched_ratios'])==1.2
