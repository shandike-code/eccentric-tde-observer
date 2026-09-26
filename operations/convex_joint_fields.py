"""Write the audited scalar convex combination; preserve every unselected input byte."""
from pathlib import Path
import numpy as np
from operations.constrained_hybrid_fields import chunks,physical
from operations.tapered_joint_fields import GATES,checks,validate
from operations.joint_taper_plane import coefficients,mix,SELECTED


def write_candidates(paths,uv,full,half,shape,*,selected=SELECTED,checkpoint=lambda:None):
    if len(paths)!=3:raise ValueError('three convex input states required')
    weights=coefficients(uv);full,half=Path(full),Path(half);temps=[p.with_suffix('.partial') for p in (full,half)]
    if len(set([full,half,*temps]))!=4 or any(p.exists() for p in [full,half,*temps]):raise FileExistsError('new distinct candidates required')
    with temps[0].open('xb') as f,temps[1].open('xb') as h:
        for start,(x,q,z) in chunks(paths,shape):
            checkpoint()
            if start//128 not in selected:
                if not (np.array_equal(x,q) and np.array_equal(x,z)):raise ValueError('unselected input changed')
                u=half_u=x
            else:
                u=mix([x,q,z],weights);half_u=.5*x+.5*u
            physical(u);physical(half_u);u.tofile(f);half_u.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temps):raise ValueError('candidate byte count')
    for p,d in zip(temps,(full,half)):p.replace(d)


def prediction_checks(comparison,prediction):
    return {'predicted_full_l2_reproduced':abs(comparison['fixed_scale_l2_ratios'][1]-prediction['l2_ratio'])<=1e-6,
            'predicted_full_linf_reproduced':abs(comparison['fixed_scale_linf_ratios'][1]-prediction['linf_ratio'])<=1e-6}
