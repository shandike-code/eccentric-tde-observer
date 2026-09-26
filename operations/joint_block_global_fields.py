"""Keep the original full-frequency map; replace only two audited joint cores."""
from pathlib import Path
import numpy as np
from operations.heating_block_global_fields import chunks,physical,GATES,checks
from operations.heating_block_global_fields import validate as original_validate
CENTERS=(24,48)
SELECTED=(23,24,25,47,48,49)


def intervals(centers, groups):
    if len(centers)!=2 or len(set(centers))!=2 or any(type(i) is not int for i in centers):
        raise ValueError('two distinct integer centers required')
    ranges={i:((i-1)*128,(i+2)*128) for i in centers}
    occupied=set()
    for start,stop in ranges.values():
        if not 0<=start<stop<=groups:raise ValueError('joint core outside grid')
        ids=set(range(start//128,stop//128))
        if occupied & ids:raise ValueError('joint core overlap')
        occupied |= ids
    return ranges


def write_candidates(source,replacements,full,half,shape,*,centers=CENTERS,checkpoint=lambda:None):
    ranges=intervals(centers,shape[0])
    if set(replacements)!=set(centers):raise ValueError('wrong replacement inventory')
    full,half=Path(full),Path(half);temporary=[p.with_suffix('.partial') for p in (full,half)]
    if len(set([full,half,*temporary]))!=4 or any(p.exists() for p in [full,half,*temporary]):
        raise FileExistsError('candidate paths must be new and distinct')
    cores={}
    for i,p in replacements.items():
        with np.load(p,allow_pickle=False) as z:cores[i]=z['candidate']
        if cores[i].shape!=(384,*shape[1:]):raise ValueError('joint core shape')
        physical(cores[i])
    with temporary[0].open('xb') as f,temporary[1].open('xb') as h:
        for start,(x,) in chunks([source],shape):
            checkpoint();which=[i for i,(a,b) in ranges.items() if a<=start<b]
            if which:
                i=which[0];a,b=ranges[i]
                if start+len(x)>b:raise ValueError('slab crosses core boundary')
                q=cores[i][start-a:start-a+len(x)];m=.5*x+.5*q
            else:q=m=x
            physical(q);physical(m);q.tofile(f);m.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temporary):raise ValueError('candidate byte count')
    for p,d in zip(temporary,(full,half)):p.replace(d)


def validate(paths,shape,*,blocks=SELECTED,checkpoint=lambda:None):
    return original_validate(paths,shape,blocks=blocks,checkpoint=checkpoint)
