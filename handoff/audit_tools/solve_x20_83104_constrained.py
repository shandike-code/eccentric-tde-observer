"""Exact convex QP for normalized radiation+heating with known-point constraints."""
from fractions import Fraction as F
from itertools import product,combinations
from pathlib import Path
import hashlib,json,math
from handoff.audit_tools.bounded_window_gram import dot,matvec,solve
from handoff.audit_tools.verify_x20_bounded_gram import det,scalar,rational
from handoff.audit_tools.analyze_x20_latest_gram import cert


def constrained_qp(g,faces):
    if len(g)!=4 or any(len(r)!=4 for r in g) or any(g[i][j]!=g[j][i] for i in range(4) for j in range(4)):raise ValueError('symmetric 4x4 required')
    h=[r[1:] for r in g[1:]];b=g[0][1:]
    if g[0][0]<=0 or any(det([r[:n] for r in h[:n]])<=0 for n in (1,2,3)) or det(g)<0:raise ValueError('nonpositive Gram; no repair')
    invcols=[solve(h,[F(i==j) for i in range(3)]) for j in range(3)]
    inv=[[invcols[j][i] for j in range(3)] for i in range(3)]
    x0=matvec(inv,[-v for v in b]);examined=0
    for n in range(4):
        for active in combinations(range(len(faces)),n):
            examined+=1;c=[faces[i][0] for i in active];limits=[faces[i][1] for i in active]
            if n:
                hi=[matvec(inv,r) for r in c]
                try:mu=solve([[dot(r,v) for v in hi] for r in c],[dot(r,x0)-v for r,v in zip(c,limits)])
                except ValueError:continue
                if any(v<0 for v in mu):continue
                x=[x0[j]-sum(mu[i]*hi[i][j] for i in range(n)) for j in range(3)]
            else:x=x0;mu=[]
            if any(dot(r,x)>v for r,v in faces):continue
            return dict(coefficients=x,multipliers=[2*v for v in mu],active=list(active),examined=examined,value=scalar(g,[F(1)]+x))
    raise ValueError('no exact feasible KKT solution')


def verify(g,faces,r):
    # 独立检查行列式和KKT，不重新调用求解器；精确正半定+支持平面给全局最小证书。
    h=[v[1:] for v in g[1:]]
    assert all(det([v[:n] for v in h[:n]])>0 for n in (1,2,3)) and det(g)>=0
    x=r['coefficients'];lam=r['multipliers'];active=r['active']
    assert len(x)==3 and len(lam)==len(active) and len(set(active))==len(active)
    assert all(v>=0 for v in lam) and all(dot(row,x)<=limit for row,limit in faces)
    assert all(dot(faces[i][0],x)==faces[i][1] for i in active)
    for j in range(3):
        assert 2*(g[0][j+1]+sum(g[j+1][k+1]*x[k] for k in range(3)))+sum(v*faces[i][0][j] for v,i in zip(lam,active))==0
    assert r['value']==scalar(g,[F(1)]+x)>=0


def inputs(locate=lambda p:p):
    root=Path('outputs/review-20260925');ev=Path('handoff/evidence')
    ap=ev/'20261002-x20-constrained-basis-83104-review.json';a=json.loads(ap.read_text());assert a['job_id']==83104 and a['independent_audit']
    bp=locate(root/'x20-constrained-basis-83104-received/basis.json');rows=json.loads(bp.read_text())['slabs']
    claim=next(v for v in a['receipt']['files'] if v['path']=='basis.json');assert hashlib.sha256(bp.read_bytes()).hexdigest()==claim['sha256']
    gr=[[sum((F(r['gram'][i][j]) for r in rows),F(0)) for j in range(4)] for i in range(4)]
    hp=ev/'20261001-x20-82989-heating-screen.json';heat=json.loads(hp.read_text());gh=[[rational(v) for v in r] for r in heat['exact_stored_vector_gram']]
    assert heat['fields']==a['fields']
    sp=locate(root/'x20-subnormal-audit-83075-received/exact-signs.json');sa=ev/'20261001-x20-subnormal-83075-review.json';signaudit=json.loads(sa.read_text())
    assert signaudit['integer_certificates_verified'] and signaudit['code_and_source_claims_verified']
    claim=next(v for v in signaudit['receipt']['files'] if v['path']=='exact-signs.json');assert hashlib.sha256(sp.read_bytes()).hexdigest()==claim['sha256']
    faces=[([F(s[j+1]-s[0]) for j in range(3)],F(17-s[0])) for s in product((-1,1),repeat=4) if len(set(s))>1]
    tuples=sorted({tuple(c['source_hex']) for slab in json.loads(sp.read_text())['slabs'] for row in slab['checks'] for c in row['cases']})
    for values in tuples:
        v=[F(float.fromhex(x)) for x in values];scale=max(v);assert scale>0 and min(v)>=0
        # v0+sum c_j(vj-v0)>=0；用精确正比例缩放以去除次正规量级。
        face=([(v[0]-z)/scale for z in v[1:]],v[0]/scale)
        if face not in faces:faces.append(face)
    g=[[(gr[i][j]/gr[0][0]+gh[i][j]/gh[0][0])/2 for j in range(4)] for i in range(4)]
    claims=[dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (ap,bp,hp,sp,sa)]
    return g,gr,gh,faces,tuples,claims


def run():
    g,gr,gh,faces,tuples,claims=inputs();r=constrained_qp(g,faces);verify(g,faces,r)
    selected=[float(F(9,10)*v) for v in r['coefficients']];x=list(map(F,selected))
    assert all(dot(row,x)<=limit for row,limit in faces)
    ratios={name:math.sqrt(float(scalar(mat,[F(1)]+x)/mat[0][0])) for name,mat in [('radiation',gr),('heating',gh)]}
    raw_ratios={name:math.sqrt(float(scalar(mat,[F(1)]+r['coefficients'])/mat[0][0])) for name,mat in [('radiation',gr),('heating',gh)]}
    result=dict(source_job=83104,source_claims=claims,objective='equal sum of anchor-normalized radiation and heating squared defects',
        objective_gram=[[cert(v) for v in row] for row in g],radiation_gram=[[cert(v) for v in row] for row in gr],heating_gram=[[cert(v) for v in row] for row in gh],
        constraints=[dict(normal=[cert(v) for v in row],limit=cert(limit)) for row,limit in faces],known_source_tuples=[list(t) for t in tuples],
        coefficients_exact=[cert(v) for v in r['coefficients']],multipliers_exact=[cert(v) for v in r['multipliers']],active=r['active'],faces_examined=r['examined'],objective_value=cert(r['value']),
        exact_kkt_verified=True,coefficient_l1_cap=17,step_safety=.9,selected_coefficients=selected,raw_ratios=raw_ratios,selected_ratios=ratios,
        selected_known_constraints_exactly_verified=True,full_field_nonnegative_verified=False,true_map_verified=False,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False)
    with Path('handoff/evidence/20261002-x20-83104-constrained-candidate.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(raw_coefficients=list(map(float,r['coefficients'])),selected=selected,raw_ratios=raw_ratios,ratios=ratios,active=r['active'],faces=len(faces),tuples=len(tuples),examined=r['examined']),indent=2))

if __name__=='__main__':run()
