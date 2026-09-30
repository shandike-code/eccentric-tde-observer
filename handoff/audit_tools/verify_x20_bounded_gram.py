"""Independent exact determinant and supporting-plane verification, no QP solve."""
from fractions import Fraction as F
from itertools import permutations
from pathlib import Path
import json,hashlib


def det(a):
    n=len(a);result=F(0)
    for perm in permutations(range(n)):
        term=F((-1)**sum(perm[i]>perm[j] for i in range(n) for j in range(i+1,n)))
        for i,j in enumerate(perm):term*=a[i][j]
        result+=term
    return result

def rational(c):return F(int(c['numerator']),int(c['denominator']))
def scalar(g,v):return sum((g[i][j]*v[i]*v[j] for i in range(len(v)) for j in range(len(v))),F(0))


def check(g,row):
    raw=[rational(v) for v in row['coefficients_exact']];w=[1-sum(raw)]+raw;assert sum(map(abs,w))<=17
    if not any(x for r in g for x in r):
        assert row['status']=='exact_zero_gram' and raw==[0]*3;return
    h=[r[1:] for r in g[1:]];pd=all(det([r[:n] for r in h[:n]])>0 for n in (1,2,3));whole=det(g)
    if row['status']=='unresolved_kept_at_anchor':
        assert raw==[0]*3 and (not pd or whole<0 or g[0][0]<=0);return
    assert pd and whole>=0
    v=[F(1)]+raw;value=scalar(g,v);assert value==rational(row['minimum_squared_exact']) and value>=0
    grad=[2*sum((g[i+1][j]*v[j] for j in range(4)),F(0)) for i in range(3)]
    supports=[]
    for i in range(4):
        for j in range(4):
            if i!=j:
                weights=[F(0)]*4;weights[i]=9;weights[j]=-8
                supports.append(sum((grad[k]*(weights[k+1]-raw[k]) for k in range(3)),F(0)))
    assert min(supports)==0 and rational(row['exact_dual_gap'])==0


def main():
    p=Path('handoff/evidence/20261001-x20-82441-bounded-gram-analysis.json');d=json.loads(p.read_text())
    rows=json.loads(Path('outputs/review-20260925/x20-latest-basis-82441-received/basis.json').read_text())['slabs']
    def gram(sub):return [[sum((F(r['gram'][i][j]) for r in sub),F(0)) for j in range(4)] for i in range(4)]
    check(gram(rows),d['global_result']);assert len(d['blocks'])==76
    for i,row in enumerate(d['blocks']):
        assert row['block']==i;g=gram([r for r in rows if r['block']==i]);check(g,row)
        x=[rational(v) for v in row['selected_coefficients_exact']]
        assert x==[F(9,10)*rational(v) for v in row['coefficients_exact']]
        assert scalar(g,[F(1)]+x)==rational(row['selected_squared'])
    out=Path('handoff/evidence/20261001-x20-82441-bounded-gram-verification.json');assert not out.exists()
    result=dict(source_job=82441,analysis_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),basis_sha256=d['basis_sha256'],
                exact_principal_determinants_checked=True,exact_supporting_plane_certificates_checked=True,all_76_blocks_retained=True,
                unresolved_blocks=d['unresolved_blocks'],unresolved_coefficients_zero=True,selected_coefficients_exactly_nine_tenths=True,
                field_constraints_verified=False,true_map_verified=False,scope='exact certificates for stored slab Gram rational sums')
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
