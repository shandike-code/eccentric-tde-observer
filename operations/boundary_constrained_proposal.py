"""Two fixed directions, one boundary-neutral affine proposal; zero new maps."""
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
import tarfile
import numpy as np
from operations import validate_population_defect_global as valid
from operations.constrained_hybrid_fields import chunks, physical

ROOT, pipeline, reused, fresh = valid.ROOT, valid.pipeline, valid.reused, valid.fresh
SOURCE = ROOT/'outputs/hpc/step21-population-defect-global-20260928'
OUT = ROOT/'outputs/hpc/step21-boundary-constrained-proposal-20260928'


def constrained_coefficients(gram, signed):
    """Minimize ||r0+a*rA+b*rB||^2 with D0+a*DA+b*DB=0 and a,b in [0,1]."""
    g = np.asarray(gram, float); d = np.asarray(signed, float)
    if g.shape != (3,3) or d.shape != (3,) or not np.isfinite(g).all() or not np.isfinite(d).all():
        raise ValueError('finite three-vector Gram matrix and flux coefficients required')
    if not np.array_equal(g, g.T) or np.linalg.eigvalsh(g).min() < -1e-13*np.max(abs(g)):
        raise ValueError('invalid Gram matrix')
    if d[2] == 0:
        raise ValueError('registered elimination requires nonzero second flux direction')
    intercept, slope = -d[0]/d[2], -d[1]/d[2]
    lo, hi = 0., 1.
    if slope == 0:
        if not 0 <= intercept <= 1: raise ValueError('empty boundary-neutral box')
    else:
        bounds = sorted((-intercept/slope, (1-intercept)/slope))
        lo, hi = max(lo,bounds[0]), min(hi,bounds[1])
        if lo > hi: raise ValueError('empty boundary-neutral box')
    c0 = np.array([1.,0.,intercept]); c1 = np.array([0.,1.,slope])
    curvature = float(c1@g@c1)
    if curvature <= 0: raise ValueError('nonpositive one-dimensional objective curvature')
    unconstrained = -float(c1@g@c0)/curvature
    # 这是有界二次最小化的端点选择，不是对物理数组裁剪或重归一化。
    a = lo if unconstrained < lo else hi if unconstrained > hi else unconstrained
    b = intercept+slope*a
    if not 0 <= a <= 1 or not 0 <= b <= 1: raise ValueError('coefficient outside declared box')
    c = np.array([1.,a,b]); square = float(c@g@c)
    if square < 0: raise ValueError('negative predicted squared defect')
    return dict(a=a,b=b,interval=[lo,hi],unconstrained_a=unconstrained,
                predicted_squared_l2=square,predicted_signed_flux=float(c@d),
                boundary_neutral_constraint=True)


def residual_basis(x,y,q,tq,u,tu):
    r0=y-x; rq=tq-q; ru=tu-u
    return r0,rq-r0,ru-rq


def gram_stats(basis):
    wide=[np.asarray(z,dtype=np.longdouble) for z in basis]
    if len(wide)!=3 or any(z.shape!=wide[0].shape or not np.isfinite(z).all() for z in wide):
        raise ValueError('invalid basis')
    g=np.zeros((3,3))
    for i in range(3):
        for j in range(i,3):g[i,j]=g[j,i]=float(np.sum(wide[i]*wide[j],dtype=np.longdouble))
    return g.tolist()


def support_check(start,x,q,u):
    block=start//128
    if block not in range(34,48) and not np.array_equal(x,q):raise ValueError('first direction support changed')
    if block not in range(20,34) and not np.array_equal(q,u):raise ValueError('second direction support changed')


def proposal_fields(start, arrays, a, b):
    if not 0<=a<=1 or not 0<=b<=1:raise ValueError('coefficients outside box')
    x,y,q,tq,u,tu=arrays;support_check(start,x,q,u);block=start//128
    if block in range(34,48): z=(1-a)*x+a*q
    elif block in range(20,34): z=(1-b)*x+b*u
    else:z=x
    # 算子输出仅为仿射预测；必须另做真实map，不将此数组当作T(z)。
    predicted=y+a*(tq-y)+b*(tu-tq)
    half=.5*x+.5*z if block in range(20,48) else x
    half_predicted=.5*y+.5*predicted
    for v in (z,predicted,half,half_predicted):physical(v)
    return z,predicted,half,half_predicted


def boundary_spectrum(a,mu,weight,width):
    left=mu<0;right=mu>0
    # 两侧出射通量：2pi * dnu * sum(w_mu |mu| I_nu)，不含内向射线。
    return 2*np.pi*width*(np.einsum('m,fm->f',weight[left]*abs(mu[left]),a[:,left,0])
        +np.einsum('m,fm->f',weight[right]*mu[right],a[:,right,-1]))


def main():
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<4:
        raise RuntimeError('four-core allocation required')
    OUT.mkdir(exist_ok=False);started=time.monotonic()
    pipeline.write_json(OUT/'status.json',dict(status='verifying_inputs'))
    try:
        ap=ROOT/'handoff/evidence/20260928-population-defect-global-review.json'
        audit=pipeline.read(ap);tp=ROOT/'handoff/evidence/20260928-population-defect-global-79878-terminal.json'
        terminal=pipeline.read(tp)
        if audit['job_id']!=79878 or audit['validated'] or audit['maps']!=2 or audit['feedback_pairs']!=0:
            raise RuntimeError('requires audited rejected 79878')
        failed={k for k,v in audit['checks'].items() if not v}
        if failed!={'original_full_boundary_bolometric','original_half_boundary_bolometric'}:
            raise RuntimeError('source verdict changed')
        if terminal['state']!='COMPLETED' or terminal['job_id']!=79878 or 'ExitCode=0:0' not in terminal['scontrol']:
            raise RuntimeError('source scheduler not complete')
        archive=audit['archive'];reused.verify([archive])
        with tarfile.open(ROOT/archive['path']) as t:
            inventory={c['path']:c for c in json.load(t.extractfile('ARCHIVE_MANIFEST.json'))['files']}
        names=['declaration.json','summary.json','population/validation.json','population/state.json','population/config.json','population/trial_material.npz']
        claims=[archive,pipeline.claim(ap),pipeline.claim(tp)]
        for name in names:
            c=pipeline.claim(SOURCE/name)
            if (c['sha256'],c['size_bytes'])!=(inventory[name]['sha256'],inventory[name]['size_bytes']):raise RuntimeError('unaudited source')
            claims.append(c)
        d=pipeline.read(SOURCE/'declaration.json');v=pipeline.read(SOURCE/'population/validation.json')
        state=pipeline.read(SOURCE/'population/state.json')
        if state['active_map'] is not None or state['history']!=[v['actual_map']]:raise RuntimeError('source state changed')
        r=state['history'][0]
        last=[v['candidate'],dict(path=r['output_path'],sha256=r['output_sha256'],size_bytes=pipeline.STATE_BYTES)]
        pairs=d['original_pair']+d['source_pair']+last;claims+=pairs
        code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/boundary_constrained_proposal.sbatch',
            'tests/test_boundary_constrained_proposal.py','handoff/protocols/boundary-constrained-proposal-v1.md')]
        reused.verify(claims+code)
        declaration=dict(job_id=os.environ['SLURM_JOB_ID'],source_job_id=79878,claims=claims,code=code,field_pairs=pairs,
            maximum_field_scans=2,maximum_coefficients=1,maximum_maps=0,maximum_feedback_pairs=0,
            maximum_wall_s=1800,maximum_parent_rss_bytes=8*1024**3,accepted_outer_steps=20,new_material_steps=0,
            original_r20_unchanged=True,physical_dt_unchanged=True,half_anchor='original 79151 x',
            numerical_change='new predictor constrained on original reference; old 79878 rejection retained',
            production_candidate_written=False,operator_recomputed=False)
        reused.immutable(OUT/'declaration.json',declaration)
        cfg=pipeline.read(SOURCE/'population/config.json')
        _,_,_,context=pipeline.configure_native(cfg,ROOT/pairs[0]['path'])
        mu=np.asarray(context['mu']);weight=np.asarray(context['weight']);width=np.diff(context['stencil'].active_lab_edge_hz)
        if len(width)!=9632 or len(mu)!=32 or len(weight)!=32:raise RuntimeError('grid changed')
        paths=[ROOT/c['path'] for c in pairs];stats=[];boundary=[]
        pipeline.write_json(OUT/'status.json',dict(status='first_scan'))
        for start,aa in chunks(paths,pipeline.SHAPE):
            support_check(start,aa[0],aa[2],aa[4]);basis=residual_basis(*aa)
            spectra=[boundary_spectrum(z,mu,weight,width[start:start+len(z)]) for z in aa]
            # 先逐频做差再积分，避免两大总量相减的消减误差。
            signed=[math.fsum(float(t) for t in spectra[j+1]-spectra[j]) for j in (0,2,4)]
            stats.append(dict(first_group=start,group_count=len(aa[0]),gram=gram_stats(basis)))
            boundary.append(dict(first_group=start,totals=[math.fsum(float(t) for t in f) for f in spectra],signed=signed))
        gram=[[math.fsum(s['gram'][i][j] for s in stats) for j in range(3)] for i in range(3)]
        delta=[math.fsum(s['signed'][i] for s in boundary) for i in range(3)]
        coeff=constrained_coefficients(gram,[delta[0],delta[1]-delta[0],delta[2]-delta[1]])
        reused.immutable(OUT/'gram.json',dict(rows=stats,boundary=boundary,gram=gram,signed=delta,coefficients=coeff))
        pipeline.write_json(OUT/'status.json',dict(status='second_scan'))
        rows=[]
        for start,aa in chunks(paths,pipeline.SHAPE):
            z,p,h,ph=proposal_fields(start,aa,coeff['a'],coeff['b']);x,y,q,tq,u,tu=aa
            defects=(y-x,p-z,ph-h,tq-q,tu-u)
            squares=[float(np.sum(t.astype(np.longdouble)**2,dtype=np.longdouble)) for t in defects]
            maxima=[float(np.max(abs(t))) for t in defects]
            spectra=[boundary_spectrum(t,mu,weight,width[start:start+len(t)]) for t in (z,p,h,ph)]
            rows.append(dict(first_group=start,group_count=len(z),squared_l2=squares,linf=maxima,
                minima=[float(t.min()) for t in (z,p,h,ph)],flux_totals=[math.fsum(float(v) for v in f) for f in spectra],
                spectrum_change_l1=[math.fsum(abs(float(v)) for v in spectra[i+1]-spectra[i]) for i in (0,2)],
                signed_flux=[math.fsum(float(v) for v in spectra[i+1]-spectra[i]) for i in (0,2)]))
        sums=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(5)]
        maxima=[max(r['linf'][i] for r in rows) for i in range(5)]
        flux=[math.fsum(r['flux_totals'][i] for r in rows) for i in range(4)]
        signed=[math.fsum(r['signed_flux'][i] for r in rows) for i in range(2)]
        l1=[math.fsum(r['spectrum_change_l1'][i] for r in rows)/max(flux[2*i:2*i+2]) for i in range(2)]
        bol=[abs(signed[i])/max(flux[2*i:2*i+2]) for i in range(2)]
        # 这只是候选筛查：真实full/half门必须由新算子映射判定。
        checks=dict(full_l2_benefit=math.sqrt(sums[1]/sums[0])<=.8,
            full_linf_nonincrease=maxima[1]<=maxima[0]*1.0000000001,
            half_l2_nonincrease=sums[2]<=sums[0]*(1.0000000001**2),
            half_linf_nonincrease=maxima[2]<=maxima[0]*1.0000000001)
        for i,name in enumerate(('full','half')):
            for k,values in [('boundary_l1',l1),('boundary_bolometric',bol)]:
                checks[name+'_'+k]=values[i]<1e-3 and values[i]<=d['original_row'][k]*1.0000000001
        reused.immutable(OUT/'prediction.json',dict(rows=rows,squared_l2=sums,linf=maxima,flux=flux,signed_flux=signed,
            l2_ratios=[math.sqrt(t/sums[0]) for t in sums],linf_ratios=[t/maxima[0] for t in maxima],
            boundary_l1=l1,boundary_bolometric=bol,checks=checks,all_predicted_checks_passed=all(checks.values()),
            genuine_transfer_map=False,half_anchor='original 79151 x'))
        reused.verify(claims+code)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=8*1024**3 or time.monotonic()-started>=1800:raise RuntimeError('diagnostic resource budget exceeded')
        reused.immutable(OUT/'summary.json',dict(status='complete_requires_review',coefficients=coeff,
            all_predicted_checks_passed=all(checks.values()),wall_s=time.monotonic()-started,peak_rss_bytes=peak,
            source_unchanged=True,source_job_id=79878,field_scans=2,new_maps=0,new_feedback_pairs=0,
            accepted_outer_steps=20,new_material_steps=0,production_candidate_written=False,operator_recomputed=False))
        pipeline.write_json(OUT/'status.json',dict(status='complete_requires_review'));reused.archive(OUT,'complete')
    except BaseException as exc:
        pipeline.write_json(OUT/'status.json',dict(status='failed',error=repr(exc)));reused.archive(OUT,'failed');raise


if __name__=='__main__':main()
