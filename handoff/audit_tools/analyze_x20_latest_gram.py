"""Compare exact bounded minima; distinguish unresolved blocks and field validation."""
from fractions import Fraction as F
from decimal import Decimal,localcontext
from pathlib import Path
import json,hashlib,math
from handoff.audit_tools.bounded_window_gram import exact_qp,dot,matvec


def decimal(x):
    with localcontext() as c:c.prec=70;return str(Decimal(x.numerator)/Decimal(x.denominator))
def cert(x):return dict(numerator=str(x.numerator),denominator=str(x.denominator),decimal=decimal(x))
def encode(r,g):
    x=r['coefficients'];inv=r.get('inverse_hessian');h=[row[1:] for row in g[1:]]
    return dict(status=r['status'],coefficients_exact=[cert(v) for v in x],coefficients_float=list(map(float,x)),
                minimum_squared_exact=cert(r['value']),exact_dual_gap=cert(r['gap']),faces_examined=r['faces_examined'],
                pivots_exact=[cert(v) for v in r['pivots']],
                hessian_condition_inf=None if inv is None else decimal(max(sum(map(abs,row)) for row in h)*max(sum(map(abs,row)) for row in inv)),
                weight_l1=decimal(abs(1-sum(x))+sum(map(abs,x))))


def main():
    root=Path('outputs/review-20260925');folder=root/'x20-latest-basis-82441-received';ev=Path('handoff/evidence')
    ap=ev/'20261001-x20-latest-basis-82441-review.json';a=json.loads(ap.read_text());assert a['independent_audit'] and a['job_id']==82441
    receipt=a['receipt'];bp=folder/'basis.json';claim=next(c for c in receipt['files'] if c['path']=='basis.json')
    assert bp.stat().st_size==claim['size_bytes'] and hashlib.sha256(bp.read_bytes()).hexdigest()==claim['sha256']
    rows=json.loads(bp.read_text())['slabs'];assert len(rows)==301
    def gram(sub):return [[sum((F(r['gram'][i][j]) for r in sub),F(0)) for j in range(4)] for i in range(4)]
    g=gram(rows);assert all(math.isclose(float(g[i][j]),a['gram'][i][j],rel_tol=3e-15) for i in range(4) for j in range(4))
    global_result=encode(exact_qp(g),g);blocks=[];total=F(0);selected_total=F(0);unresolved=[];unresolved_scale=F(0)
    for b in range(76):
        sub=[r for r in rows if r['block']==b];assert sub
        gb=gram(sub);anchor=gb[0][0];row=dict(block=b,first_group=sub[0]['first_group'],group_count=sum(r['group_count'] for r in sub),anchor_squared=cert(anchor))
        try:
            rr=exact_qp(gb);row.update(encode(rr,gb));x=rr['coefficients'];total+=rr['value']
        except ValueError as exc:
            x=[F(0)]*3;row.update(status='unresolved_kept_at_anchor',error=str(exc),coefficients_exact=[cert(v) for v in x],coefficients_float=[0.,0.,0.]);unresolved.append(b);unresolved_scale+=anchor;total+=anchor
        selected=[F(9,10)*v for v in x];vec=[F(1)]+selected;selected_value=dot(vec,matvec(gb,vec));assert selected_value>=0
        row.update(selected_coefficients_exact=[cert(v) for v in selected],selected_coefficients_float=list(map(float,selected)),selected_squared=cert(selected_value));selected_total+=selected_value;blocks.append(row)
        print('block',b,row['status'],flush=True)
    result=dict(source_job=82441,audit_sha256=hashlib.sha256(ap.read_bytes()).hexdigest(),basis_sha256=claim['sha256'],
                coefficient_l1_cap=17,step_safety=.9,arithmetic='exact rational sum of stored binary64 slab Gram entries',global_result=global_result,
                global_minimum_l2_ratio=math.sqrt(float(F(int(global_result['minimum_squared_exact']['numerator']),int(global_result['minimum_squared_exact']['denominator']))/g[0][0])),
                blocks=blocks,unresolved_blocks=unresolved,unresolved_anchor_squared_fraction=float(unresolved_scale/g[0][0]),
                all_block_minima_certified=not unresolved,blockwise_minimum_l2_ratio=None if unresolved else math.sqrt(float(total/g[0][0])),
                blockwise_feasible_anchor_retained_l2_ratio=math.sqrt(float(total/g[0][0])),blockwise_selected_l2_ratio=math.sqrt(float(selected_total/g[0][0])),
                scope='stored Gram prediction only; no full-field positivity/Linf/boundary or true-map validation',candidate_written=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False)
    target=ev/'20261001-x20-82441-bounded-gram-analysis.json';assert not target.exists();target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('blocks','global_result')},indent=2))


if __name__=='__main__':main()
