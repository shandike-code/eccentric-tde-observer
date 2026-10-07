"""Fixed synthetic-only wiring to frozen diagonal kernel, never production fields."""
import copy
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import numpy as np
from operations import x20_85889_chord_scan as original
from operations import x20_85889_chord_scan_diagonal as diagonal
from handoff.audit_tools.review_x20_85889_chord_scan import review


def scalar_oracle(arrays, row):
    """Independent elementwise Decimal80 full matrices for dyadic fixtures."""
    with localcontext() as c:
        c.prec=80
        points=[list(map(lambda x:Decimal.from_float(float(x)), a.flat)) for a in arrays]
        sub=lambda x,y:[a-b for a,b in zip(x,y)]
        ap,af,am,hp,hf,hm=points
        basis=[sub(hf,af),sub(af,ap),sub(am,af),sub(hf,hp),sub(hm,hf)]
        groups=[(basis,row['gram'])]
        for k,(a,h) in enumerate(((0,3),(0,4),(1,3),(1,4))):
            d=sub(points[h],points[a]);ra=sub(points[a+1],points[a]);rh=sub(points[h+1],points[h])
            vectors=[d,sub(rh,ra),sub(points[h+1],points[a+1]),ra,rh]
            groups.append((vectors,row['pairs'][k]['moments']))
            if [Decimal(s) for s in row['pairs'][k]['linf']]!=[max(map(abs,v)) for v in vectors]:raise ValueError('oracle Linf')
        for vectors,matrix in groups:
            for i in range(5):
                for j in range(5):
                    products=[a*b for a,b in zip(vectors[i],vectors[j])]
                    if Decimal(matrix['value'][i][j])!=sum(products):raise ValueError('oracle signed')
                    if Decimal(matrix['absolute'][i][j])!=sum(map(abs,products)):raise ValueError('oracle absolute')
    return 250


def exercise(output):
    output=Path(output);output.mkdir(exist_ok=False)
    shape=(129,2,3)
    x=np.arange(np.prod(shape),dtype='<f8').reshape(shape)%11+2
    y=np.flip(x,axis=0)+3
    fields=[x,.5*x+4,.25*x+6,y,.5*y+4,.25*y+6]
    claims=[]
    for i,a in enumerate(fields):
        raw=a.tobytes();p=output/f'synthetic-{i}.bin'
        with p.open('xb') as f:f.write(raw)
        claims.append(dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    reference=original.scan(claims,list(shape),lambda _:None)
    buffers=[Path(c['path']).read_bytes() for c in claims]
    for raw,c in zip(buffers,claims):
        if hashlib.sha256(raw).hexdigest()!=c['sha256']:raise ValueError('synthetic input SHA')
    arrays=[np.frombuffer(raw,dtype='<f8').reshape(shape) for raw in buffers]
    rows=[];checks=0
    for start in range(0,129,32):
        slab=[a[start:start+32] for a in arrays]
        row=diagonal.slab_statistics(slab);checks+=scalar_oracle(slab,row)
        row.update(first_group=start,group_count=len(slab[0]),block=start//128);rows.append(row)
    if rows!=reference['slabs']:raise ValueError('complete schema difference')
    candidate=copy.deepcopy(reference);candidate['slabs']=rows
    candidate['synthetic_explicit_slab_wiring']=True;candidate['file_evidence_from_original_scan']=True
    checked=review(candidate)
    for pair in checked['total']['pairs']:
        if Decimal(pair['mapped_difference_l2_ratio'])!=Decimal('.5'):raise ValueError('analytic norm ratio')
    for name,obj in [('scan',candidate),('review',checked),('metadata',dict(shape=list(shape),scalar_matrix_checks=checks,
        file_evidence_from_original_scan=True,synthetic_only=True,production_driver=False,
        shared_buffer_bytes=sum(map(len,buffers)),original_scan_bytes=reference['field_bytes_read'],
        readonly=all(not a.flags.writeable for a in arrays),arithmetic=reference['arithmetic'],
        production_resource_verified=False,submission_ready=False))]:
        with (output/(name+'.json')).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
    return dict(scalar_matrix_checks=checks,slabs=5,production_driver=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(exercise(a.output)))
