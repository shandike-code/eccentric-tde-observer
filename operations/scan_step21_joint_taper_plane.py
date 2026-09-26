"""Bounded convex screening of two existing globally mapped radiation directions."""
import argparse,os,resource,signal,sys,time,math
import numpy as np
from operations import diagnose_step21_taper_commutator as inherited
from operations import joint_taper_plane as plane
ROOT,pipeline,fresh,reused,v,fields=inherited.ROOT,inherited.pipeline,inherited.fresh,inherited.reused,inherited.v,inherited.fields


def prepare(out):
    ev=ROOT/'handoff/evidence';vals=[];priors=[]
    claims=v.audited_inputs(ROOT/'outputs/hpc/step21-taper-commutator-20260927',ev/'20260927-taper-commutator-review.json',ev/'20260927-taper-commutator-77954-terminal.json',77954,['declaration.json','decomposition.json','status.json'])
    for folder,audit,terminal,job in [
        ('step21-joint-block-global-20260926','20260926-joint-global-review','20260926-joint-global-77843-terminal',77843),
        ('step21-tapered-joint-20260926','20260926-tapered-joint-review','20260926-tapered-joint-77927-terminal',77927)]:
        src=ROOT/'outputs/hpc'/folder
        claims+=v.audited_inputs(src,ev/(audit+'.json'),ev/(terminal+'.json'),job,['declaration.json','summary.json','control/validation.json','control/state.json','control/config.json','control/trial_material.npz'])
        val=pipeline.read(src/'control/validation.json');prior=pipeline.read(src/'declaration.json');vals.append(val);priors.append(prior)
        if val['validated'] or not val['checks']['independent_half_affinity']:raise RuntimeError('expected audited rejection with valid half sample')
        state=pipeline.read(src/'control/state.json')
        if pipeline.sha256(src/'control/config.json')!=state['config_sha256']:raise RuntimeError('source config changed')
        if state['active_map'] is not None or state['history']!=[val['actual_map']]:raise RuntimeError('source not settled')
        claims+=prior['claims']+prior['code']
    if vals[0]['source_pair']!=vals[1]['source_pair'] or priors[0]['replacements']!=priors[1]['replacements'] or priors[1]['taper']!=fields.TAPER:
        raise RuntimeError('different origin or direction')
    paths=list(vals[0]['source_pair'])
    for val in vals:
        row=val['actual_map'];paths += [val['candidate'],dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)]
    claims+=paths;claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ['operations/scan_step21_joint_taper_plane.sbatch','tests/test_joint_taper_plane.py','handoff/protocols/step21-joint-taper-plane-v1.md']]
    reused.verify(claims+code)
    plan=dict(paths=paths,claims=claims,code=code,taper=fields.TAPER,accepted_outer_steps=20,maximum_maps=0,maximum_feedback_pairs=0,maximum_candidate_writes=0,maximum_passes=6,controls=plane.CONTROL,source_row=priors[0]['source_row'],environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    cfg=pipeline.read(ROOT/'outputs/hpc/step21-tapered-joint-20260926/control/config.json')
    native,_,_,context=pipeline.configure_native(cfg,ROOT/paths[0]['path']);widths=np.diff(context['stencil'].active_lab_edge_hz)
    flux=lambda a,start:native.base._block_flux(a,context['mu'],context['weight'],widths[start:start+len(a)])
    return plan,flux,priors[0]['source_row']


def execute(out):
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        plan,flux,original=prepare(out);paths=[ROOT/c['path'] for c in plan['paths']];mark('gram')
        gram=plane.gram_scan(paths,pipeline.SHAPE,flux,reused.checkpoint)
        audit=pipeline.read(ROOT/'handoff/evidence/20260927-taper-commutator-review.json')
        if not math.isclose(gram['s0'],audit['domains']['all']['squared_l2'][0],rel_tol=1e-12) or gram['maximum']!=audit['domains']['all']['linf'][0]:raise RuntimeError('original scale changed')
        reused.immutable(out/'gram.json',gram)
        def evaluate(uv):
            mark('scanning',uv=uv)
            return plane.inspect(paths,pipeline.SHAPE,uv,gram,original,checkpoint=reused.checkpoint)
        result=plane.search(gram,evaluate,lambda data:pipeline.write_json(out/'progress.json',data))
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('memory guard')
        result['peak_rss_bytes']=peak;reused.verify(plan['claims']+plan['code']);reused.immutable(out/'prediction.json',result)
        mark('complete_requires_review');reused.archive(out,'complete')
    except BaseException as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
