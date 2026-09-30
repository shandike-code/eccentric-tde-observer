"""Dimension-aware small-data necessary-condition diagnostic; no radiation maps."""
import argparse,hashlib,itertools,json,math,platform,subprocess,tarfile,time
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import minimize,linprog

ROOT=Path(__file__).resolve().parents[1]
D=lambda x:Decimal.from_float(float(x))


def claim(path):
    path=Path(path);return dict(path=str(path.relative_to(ROOT)),size_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def cap_geometry(dimension):
    if not isinstance(dimension,int) or not 1<=dimension<=8:raise ValueError("dimension must be 1..8")
    indices=[i for i in range(dimension+1) if i!=1]
    vertices=[]
    for i,j in itertools.permutations(range(dimension+1),2):
        w=np.zeros(dimension+1);w[i]=9;w[j]=-8;vertices.append(w[indices])
    rows=[];bounds=[]
    for s in itertools.product((-1,1),repeat=dimension+1):
        a=[s[i]-s[1] for i in indices]
        if any(a):rows.append(a);bounds.append(17-s[1])
    return np.array(vertices),np.array(rows,float),np.array(bounds,float)


def system(spectra, pairs):
    f=np.asarray(spectra,float)
    if f.ndim!=2 or f.shape[0]<3 or not np.isfinite(f).all() or np.any(f<0):raise ValueError('finite nonnegative spectra required')
    if not pairs or any(len(p)!=2 or min(p)<0 or max(p)>=len(f) for p in pairs):raise ValueError('invalid input/output pairs')
    b,c=f[1:3];scale=max(math.fsum(b),math.fsum(c))
    if scale<=0:raise ValueError('positive boundary scale required')
    r=(c-b)/scale
    dr=np.array([(f[j]-f[i])-(c-b) for i,j in pairs]).T/scale
    di=np.array([f[i]-b for i,j in pairs]).T/scale
    return dict(r=r,dr=dr,di=di,base=b/scale,scale=scale,limit=math.fsum(abs(r))*(1+1e-10))


def positive_hessian(gram):
    # 保存的Gram由长双精度积分转存；用70位LDL检查其凸性，不删除小特征方向。
    with localcontext() as ctx:
        ctx.prec=70
        h=[[D(v)/D(gram[0,0]) for v in row[1:]] for row in gram[1:]]
        pivots=[]
        for n in range(len(h)):
            pivot=h[n][n]
            if pivot<=0:raise ValueError('convex positive Gram required; no eigenvalue clipping')
            pivots.append(str(pivot))
            for i in range(n+1,len(h)):
                for j in range(n+1,len(h)):h[i][j]-=h[i][n]*h[n][j]/pivot
    return pivots


def denominator_upper(sys,fraction):
    """Exact affine maximization over all vertices of the registered cap polytope."""
    vv,_,_=cap_geometry(sys['dr'].shape[1])
    with localcontext() as ctx:
        ctx.prec=70;t=D(fraction);b=sum(map(D,sys['base']));r=sum(map(D,sys['r']))
        di=[sum(map(D,col)) for col in sys['di'].T];dr=[sum(map(D,col)) for col in sys['dr'].T]
        values=[]
        for v in vv:
            incoming=b+t*sum(D(x)*y for x,y in zip(v,di))
            outgoing=incoming+r+t*sum(D(x)*y for x,y in zip(v,dr))
            values.append([str(incoming),str(outgoing)])
        exact=max(Decimal(z) for row in values for z in row)
        # 对保存双精度谱系数定义的代数模型取外向上界，绝不调物理谱归一化。
        allowance=Decimal('1e-50')*(1+abs(exact));upper=math.nextafter(float(exact+allowance),math.inf)
        if exact<=0:raise ValueError('positive denominator upper bound required')
        return dict(fraction=fraction,vertex_fluxes_70digit=values,maximum_70digit=str(exact),upper=upper)


def spectral_cut(sys,point,fraction,upper):
    v=sys['r']+fraction*(sys['dr']@point);sign=np.sign(v);limit=sys['limit']
    if limit<=0:raise ValueError('positive spectral defect required')
    with localcontext() as ctx:
        ctx.prec=70;t=D(fraction);lim=D(limit)
        aa=[t*sum(D(s)*D(x) for s,x in zip(sign,col))/lim for col in sys['dr'].T]
        bb=D(upper)-sum(D(s)*D(x) for s,x in zip(sign,sys['r']))/lim
        a=np.array(list(map(float,aa)));b=float(bb)
        # |c_i|<=9；保存切面系数的舍入误差只能向外扩大可行域。
        padding=abs(bb-D(b))+9*sum(abs(x-D(y)) for x,y in zip(aa,a))+Decimal('1e-45')*(1+abs(bb)+sum(map(abs,aa)))
        bound=math.nextafter(float(bb+padding),math.inf)
    exact_den=math.fsum(sys['base'])+fraction*math.fsum(point*np.array([math.fsum(x) for x in sys['di'].T]))+max(math.fsum(v),0.)
    return dict(fraction=fraction,a=a.tolist(),b=bound,outward_padding=float(D(bound)-bb),
        relaxed_ratio=math.fsum(abs(v))/(limit*upper),exact_denominator=exact_den,
        original_denominator_ratio=math.fsum(abs(v))/(limit*exact_den) if exact_den>0 else None,
        positive_groups=int(np.count_nonzero(v>0)),negative_groups=int(np.count_nonzero(v<0)))


def dual_certificate(gram,point,aa,bb,fraction=.9):
    """Convex support lower bound with a bounded-box correction for LP dual residual."""
    g=np.asarray(gram,float);g=g/g[0,0];c=np.asarray(point,float);n=len(c)
    gradient=2*fraction*(g[1:,0]+fraction*g[1:,1:]@c)
    lp=linprog(gradient,A_ub=aa,b_ub=bb,bounds=[(None,None)]*n,method='highs',options={'time_limit':10.})
    if not lp.success:raise RuntimeError('linear support problem unresolved: '+lp.message)
    raw_y=np.asarray(lp.ineqlin.marginals)
    if not np.isfinite(raw_y).all():raise RuntimeError('nonfinite dual')
    # LP容差可能给出微小正乘子。只选非正乘子构造有效的数学对偶点；
    # 改动后的全部梯度残差在下方由有限系数盒补偿，不裁剪任何物理数组。
    y=np.array([min(v,0.) for v in raw_y])
    with localcontext() as ctx:
        ctx.prec=70;gd=[[D(v)/D(gram[0,0]) for v in row] for row in gram]
        p=list(map(D,c));t=D(fraction);u=[D(1)]+[t*x for x in p]
        value=sum(u[i]*gd[i][j]*u[j] for i in range(n+1) for j in range(n+1))
        grad=[2*t*sum(gd[i+1][j]*u[j] for j in range(n+1)) for i in range(n)]
        yd=list(map(D,y));dual=sum(z*D(b) for z,b in zip(yd,bb))
        residual=[grad[j]-sum(z*D(a[j]) for z,a in zip(yd,aa)) for j in range(n)]
        correction=9*sum(map(abs,residual))
        support=value-sum(x*z for x,z in zip(grad,p))+dual-correction
        allowance=Decimal('1e-45')*(1+abs(value)+abs(dual)+correction+sum(map(abs,grad)))
        lower=support-allowance
        if lower<0:l2=0.
        else:l2=math.nextafter(float(lower.sqrt()),-math.inf)
        return dict(squared_value_70digit=str(value),squared_lower_70digit=str(lower),l2_lower=l2,
            raw_dual_multipliers=raw_y.tolist(),dual_multipliers=y.tolist(),positive_raw_dual_indices=np.flatnonzero(raw_y>0).tolist(),
            gradient_70digit=list(map(str,grad)),dual_residual_70digit=list(map(str,residual)),
            residual_box_correction_70digit=str(correction),decimal_allowance=str(allowance),lp_status=lp.message)


def solve(gram,spectra,pairs,maximum_iterations=64):
    n=len(pairs)
    g=np.asarray(gram,float)
    if g.shape!=(n+1,n+1) or not np.isfinite(g).all() or not np.array_equal(g,g.T) or g[0,0]<=0:raise ValueError('invalid Gram')
    pivots=positive_hessian(g)
    sys=system(spectra,pairs);den=[denominator_upper(sys,t) for t in (.9,.45)]
    _,a,b=cap_geometry(n);g0=g/g[0,0];point=np.zeros(n);trace=[]
    def value(c):u=np.r_[1,.9*c];return float(u@g0@u)
    def grad(c):return 1.8*(g0[1:,0]+.9*g0[1:,1:]@c)
    for iteration in range(maximum_iterations):
        row_scale=np.linalg.norm(a,axis=1);an=a/row_scale[:,None];bn=b/row_scale
        opt=minimize(value,point,jac=grad,method='SLSQP',constraints=[{'type':'ineq','fun':lambda c:bn-an@c,'jac':lambda c:-an}],options={'ftol':1e-12,'maxiter':200})
        point=np.asarray(opt.x)
        if not np.isfinite(point).all():raise RuntimeError('nonfinite proposal')
        # 原始完整约束给LP；优化器候选只用于选择支撑面，不把success当证明。
        certificate=dual_certificate(g,point,a,b)
        cuts=[spectral_cut(sys,point,t,d['upper']) for t,d in zip((.9,.45),den)]
        trace.append(dict(iteration=iteration,point=point.tolist(),a=a.tolist(),b=b.tolist(),
            optimizer=dict(success=bool(opt.success),message=opt.message,iterations=int(opt.nit)),certificate=certificate,cuts=cuts))
        if certificate['l2_lower']>.8:status='no_20pct_candidate_in_full_registered_cap';break
        if all(z['relaxed_ratio']<=1 for z in cuts) and np.max(a@point-b)<=1e-10:
            status='relaxed_point_requires_all_original_gates';break
        if not opt.success:status='quadratic_optimizer_unresolved';break
        new=[z for z in cuts if z['relaxed_ratio']>1]
        if not new:status='constraint_precision_unresolved';break
        a=np.vstack([a,*[z['a'] for z in new]]);b=np.r_[b,[z['b'] for z in new]]
    else:status='cut_iteration_budget_exhausted'
    return dict(status=status,trace=trace,denominator_bounds=den,maximum_iterations=maximum_iterations,
        dimension=n,pairs=[list(p) for p in pairs],positive_hessian_ldl_pivots=pivots,
        boundary_limit=sys['limit'],coefficient_l1_cap=17,full_fraction=.9,half_fraction=.45,
        zero_net_boundary_equality_used=False,original_science_gates_changed=False,
        positivity_linf_bolometric_omitted_only_in_relaxation=True,physical_error_bound=False)


def execute(source,out):
    started=time.monotonic();out.relative_to(ROOT/'outputs');out.mkdir(exist_ok=False)
    audit_path=ROOT/'handoff/evidence/20260930-x20-long-chord-review.json'
    audit_claim=claim(audit_path);audit=json.loads(audit_path.read_text())
    if audit.get('job_id')!=81647 or not audit.get('scientific_independent_audit_completed'):raise ValueError('audited 81647 source required')
    archive=source.parent/Path(audit['archive']['path']).name;archive_claim=claim(archive)
    if (archive_claim['sha256'],archive_claim['size_bytes'])!=(audit['archive']['sha256'],audit['archive']['size_bytes']):raise ValueError('source archive changed')
    manifest_path=source/'ARCHIVE_MANIFEST.json';manifest_claim=claim(manifest_path);manifest=json.loads(manifest_path.read_text())
    with tarfile.open(archive) as handle:
        if json.load(handle.extractfile('ARCHIVE_MANIFEST.json'))!=manifest:raise ValueError('source manifest changed')
    files=[];seen=set()
    for c in manifest['files']:
        p=Path(c['path'])
        if p.is_absolute() or '..' in p.parts or str(p) in seen:raise ValueError('invalid inventory path')
        seen.add(str(p));actual=claim(source/p)
        if (actual['sha256'],actual['size_bytes'])!=(c['sha256'],c['size_bytes']):raise ValueError('source bytes changed')
        files.append(actual)
    if {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}!=seen|{'ARCHIVE_MANIFEST.json'}:raise ValueError('extra source files')
    with np.load(source/'expanded-system.npz',allow_pickle=False) as z:gram=z['gram'];spectra=z['spectra']
    if gram.shape!=(5,5) or spectra.shape!=(8,9632):raise ValueError('complete expanded source required')
    with np.load(source/'chord/trial_material.npz',allow_pickle=False) as trial:
        if int(trial['phase_index'])!=1367 or float(trial['step_duration_s'])!=889.419892762322:raise ValueError('physical identity changed')
    pairs=((0,1),(3,4),(4,5),(6,7))
    code=[claim(ROOT/p) for p in ('operations/x20_expanded_feasibility.py','tests/test_x20_expanded_feasibility.py','handoff/protocols/x20-expanded-feasibility-v1.md')]
    write(out/'declaration.json',dict(source_files=files,source_audit=audit_claim,source_archive=archive_claim,source_manifest=manifest_claim,code=code,
        source_job=81647,source_basis=json.loads((source/'expanded-basis.json').read_text()),pairs=pairs,coefficient_dimension=4,
        git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        tracked_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()),
        python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,host=platform.node(),
        maximum_cut_iterations=64,large_fields_read=0,new_maps=0,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False))
    result=solve(gram,spectra,pairs)
    for c in files+code+[audit_claim,archive_claim,manifest_claim]:
        if claim(ROOT/c['path'])!=c:raise RuntimeError('input changed during diagnostic')
    result.update(wall_s=time.monotonic()-started,accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_pairs=0,large_fields_read=0,baseline_replaced=False,candidate_written=False)
    write(out/'result.json',result)
    print(json.dumps(dict(status=result['status'],iterations=len(result['trace']),last=result['trace'][-1]['certificate'],wall_s=result['wall_s']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='outputs/review-20260925/x20-long-chord-81647-received');parser.add_argument('--out',required=True)
    args=parser.parse_args();execute((ROOT/args.source).resolve(),(ROOT/args.out).resolve())
