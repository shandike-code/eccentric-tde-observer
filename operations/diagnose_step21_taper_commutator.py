"""One read-only pass: resolve tapered defect into weighted defect and noncommutation."""
import argparse,math,os,resource,signal,sys,time
import numpy as np
from operations import scan_step21_joint_line_cost as inherited
from operations import tapered_joint_fields as fields
from operations.constrained_hybrid_fields import chunks
ROOT,pipeline,fresh,reused,v=inherited.ROOT,inherited.pipeline,inherited.fresh,inherited.reused,inherited.v


def decompose(paths,shape,*,centers=fields.CENTERS,checkpoint=lambda:None):
    if len(paths)!=6:raise ValueError('six original/uniform/tapered input-output fields required')
    ranges=fields.intervals(centers,shape[0]);rows=[]
    for start,(x,y,q,vv,z,tz) in chunks(paths,shape):
        checkpoint();hit=[a for a,b in ranges.values() if a<=start<b]
        if hit:
            a=hit[0];w=fields.taper_weights()[start-a:start-a+len(x),None,None]
            if w.shape[0]!=len(x):raise ValueError('crossed core boundary')
            if not np.array_equal(z,(1-w)*x+w*q):raise ValueError('taper candidate identity')
        else:
            if not (np.array_equal(q,x) and np.array_equal(z,x)):raise ValueError('unselected input identity')
            w=None
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            raw=y-x;uniform=vv-q;actual=tz-z
            predicted=raw if w is None else (1-w)*raw+w*uniform
            comm=actual-predicted
            vals=[raw,uniform,actual,predicted,comm]
            ss=[float(np.sum(a*a)) for a in vals];mx=[float(np.max(abs(a))) for a in vals]
            cross=float(np.sum(predicted*comm));closure=float(np.max(abs(actual-(predicted+comm))))
        if not np.isfinite(ss+mx+[cross,closure]).all():raise ValueError('nonfinite reduction')
        ind=np.unravel_index(np.argmax(abs(actual)),actual.shape)
        witness={'index':[int(start+ind[0]),int(ind[1]),int(ind[2])],
                 'actual':float(actual[ind]),'weighted_defect':float(predicted[ind]),'commutator':float(comm[ind])}
        rows.append(dict(first_group=start,group_count=len(x),selected=bool(hit),squared_l2=ss,linf=mx,cross=cross,closure_linf=closure,witness=witness))
    if not rows or math.fsum(r['squared_l2'][0] for r in rows)<=0:raise ValueError('zero reference')
    domains={}
    for name,part in [('all',rows),('selected',[r for r in rows if r['selected']]),('outside',[r for r in rows if not r['selected']])]:
        sums=[math.fsum(r['squared_l2'][i] for r in part) for i in range(5)]
        domains[name]={'squared_l2':sums,'linf':[max((r['linf'][i] for r in part),default=0.) for i in range(5)],
                       'cross':math.fsum(r['cross'] for r in part)}
    return dict(columns=['original','uniform','actual_tapered','weighted_defect','commutator'],domains=domains,slabs=rows,
        passes=1,actual_map_performed=False,candidate_written=False,accepted_material_step=False)


def prepare(out):
    ev=ROOT/'handoff/evidence';claims=[];vals=[];priors=[]
    for folder,audit,terminal,job in [
        ('step21-joint-block-global-20260926','20260926-joint-global-review','20260926-joint-global-77843-terminal',77843),
        ('step21-tapered-joint-20260926','20260926-tapered-joint-review','20260926-tapered-joint-77927-terminal',77927)]:
        src=ROOT/'outputs/hpc'/folder
        claims+=v.audited_inputs(src,ev/(audit+'.json'),ev/(terminal+'.json'),job,['declaration.json','summary.json','control/validation.json','control/state.json'])
        val=pipeline.read(src/'control/validation.json');prior=pipeline.read(src/'declaration.json');vals.append(val);priors.append(prior)
        if val['validated'] or not val['checks']['independent_half_affinity']:raise RuntimeError('expected audited rejection with valid half sample')
        state=pipeline.read(src/'control/state.json')
        if state['active_map'] is not None or state['history']!=[val['actual_map']]:raise RuntimeError('source not settled')
        claims+=prior['claims']+prior['code']
    if vals[0]['source_pair']!=vals[1]['source_pair'] or priors[0]['replacements']!=priors[1]['replacements'] or priors[1]['taper']!=fields.TAPER:
        raise RuntimeError('different origin or direction')
    paths=list(vals[0]['source_pair'])
    for val in vals:
        row=val['actual_map'];paths += [val['candidate'],dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)]
    claims+=paths;claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ['operations/diagnose_step21_taper_commutator.sbatch','tests/test_diagnose_step21_taper_commutator.py','handoff/protocols/step21-taper-commutator-v1.md']]
    reused.verify(claims+code)
    plan=dict(paths=paths,claims=claims,code=code,taper=fields.TAPER,accepted_outer_steps=20,maximum_maps=0,maximum_feedback_pairs=0,maximum_candidate_writes=0,maximum_passes=1,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan);return plan


def execute(out):
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        plan=prepare(out);mark('scanning');result=decompose([ROOT/c['path'] for c in plan['paths']],pipeline.SHAPE,checkpoint=reused.checkpoint)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('memory guard')
        result['peak_rss_bytes']=peak;reused.verify(plan['claims']+plan['code']);reused.immutable(out/'decomposition.json',result)
        mark('complete_requires_review');reused.archive(out,'complete')
    except BaseException as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
