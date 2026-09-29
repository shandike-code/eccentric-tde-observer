"""One field scan, then a bounded spectral-feasibility certificate; zero maps."""
import argparse,itertools,math,resource,signal,sys,time
import numpy as np
from operations import x20_history_operator as core
from operations.x20_history_scan_v2 import require_scan_allocation
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused


def hull(points):
    pts=sorted(set(tuple(map(float,p)) for p in points))
    if len(pts)<3:raise ValueError('degenerate coefficient polygon')
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def side(values):
        stack=[]
        for p in values:
            while len(stack)>1 and cross(stack[-2],stack[-1],p)<=0:stack.pop()
            stack.append(p)
        return stack
    return np.asarray(side(pts)[:-1]+side(pts[::-1])[:-1])


def clip_polygon(poly,a,b):
    """Intersect a convex polygon with a coefficient halfspace, not field clipping."""
    out=[]
    for x,y in zip(poly,np.roll(poly,-1,axis=0)):
        fx=float(a@x-b);fy=float(a@y-b)
        if fx<=0:out.append(x)
        if (fx<0<fy) or (fy<0<fx):out.append(x+(-fx/(fy-fx))*(y-x))
    return np.asarray(out).reshape(-1,2)


def coefficient_plane(flux):
    f=np.asarray(flux,float);scale=max(abs(f))
    if scale<=0 or not np.isfinite(f).all():raise ValueError('invalid equality')
    f=f/scale;k=1+int(np.argmax(abs(f[1:])))
    if f[k]==0:raise ValueError('equality has no direction')
    free=[i for i in range(3) if i!=k-1];anchor=np.zeros(3);anchor[k-1]=-f[0]/f[k]
    basis=np.zeros((3,2))
    for j,i in enumerate(free):basis[i,j]=1;basis[k-1,j]=-f[i+1]/f[k]
    vertices=[]
    for i,j in itertools.permutations(range(4),2):
        w=np.zeros(4);w[i]=9;w[j]=-8;vertices.append(w[[0,2,3]])
    cut=[]
    for x in vertices:
        if f[0]+f[1:]@x==0:cut.append(x[free])
    for x,y in itertools.combinations(vertices,2):
        fx=float(f[0]+f[1:]@x);fy=float(f[0]+f[1:]@y)
        if (fx<0<fy) or (fy<0<fx):cut.append((x+(-fx/(fy-fx))*(y-x))[free])
    return anchor,basis,hull(cut)


def minimize_polygon(g,anchor,basis,poly,safety=.9):
    g=np.asarray(g,float);g=g/g[0,0]
    base=np.r_[1,safety*anchor];directions=np.vstack((np.zeros(2),safety*basis))
    a=directions.T@g@directions;b=directions.T@g@base;constant=float(base@g@base)
    if np.linalg.eigvalsh(a).min()<=0:raise ValueError('quadratic not strictly convex in plane')
    candidates=[];unconstrained=np.linalg.solve(a,-b)
    def inside(z):
        return all(np.linalg.det(np.stack((y-x,z-x)))>=0 for x,y in zip(poly,np.roll(poly,-1,axis=0)))
    if inside(unconstrained):candidates.append(unconstrained)
    for x,y in zip(poly,np.roll(poly,-1,axis=0)):
        v=y-x;curvature=float(v@a@v)
        if curvature==0:candidates.append(x);continue
        t=-float(v@(a@x+b))/curvature
        candidates.append(x+(min(1.,max(0.,t)))*v)
    def value(z):return float(constant+2*b@z+z@a@z)
    point=min(candidates,key=value);upper=value(point);gradient=2*(a@point+b)
    lower=upper+min(float(gradient@(v-point)) for v in poly)
    scale=abs(constant)+2*np.abs(b)@np.abs(point)+np.abs(point)@np.abs(a)@np.abs(point)
    allowance=8192*np.finfo(float).eps*float(1+scale+max(np.abs(gradient)@np.abs(v-point) for v in poly))
    if upper<=0 or not np.isfinite([upper,lower,allowance]).all():raise ValueError('invalid quadratic bound')
    return point,dict(squared_upper=upper,squared_support_lower=lower,roundoff_allowance=allowance,
        l2_upper=math.sqrt(upper),l2_conservative_lower=math.sqrt(max(0,lower-allowance)))


def spectral_system(spectra):
    fs=np.asarray(spectra,float)
    if fs.ndim!=2 or fs.shape[0]!=6 or not np.isfinite(fs).all() or np.any(fs<0):raise ValueError('six nonnegative spectra required')
    scale=max(math.fsum(fs[1]),math.fsum(fs[2]))
    if scale<=0:raise ValueError('zero original boundary scale')
    # 先对原单位谱求差，再统一无量纲化，避免先除大尺度导致额外相消。
    a,b,c,h,j,k=fs;r=(c-b)/scale
    dr=np.stack(((b-a)-(c-b),(j-h)-(c-b),(k-j)-(c-b)),axis=1)/scale
    di=np.stack((a-b,h-b,j-b),axis=1)/scale
    flux=np.r_[math.fsum(r),[math.fsum(dr[:,i]) for i in range(3)]]
    return dict(r=r,dr=dr,di=di,base_flux=math.fsum(b)/scale,flux=flux,
        original_boundary_l1=math.fsum(abs(r)),boundary_scale=scale)


def spectral_cut(system,c,fraction,limit):
    r,dr,di=system['r'],system['dr'],system['di'];v=r+fraction*(dr@c)
    signed=float(system['flux'][0]+fraction*(system['flux'][1:]@c))
    input_flux=system['base_flux']+fraction*float(np.array([math.fsum(di[:,i]) for i in range(3)])@c)
    denominator=input_flux+max(signed,0.)
    if denominator<=0:raise ValueError('nonpositive proposed boundary flux')
    numerator=math.fsum(abs(v));sign=np.sign(v)
    # 在raw净变化为零的平面上，full/half净变化符号固定，max分母是仿射函数。
    offset=system['base_flux']+max((1-fraction)*system['flux'][0],0.)
    a=fraction*(np.array([math.fsum(sign*dr[:,i]) for i in range(3)])/limit-np.array([math.fsum(di[:,i]) for i in range(3)]))
    b=offset-math.fsum(sign*r)/limit
    return dict(fraction=fraction,numerator=numerator,denominator=denominator,ratio_to_limit=numerator/(limit*denominator),
        a=a.tolist(),b=b,positive_groups=int(np.count_nonzero(v>0)),negative_groups=int(np.count_nonzero(v<0)))


def solve(gram,spectra,maximum_iterations=64):
    system=spectral_system(spectra);limit=system['original_boundary_l1']*(1+1e-10)
    if limit<=0:raise ValueError('zero original spectral defect')
    anchor,basis,poly=coefficient_plane(system['flux']);initial=poly.copy();rows=[]
    for iteration in range(maximum_iterations):
        point,bound=minimize_polygon(gram,anchor,basis,poly);c=anchor+basis@point
        cuts=[spectral_cut(system,c,t,limit) for t in (.9,.45)]
        record=dict(iteration=iteration,polygon=poly.tolist(),raw_coefficients=c.tolist(),bound=bound,cuts=cuts)
        rows.append(record)
        if bound['l2_conservative_lower']>.8:
            status='no_20pct_candidate_in_registered_plane';break
        if all(z['ratio_to_limit']<=1 for z in cuts):
            status='algebraic_candidate_requires_full_field_validation';break
        changed=False
        for cut in cuts:
            if cut['ratio_to_limit']<=1:continue
            a=np.asarray(cut['a']);a2=basis.T@a;b2=cut['b']-float(a@anchor)
            new=clip_polygon(poly,a2,b2)
            if len(new)<3:
                status='empty_spectral_cut_polygon_requires_review';poly=new;break
            changed=changed or not np.array_equal(poly,new);poly=new
        else:
            if changed:continue
            status='numerical_cut_stagnation_requires_review';break
        break
    else:status='cut_iteration_budget_exhausted'
    return dict(status=status,iterations=rows,initial_polygon=initial.tolist(),plane_anchor=anchor.tolist(),plane_basis=basis.tolist(),
        original_boundary_l1=system['original_boundary_l1'],spectral_limit=limit,boundary_flux_coefficients=system['flux'].tolist(),
        selected_fraction=.9,coefficient_l1_cap=17,maximum_cut_iterations=maximum_iterations,
        registered_plane_only=True,positivity_and_linf_not_checked=True,candidate_written=False,
        true_map_performed=False,strict_physical_error_bound=False)


def collect(paths,shape,geometry,checkpoint=lambda:None):
    columns=[[] for _ in paths]
    for start,aa in core.chunks(paths,shape):
        checkpoint()
        for store,z in zip(columns,aa):store.append(core.boundary_spectrum(z,geometry['mu'],geometry['weight'],geometry['width'][start:start+len(z)]))
    return np.stack([np.concatenate(z) for z in columns])


def execute(out):
    require_scan_allocation();out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        ev=ROOT/'handoff/evidence';claims=[]
        for job,tag,run in [(80862,'subspace','x20-boundary-subspace-20260929'),(80925,'capped','x20-capped-subspace-20260929')]:
            ap=ev/f'20260929-x20-{tag}-review.json';tp=ev/f'20260929-x20-{tag}-{job}-terminal.json'
            review=pipeline.read(ap)
            if not review['independent_small_statistic_reduction'] or review['new_maps'] or review['new_material_steps'] or review['baseline_replaced']:raise RuntimeError('rejected source review required')
            claims+=core.v.audited_inputs(ROOT/'outputs/hpc'/run,ap,tp,job,['declaration.json','summary.json','prediction.json'])
        previous=ROOT/'outputs/hpc/x20-capped-subspace-20260929';source=pipeline.read(previous/'declaration.json');pred=pipeline.read(previous/'prediction.json')
        if {k for k,v in pred['prediction']['checks'].items() if not v}!={'full_boundary_l1','half_boundary_l1'}:raise RuntimeError('wrong source failure')
        pre=out/'source-preflight';pre.mkdir();plan,geometry=core.prepare(pre,'scan')
        basis=source['basis']
        if [basis[i] for i in (1,2,4,5)]!=plan['field_pairs']:raise RuntimeError('source basis changed')
        claims+=plan['claims']+plan['code']+basis;claims=list({(c['path'],c['sha256']):c for c in claims}.values())
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/f) for f in ('operations/x20_spectral_feasibility.sbatch','tests/test_x20_spectral_feasibility.py','handoff/protocols/x20-spectral-feasibility-v1.md')]
        reused.verify(claims+code)
        reused.immutable(out/'declaration.json',dict(claims=claims,code=code,basis=basis,cases=plan['cases'],source_jobs=[80554,80862,80925],
            maximum_maps=0,maximum_feedback_pairs=0,maximum_field_scans=1,maximum_cut_iterations=64,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,candidate_written=False,
            coefficient_l1_cap=17,selected_fraction=.9,registered_plane_only=True,environment=pipeline.environment()))
        mark('collecting_boundary_spectra');spectra=collect([ROOT/c['path'] for c in basis],pipeline.SHAPE,geometry,reused.checkpoint)
        np.savez(out/'boundary-spectra.npz',spectra=spectra,gram=np.asarray(pred['gram']),original_boundary_coefficients=np.asarray(pred['boundary_coefficients']))
        mark('solving_spectral_feasibility');reused.checkpoint();result=solve(pred['gram'],spectra)
        # 新谱归约与旧大场扫描必须一致；容许普通双精度频率积分的舍入，不改接受门。
        original=pred['prediction']['boundary'][0]['boundary_l1']
        if not np.isclose(result['original_boundary_l1'],original,rtol=1e-12,atol=0):raise RuntimeError('original spectrum scale changed')
        system=spectral_system(spectra);actual_flux=system['flux']*system['boundary_scale'];old=np.asarray(pred['boundary_coefficients'])
        if not np.allclose(actual_flux,old,rtol=1e-12,atol=64*np.finfo(float).eps*system['boundary_scale']):raise RuntimeError('boundary reduction changed')
        result['source_boundary_coefficients']=old.tolist();result['reduced_boundary_coefficients']=actual_flux.tolist()
        reused.immutable(out/'feasibility.json',result);reused.verify(claims+code)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        reused.immutable(out/'summary.json',dict(status=result['status'],new_maps=0,new_feedback_pairs=0,accepted_outer_steps=20,new_material_steps=0,
            baseline_replaced=False,strict_error_bound=False,candidate_written=False,field_scans=1,cut_iterations=len(result['iterations']),
            parent_peak_rss_bytes=peak,wall_s=time.monotonic()-started,historical_failures_retained=True))
        mark(result['status']);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,args.run))
