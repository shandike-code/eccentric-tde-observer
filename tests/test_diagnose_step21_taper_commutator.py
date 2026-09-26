import math
import numpy as np
import pytest
from operations import diagnose_step21_taper_commutator as diag
from test_validate_step21_joint_blocks import arrays


def setup(tmp_path,op):
    shape,x,xp,repl=arrays(tmp_path);q=x.copy();q[:384]=2;q[512:896]=2
    zp=tmp_path/'z.dat';hp=tmp_path/'h.dat';diag.fields.write_candidates(xp,repl,zp,hp,shape,centers=(1,5));z=np.fromfile(zp).reshape(shape)
    paths=[]
    for i,a in enumerate((x,op(x),q,op(q),z,op(z))):
        p=tmp_path/f'f{i}.dat';a.tofile(p);paths.append(p)
    return shape,paths


@pytest.mark.parametrize('neighbor',[False,True])
def test_exact_decomposition_and_frequency_noncommutation(tmp_path,neighbor):
    op=(lambda x:.25*x+.05*np.roll(x,1,axis=0)+1) if neighbor else (lambda x:.25*x+1)
    shape,paths=setup(tmp_path,op);d=diag.decompose(paths,shape,centers=(1,5));s=d['domains']['all']
    assert len(d['slabs'])==32 and d['passes']==1 and not d['actual_map_performed']
    np.testing.assert_allclose(s['squared_l2'][2],s['squared_l2'][3]+s['squared_l2'][4]+2*s['cross'],rtol=2e-15)
    assert max(r['closure_linf'] for r in d['slabs'])<1e-15
    if neighbor:
        assert s['linf'][4]>1e-4 and d['domains']['outside']['linf'][4]>0
    else:assert s['linf'][4]<1e-15
    w=max(d['slabs'],key=lambda r:abs(r['witness']['actual']))['witness']
    assert math.isclose(w['actual'],w['weighted_defect']+w['commutator'],abs_tol=1e-15)


@pytest.mark.parametrize('kind',['inside','outside','nan','negative','truncate','stop'])
def test_invalid_input_never_returns_result(tmp_path,kind):
    shape,paths=setup(tmp_path,lambda x:.25*x+1);cb=lambda:None
    if kind=='stop':
        def cb():raise diag.reused.Stopped('stop')
    elif kind=='truncate':paths[-1].write_bytes(b'')
    else:
        a=np.fromfile(paths[4]).reshape(shape);a[0 if kind!='outside' else 950,0,0]={'nan':np.nan,'negative':-1}.get(kind,10.);a.tofile(paths[4])
    with pytest.raises((ValueError,diag.reused.Stopped)):diag.decompose(paths,shape,centers=(1,5),checkpoint=cb)
