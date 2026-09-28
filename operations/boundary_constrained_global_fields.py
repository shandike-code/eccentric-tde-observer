"""Actual candidates and actual-map gates anchored at the original x."""
from pathlib import Path
import numpy as np
from operations import seven_block_global_fields as seven
from operations import population_defect_global_fields as dual
from operations.boundary_constrained_proposal import support_check

GATES=seven.GATES.copy()
SELECTED=tuple(range(20,48))


def write_candidates(paths,full,half,shape,a,b,checkpoint=lambda:None):
    if len(paths)!=3 or not 0<=a<=1 or not 0<=b<=1:raise ValueError('three fields and box coefficients required')
    full,half=Path(full),Path(half);temps=[p.with_suffix('.partial') for p in (full,half)]
    if len(set((full,half,*temps)))!=4 or any(p.exists() for p in (full,half,*temps)):raise FileExistsError('new candidate files required')
    with temps[0].open('xb') as f,temps[1].open('xb') as h:
        for start,(x,q,u) in seven.chunks(paths,shape):
            checkpoint();support_check(start,x,q,u);block=start//128
            if block in range(34,48):z=(1-a)*x+a*q
            elif block in range(20,34):z=(1-b)*x+b*u
            else:z=x
            mid=.5*x+.5*z if block in SELECTED else x
            seven.physical(z);seven.physical(mid);z.tofile(f);mid.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temps):raise RuntimeError('incomplete candidate')
    for p,target in zip(temps,(full,half)):p.replace(target)


def validate(paths,prior_q_pair,shape,checkpoint=lambda:None):
    original=seven.validate(paths,shape,blocks=SELECTED,checkpoint=checkpoint)
    q=dual.original_reference(list(prior_q_pair)+list(paths[2:]),shape,checkpoint)
    return original,q


def checks(original,q,original_row,q_row,full,half):
    raw=dual.checks(original,q,original_row,q_row,full,half)
    # 11门用于本次真实中点的原x；q只提供10个收益/边界比较，不冒充其中点。
    return {('original_'+k[len('current_'):] if k.startswith('current_') else 'prior_q_'+k[len('original_'):]):v for k,v in raw.items()}
