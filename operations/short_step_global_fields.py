"""Write one preregistered convex short step; reuse unchanged full-domain checks."""
from pathlib import Path
import math
import numpy as np
from operations.constrained_hybrid_fields import chunks,physical
from operations.heating_block_global_fields import GATES,checks,validate

BLOCKS=(24,48)


def write_candidates(source,replacements,full,half,shape,*,fraction,blocks=BLOCKS,checkpoint=lambda:None):
    if not np.isfinite(fraction) or not 0<fraction<=1:raise ValueError("invalid short fraction")
    if set(replacements)!=set(blocks) or len(blocks)!=2:raise ValueError('wrong block inventory')
    if any((i+1)*128>shape[0] for i in blocks):raise ValueError('block outside shape')
    full,half=Path(full),Path(half)
    temporary=[p.with_suffix('.partial') for p in (full,half)]
    if len(set([full,half,*temporary]))!=4 or any(p.exists() for p in [full,half,*temporary]):raise FileExistsError('candidate paths must be new and distinct')
    cores={}
    for i,p in replacements.items():
        with np.load(p,allow_pickle=False) as z:cores[i]=z['candidate']
        if cores[i].shape!=(128,*shape[1:]):raise ValueError('core shape')
        physical(cores[i])
    with temporary[0].open('xb') as f,temporary[1].open('xb') as h:
        for start,(x,) in chunks([source],shape):
            checkpoint();i=start//128
            q=(1-fraction)*x+fraction*cores[i][start%128:start%128+len(x)] if i in cores else x
            physical(q)
            # 未改块逐位复制：不能对极小的次正规数执行半乘再相加。
            m=.5*x+.5*q if i in cores else x
            physical(m);q.tofile(f);m.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temporary):raise ValueError('candidate byte count')
    for p,d in zip(temporary,(full,half)):p.replace(d)


