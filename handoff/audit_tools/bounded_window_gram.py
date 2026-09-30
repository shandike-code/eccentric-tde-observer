"""Exact rational convex QP on stored Gram entries, with no spectral truncation."""
from fractions import Fraction as F
from itertools import product,combinations


def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))
def matvec(a,b):return [dot(r,b) for r in a]


def solve(a,b):
    n=len(b);rows=[list(r)+[v] for r,v in zip(a,b)]
    for j in range(n):
        piv=next((i for i in range(j,n) if rows[i][j]),None)
        if piv is None:raise ValueError('singular equality system')
        rows[j],rows[piv]=rows[piv],rows[j]
        q=rows[j][j];rows[j]=[v/q for v in rows[j]]
        for i in range(n):
            if i!=j:
                c=rows[i][j];rows[i]=[u-c*v for u,v in zip(rows[i],rows[j])]
    return [r[-1] for r in rows]


def exact_qp(gram,cap=17):
    if cap<1:raise ValueError('anchor excluded')
    g=[[F(v) for v in row] for row in gram]
    if len(g)!=4 or any(len(r)!=4 for r in g) or any(g[i][j]!=g[j][i] for i in range(4) for j in range(4)):
        raise ValueError('finite symmetric 4x4 Gram required')
    if not any(v for row in g for v in row):
        return dict(status='exact_zero_gram',coefficients=[F(0)]*3,value=F(0),gap=F(0),faces_examined=0,pivots=[])
    a=g[0][0];b=g[0][1:];h=[r[1:] for r in g[1:]]
    if a<=0:raise ValueError('nonpositive anchor Gram; no regularization')
    # Exact LDL positivity certificate for the full, unmodified three-direction Hessian.
    l=[[F(i==j) for j in range(3)] for i in range(3)];p=[]
    for i in range(3):
        p.append(h[i][i]-sum((l[i][k]**2*p[k] for k in range(i)),F(0)))
        if p[i]<=0:raise ValueError('nonpositive Hessian pivot; retain unresolved direction')
        for j in range(i+1,3):l[j][i]=(h[j][i]-sum((l[j][k]*l[i][k]*p[k] for k in range(i)),F(0)))/p[i]
    invcols=[solve(h,[F(i==j) for i in range(3)]) for j in range(3)]
    inv=[[invcols[j][i] for j in range(3)] for i in range(3)]
    x0=matvec(inv,[-v for v in b]);unconstrained=a+dot(b,x0)
    if unconstrained<0:raise ValueError('negative full-Gram Schur complement; no repair')
    # |1-sum x|+sum |x|<=cap is the intersection of all 16 sign halfspaces.
    faces=[([F(s[j+1]-s[0]) for j in range(3)],F(cap-s[0])) for s in product((-1,1),repeat=4) if len(set(s))>1]
    vertices=[]
    for i in range(4):
        for j in range(4):
            if i!=j:
                w=[F(0)]*4;w[i]=F(cap+1,2);w[j]=-F(cap-1,2);vertices.append(w[1:])
    examined=0
    for size in range(4):
        for active in combinations(range(len(faces)),size):
            examined+=1
            c=[faces[i][0] for i in active];limits=[faces[i][1] for i in active]
            if size:
                hi=[matvec(inv,row) for row in c]
                schur=[[dot(row,v) for v in hi] for row in c]
                try:mu=solve(schur,[dot(row,x0)-limit for row,limit in zip(c,limits)])
                except ValueError:continue # redundant equality faces, not discarded basis directions
                if any(v<0 for v in mu):continue
                x=[x0[j]-sum((v*hi[i][j] for i,v in enumerate(mu)),F(0)) for j in range(3)]
            else:x=x0
            if any(dot(row,x)>limit for row,limit in faces):continue
            value=a+2*dot(b,x)+dot(x,matvec(h,x))
            grad=[2*v for v in [u+v for u,v in zip(b,matvec(h,x))]]
            lower=value+min(dot(grad,[u-v for u,v in zip(vertex,x)]) for vertex in vertices)
            assert value>=0 and value-lower==0,'exact convex supporting-plane certificate failed'
            assert abs(1-sum(x))+sum(map(abs,x))<=cap
            return dict(status='certified_stored_gram_minimum',coefficients=x,value=value,gap=value-lower,
                        faces_examined=examined,active_faces=list(active),pivots=p,unconstrained_value=unconstrained,
                        inverse_hessian=inv)
    raise ArithmeticError('bounded face enumeration produced no KKT certificate')
