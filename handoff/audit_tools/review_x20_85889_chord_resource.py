"""Independent small receipt review for one resource slab; no scanner import."""
from decimal import Decimal as D, localcontext
import argparse
import json
from pathlib import Path
from handoff.audit_tools.review_x20_85889_chord_scan import matrix,number,vector,COEFFICIENTS,LABELS


def review(data):
    with localcontext() as ctx:
        ctx.prec=80
        shape=data['shape'];n=32*shape[1]*shape[2];row=data['slab'];a=data['arithmetic']
        if (len(shape)!=3 or any(type(x)!=int or x<=0 for x in shape) or shape[0]<32 or
            data['status']!='resource_probe_complete_requires_review' or data['first_group']!=0 or data['group_count']!=32 or
            row['count']!=n or data['field_bytes_read']!=12*n*8):raise ValueError('resource slab scope')
        if (a['rounding_mode_code']!=0 or type(a['nmant'])!=int or a['nmant']<52 or
            data['peak_rss_bytes']>=6*1024**3 or data['peak_rss_bytes']<=0):raise ValueError('arithmetic/RSS')
        if any(data[k] is not False for k in ('full_field_sha_refreshed','full_field_statistics_complete','physical_inference_authorized','full_scan_authorized','strict_error_bound')):
            raise ValueError('unsupported scientific promotion')
        if data['source_stats_before']!=data['source_stats_after'] or len(data['source_stats_before'])!=6:
            raise ValueError('source stat identity')
        if len(data['slice_sha256'])!=6 or any(len(h)!=64 or any(c not in '0123456789abcdef' for c in h) for h in data['slice_sha256']):raise ValueError('slice SHA')
        claims=data['source_claims'];size=shape[0]*shape[1]*shape[2]*8
        if len(claims)!=6 or len({c['path'] for c in claims})!=6 or any(c['size_bytes']!=size for c in claims):raise ValueError('field claims')
        if any(len(s)!=5 or s[2]!=size for s in data['source_stats_before']):raise ValueError('stat sizes')
        tau=64*D(n)*D(2)**(-a['nmant'])
        if tau>=D('.01'):raise ValueError('precision')
        g,absolute=matrix(row['gram'],tau)
        lo=list(map(number,row['minima']));hi=list(map(number,row['maxima']))
        if len(lo)!=6 or len(hi)!=6 or any(x<0 or x>y for x,y in zip(lo,hi)):raise ValueError('extrema')
        if len(row['pairs'])!=4:raise ValueError('four combinations required')
        for k,pair in enumerate(row['pairs']):
            if pair['label']!=LABELS[k]:raise ValueError('combination')
            direct,_=matrix(pair['moments'],tau);errors=vector(pair['reconstruction_error_square'])
            bound=number(pair['identity_bound_max']);residual=number(pair['identity_linf']);vector(pair['linf'])
            if not 0<=residual<=bound or any(x>bound for x in vector(pair['reconstruction_error_linf'])) or any(x>D(n)*bound*bound*(1+tau) for x in errors):raise ValueError('reconstruction')
            c=COEFFICIENTS[k]
            for i in range(5):
                for j in range(5):
                    predicted=sum((D(c[i][u]*c[j][v])*g[u][v] for u in range(5) for v in range(5)),D(0))
                    scale=sum((abs(D(c[i][u]*c[j][v]))*absolute[u][v] for u in range(5) for v in range(5)),D(0))
                    error=(errors[i]*direct[j][j]).sqrt()+(errors[j]*direct[i][i]).sqrt()+(errors[i]*errors[j]).sqrt()
                    if abs(predicted-direct[i][j])>error*(1+tau)+tau*scale:raise ValueError('direct/Gram disagreement')
        return dict(status='resource_slab_small_statistics_consistent',slabs=1,combinations=4,decimal_precision=80,
                    full_field_sha_refreshed=False,full_scan_authorized=False,physical_validation=False,strict_error_bound=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=review(json.loads(a.input.read_text()))
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
