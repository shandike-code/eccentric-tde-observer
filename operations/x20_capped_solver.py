"""Solve the small boundary-equality quadratic WITH the affine-weight cap."""
import itertools,math
import numpy as np


def solve(gram,flux,cap=17.):
    g=np.asarray(gram,float);f=np.asarray(flux,float)
    if g.shape!=(4,4) or f.shape!=(4,) or not np.isfinite(g).all() or not np.isfinite(f).all() or not np.array_equal(g,g.T):raise ValueError('invalid Gram or boundary')
    if cap<=1 or g[0,0]<=0 or np.max(abs(f))==0:raise ValueError('invalid cap, defect or boundary scale')
    eigen=np.linalg.eigvalsh(g[1:,1:]);scale=float(eigen[-1])
    if scale<=0 or np.any(eigen<=1e-12*scale):raise ValueError('three resolved directions required')
    g=g/g[0,0];a=g[1:,1:];b=g[0,1:];f=f/np.max(abs(f))
    # sum(w)=1与||w||1<=R的完整顶点；c=(w0,w2,w3)，不是逐频选择。
    vertices=[]
    for i,j in itertools.permutations(range(4),2):
        w=np.zeros(4);w[i]=(cap+1)/2;w[j]=-(cap-1)/2;vertices.append(w[[0,2,3]])
    cut=[]
    for x in vertices:
        if f[0]+f[1:]@x==0:cut.append(x.copy())
    # 超平面与所有顶点连线交点的凸包就是切片。包括非边连线只添加内部点。
    for x,y in itertools.combinations(vertices,2):
        fx=float(f[0]+f[1:]@x);fy=float(f[0]+f[1:]@y)
        if (fx<0<fy) or (fy<0<fx):cut.append(x+(-fx/(fy-fx))*(y-x))
    if not cut:raise ValueError('boundary equality has no point inside coefficient cap')
    cut=np.asarray(cut);best=None
    # 平面凸包至多用三个顶点表示；逐个小单纯形求精确二次极小再核重心坐标。
    for n in range(1,4):
        for ids in itertools.combinations(range(len(cut)),n):
            v=cut[list(ids)];c=v[0].copy()
            if n>1:
                t=(v[1:]-c).T
                if np.linalg.matrix_rank(t)<n-1:continue
                try:u=np.linalg.solve(t.T@a@t,-t.T@(a@c+b))
                except np.linalg.LinAlgError:continue
                if np.min(np.r_[1-math.fsum(u),u])<0:continue
                c+=t@u
            w=np.r_[c[0],1-math.fsum(c),c[1:]]
            if math.fsum(abs(w))>cap*(1+1e-13):continue
            value=float(1+2*b@c+c@a@c)
            if best is None or value<best[0]:best=(value,c)
    if best is None:raise ArithmeticError('no feasible quadratic minimum')
    value,c=best;gradient=2*(a@c+b)
    # 支撑平面的最小值给此小型凸二次问题的后验下界，并非物理真解误差界。
    lower=value+min(float(gradient@(v-c)) for v in cut)
    magnitude=1+2*np.abs(b)@np.abs(c)+np.abs(c)@np.abs(a)@np.abs(c)
    margin=4096*np.finfo(float).eps*float(magnitude+max(np.abs(gradient)@np.abs(v-c) for v in cut))
    if value<0 or value-lower>max(1e-9,margin):raise ArithmeticError('quadratic optimum not certified')
    equality=float(f[0]+f[1:]@c)
    if abs(equality)>1e-10*(1+np.linalg.norm(f[1:])*np.linalg.norm(c)):raise ArithmeticError('boundary equality violated')
    return c,dict(raw_coefficients=c.tolist(),raw_weights=[float(c[0]),1-math.fsum(c),float(c[1]),float(c[2])],
        eigenvalues=eigen.tolist(),retained_rank=3,relative_cutoff=1e-12,coefficient_l1_cap=cap,
        normalized_boundary_residual=equality,cut_vertex_count=len(cut),squared_upper=value,
        squared_support_lower=lower,roundoff_allowance=margin,l2_ratio=math.sqrt(value),
        l2_conservative_lower=math.sqrt(max(0,lower-margin)),strict_error_bound=False,
        constraint='coefficient L1 cap and signed boundary equality solved jointly')
