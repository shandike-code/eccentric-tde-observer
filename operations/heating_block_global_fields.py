"""Streaming, fixed-scale full-frequency validation of two saved local cores."""
from pathlib import Path
import math
import numpy as np
from operations.constrained_hybrid_fields import chunks,physical
from operations.composite_hybrid_audit import GATES,checks

BLOCKS=(24,48)


def write_candidates(source,replacements,full,half,shape,*,blocks=BLOCKS,checkpoint=lambda:None):
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
            q=cores[i][start%128:start%128+len(x)] if i in cores else x
            # 未改块逐位复制：不能对极小的次正规数执行半乘再相加。
            m=.5*x+.5*q if i in cores else x
            physical(m);q.tofile(f);m.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temporary):raise ValueError('candidate byte count')
    for p,d in zip(temporary,(full,half)):p.replace(d)


def validate(paths,shape,*,blocks=BLOCKS,checkpoint=lambda:None):
    if len(paths)!=6:raise ValueError('original, full, half input/output pairs required')
    rows=[];peaks=np.zeros(4)
    for start,(x,y,q,tq,h,th) in chunks(paths,shape):
        checkpoint();selected=start//128 in blocks
        if not selected and not (np.array_equal(x,q) and np.array_equal(x,h)):raise ValueError('unselected input changed')
        if selected and not np.array_equal(h,.5*x+.5*q):raise ValueError('half identity')
        # R=T(I)-I；半步与两端真实缺陷插值比较，分母始终用旧R的范数。
        with np.errstate(invalid='raise',over='raise',divide='raise'):
            a=y-x;b=tq-q;c=th-h;d=c-.5*a-.5*b
            ss=[float(np.sum(z*z)) for z in (a,b,c,d)]
            pp=[float(np.max(abs(z))) for z in (a,b,c,d)]
        if not np.isfinite(ss+pp).all():raise ValueError('nonfinite norm')
        peaks=np.maximum(peaks,pp)
        rows.append(dict(first_group=start,group_count=len(x),block=start//128,squared_l2=ss,linf=pp,
            selected_input=selected,output_change_linf=float(np.max(abs(tq-y)))))
    sums=np.array([math.fsum(row['squared_l2'][i] for row in rows) for i in range(4)])
    if sums[0]<=0 or peaks[0]<=0:raise ValueError('zero original defect')
    return dict(fixed_scale_l2_ratios=np.sqrt(sums/sums[0]).tolist(),fixed_scale_linf_ratios=(peaks/peaks[0]).tolist(),
        original_defect_l2=math.sqrt(sums[0]),original_defect_linf=float(peaks[0]),slabs=rows,
        all_groups_evaluated=shape[0],selected_blocks=list(blocks))
