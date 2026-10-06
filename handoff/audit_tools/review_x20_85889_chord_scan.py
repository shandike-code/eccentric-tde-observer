"""Independent Decimal reduction of exported six-field statistics.

不导入扫描器；只消费小JSON，逐片/块复核，不重新读源大场。
"""
from decimal import Decimal, localcontext
from itertools import combinations, permutations
import argparse
import json
from pathlib import Path

D=Decimal
LABELS=('AP_HP','AP_HF','AF_HP','AF_HF')
COEFFICIENTS=(
 ((1,1,0,-1,0),(0,-1,0,1,0),(1,0,0,0,0),(0,1,0,0,0),(0,0,0,1,0)),
 ((1,1,0,0,0),(0,-1,0,0,1),(1,0,0,0,1),(0,1,0,0,0),(0,0,0,0,1)),
 ((1,0,0,-1,0),(0,0,-1,1,0),(1,0,-1,0,0),(0,0,1,0,0),(0,0,0,1,0)),
 ((1,0,0,0,0),(0,0,-1,0,1),(1,0,-1,0,1),(0,0,1,0,0),(0,0,0,0,1)))


def number(x):
    if not isinstance(x,str):raise ValueError('statistics must preserve decimal strings')
    v=D(x)
    if not v.is_finite():raise ValueError('nonfinite statistic')
    return v


def matrix(row,tau):
    g=[[number(x) for x in r] for r in row['value']]
    a=[[number(x) for x in r] for r in row['absolute']]
    if len(g)!=5 or len(a)!=5 or any(len(r)!=5 for r in g+a):
        raise ValueError('matrix shape')
    for i in range(5):
        for j in range(5):
            if g[i][j]!=g[j][i] or a[i][j]!=a[j][i] or a[i][j]<0 or abs(g[i][j])>a[i][j]*(1+tau):
                raise ValueError('matrix symmetry/absolute moment')
        if g[i][i]<0 or g[i][i]!=a[i][i]:raise ValueError('negative or inconsistent square')
    # PSD等价于全部主子式非负；保留容差内负值，不修改矩阵或删秩。
    for n in range(2,6):
        for ids in combinations(range(5),n):
            value=D(0);scale=D(0)
            for perm in permutations(range(n)):
                term=D(1)
                for k in range(n):term*=g[ids[k]][ids[perm[k]]]
                inversions=sum(perm[i]>perm[j] for i in range(n) for j in range(i+1,n))
                value+=(-term if inversions%2 else term);scale+=abs(term)
            if value < -tau*scale:raise ValueError('non-PSD principal minor')
    return g,a


def vector(values):
    v=[number(x) for x in values]
    if len(v)!=5 or any(x<0 for x in v):raise ValueError('invalid error/norm vector')
    return v


def summarize(rows):
    totals=[]
    for k in range(4):
        g=[[sum((number(r['pairs'][k]['moments']['value'][i][j]) for r in rows),D(0)) for j in range(5)] for i in range(5)]
        dd,ee,mm=g[0][0],g[1][1],g[2][2]
        def cosine(i,j):
            return None if g[i][i]==0 or g[j][j]==0 else str(g[i][j]/(g[i][i]*g[j][j]).sqrt())
        totals.append(dict(label=LABELS[k],moments=[[str(x) for x in line] for line in g],
            relative_change_l2=None if dd==0 else str((ee/dd).sqrt()),
            mapped_difference_l2_ratio=None if dd==0 else str((mm/dd).sqrt()),
            direction_projection=None if dd==0 else str(g[0][2]/dd),
            cos_difference_mapped=cosine(0,2),cos_difference_A_defect=cosine(0,3),cos_difference_H_defect=cosine(0,4)))
    return dict(gram=[[str(sum((number(r['gram']['value'][i][j]) for r in rows),D(0))) for j in range(5)] for i in range(5)],pairs=totals)


def review(data):
    with localcontext() as ctx:
        ctx.prec=80
        if data['status']!='statistics_complete_requires_independent_review':raise ValueError('incomplete scan')
        shape=data['shape'];rows=data['slabs'];a=data['arithmetic']
        if len(shape)!=3 or any(type(n)!=int or n<=0 for n in shape):raise ValueError('shape')
        if a['rounding_mode_code']!=0 or a['rounding_mode']!='FE_TONEAREST':raise ValueError('rounding mode')
        nmant=a['nmant'];eps=number(a['eps'])
        if type(nmant)!=int or nmant<52 or abs(eps-D(2)**(-nmant))>D('1e-35')*eps:raise ValueError('precision metadata')
        if data['labels']!=['AP','AF','AM','HP','HF','HM']:raise ValueError('field order')
        claims=data['source_claims']
        if len(claims)!=6 or len({c['path'] for c in claims})!=6:raise ValueError('sources')
        expected=[c['sha256'] for c in claims]
        size=shape[0]*shape[1]*shape[2]*8
        if any(c['size_bytes']!=size for c in claims):raise ValueError('source size')
        if any(len(h)!=64 or any(c not in '0123456789abcdef' for c in h) for h in expected):raise ValueError('SHA syntax')
        if any(data[k]!=expected for k in ('hashes_before','hashes_scan','hashes_after')):raise ValueError('SHA disagreement')
        if data['source_stats_before']!=data['source_stats_after'] or len(data['source_stats_before'])!=6:raise ValueError('stat disagreement')
        if any(len(s)!=5 or any(type(v)!=int or v<0 for v in s) or s[2]!=size for s in data['source_stats_before']):raise ValueError('stat schema/size')
        if data['field_bytes_read']!=18*size:raise ValueError('I/O budget')
        starts=list(range(0,shape[0],32))
        if [r['first_group'] for r in rows]!=starts:raise ValueError('missing/duplicate/out-of-order slab')
        max_tau=D(0)
        for start,row in zip(starts,rows):
            count=min(32,shape[0]-start)
            if row['group_count']!=count or row['block']!=start//128 or row['count']!=count*shape[1]*shape[2]:raise ValueError('slab extent/block')
            tau=64*D(row['count'])*eps
            if tau>=D('.01'):raise ValueError('insufficient accumulation precision')
            max_tau=max(max_tau,tau);g,absolute=matrix(row['gram'],tau)
            lo=[number(x) for x in row['minima']];hi=[number(x) for x in row['maxima']]
            if len(lo)!=6 or len(hi)!=6 or any(x<0 or x>y for x,y in zip(lo,hi)):raise ValueError('original field extrema')
            if len(row['pairs'])!=4:raise ValueError('pair coverage')
            for k,pair in enumerate(row['pairs']):
                if pair['label']!=LABELS[k]:raise ValueError('wrong endpoint combination')
                direct,_=matrix(pair['moments'],tau)
                errors=vector(pair['reconstruction_error_square']);vector(pair['linf'])
                residual=number(pair['identity_linf']);bound=number(pair['identity_bound_max'])
                if not 0<=residual<=bound:raise ValueError('formation identity')
                if any(x>bound for x in vector(pair['reconstruction_error_linf'])) or any(x>D(row['count'])*bound*bound*(1+tau) for x in errors):raise ValueError('basis reconstruction scale')
                c=COEFFICIENTS[k]
                for i in range(5):
                    for j in range(5):
                        predicted=sum((D(c[i][u]*c[j][v])*g[u][v] for u in range(5) for v in range(5)),D(0))
                        scale=sum((abs(D(c[i][u]*c[j][v]))*absolute[u][v] for u in range(5) for v in range(5)),D(0))
                        # 实测重建差的Cauchy尺度加归约容差；是内部一致性核，不是源物理解误差。
                        error=(errors[i]*direct[j][j]).sqrt()+(errors[j]*direct[i][i]).sqrt()+(errors[i]*errors[j]).sqrt()
                        if abs(predicted-direct[i][j])>error*(1+tau)+tau*scale:
                            raise ValueError('direct/Gram disagreement')
        blocks={str(b):summarize([r for r in rows if r['block']==b]) for b in range((shape[0]+127)//128)}
        return dict(status='small_statistics_consistent',slabs=len(rows),blocks=blocks,total=summarize(rows),
            decimal_precision=80,maximum_reduction_tolerance=str(max_tau),
            full_field_reread=False,physical_validation=False,strict_error_bound=False,new_maps=0,new_material=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    result=review(json.loads(args.input.read_text()))
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
