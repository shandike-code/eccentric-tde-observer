"""Four original fixed-x20 maps to measure one longer late-history direction."""
import argparse,math,os,resource,shutil,signal,sys,time
import numpy as np
from operations import x20_history_operator as core
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused
MAP_LIMIT=4


def require_fullspace_review(review,result):
    if (not review.get('independent_vertex_and_dual_audit') or not review.get('no_20pct_candidate_in_full_registered_cap')
        or review.get('physical_model_nonexistence') is not False or review.get('source_job')!=81453
        or result.get('status')!='no_20pct_candidate_in_full_registered_cap'
        or result.get('coefficient_l1_cap')!=17 or result.get('full_fraction')!=.9
        or result.get('accepted_outer_steps')!=20 or result.get('new_material_steps')!=0):raise ValueError('reviewed old-space exclusion required')


def advance_four(folder,cfg,state,driver,before_map):
    if state.get('active_map') is not None or state['history']:raise ValueError('new history must start empty')
    for n in range(MAP_LIMIT):
        reused.checkpoint();before_map(n)
        if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial original map retained')
        if state['status'] in driver.FAULT_STATUSES or len(state['history'])!=n+1 or state.get('active_map') is not None:raise RuntimeError('map budget/order or resource failure')
        row=state['history'][-1]
        if not all(math.isfinite(row[k]) and row[k]>=0 for k in ('residual','boundary_l1','boundary_bolometric','maximum_worker_rss_mib')):raise RuntimeError('nonfinite map statistics')
        receipts=list((folder/f'map{n+1:04d}').glob('block*.process-*.json'))
        if len(receipts)!=76:raise RuntimeError('map process receipt count')
        for p in receipts:
            z=pipeline.read(p)
            if z['returncode'] or not z['memory_guard_passed'] or z['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker memory/process guard')


def basis_moments(fields):
    if len(fields)!=8 or any(z.shape!=fields[0].shape for z in fields):raise ValueError('eight equal full-grid slabs required')
    for z in fields:core.physical(z)
    a,b,c,h,j,k,x,y=fields;raw=c-b
    # 新方向输入X-B跨late15到late19，预测输出Y-C使用真实T(X)=Y。
    defects=[raw,(b-a)-raw,(j-h)-raw,(k-j)-raw,(y-x)-raw]
    wide=[z.astype(np.longdouble) for z in defects];g=np.zeros((5,5))
    for i in range(5):
        for j in range(i,5):g[i,j]=g[j,i]=float(np.sum(wide[i]*wide[j],dtype=np.longdouble))
    return g


def collect(paths,shape,geometry,checkpoint=reused.checkpoint):
    slabs=[];spectra=[[] for _ in paths]
    for start,fields in core.chunks(paths,shape):
        checkpoint();g=basis_moments(fields)
        slabs.append(dict(first_group=start,group_count=len(fields[0]),gram=g.tolist(),minima=[float(z.min()) for z in fields]))
        for store,z in zip(spectra,fields):store.append(core.boundary_spectrum(z,geometry['mu'],geometry['weight'],geometry['width'][start:start+len(z)]))
    gram=np.array([[math.fsum(z['gram'][i][j] for z in slabs) for j in range(5)] for i in range(5)])
    return gram,np.stack([np.concatenate(z) for z in spectra]),slabs


def execute(out):
    pipeline.require_allocation(16)
    if int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=32 or os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('registered 32CPU allocation and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**extra):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**extra))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient field/retention disk budget')
        ev=ROOT/'handoff/evidence';ap=ev/'20260930-x20-fullspace-review.json';rp=ev/'20260930-x20-fullspace-result.json';dp=ev/'20260930-x20-fullspace-declaration.json'
        audit=pipeline.read(ap);require_fullspace_review(audit,pipeline.read(rp))
        if pipeline.sha256(rp)!=audit['result_sha256'] or pipeline.sha256(dp)!=audit['declaration_sha256']:raise RuntimeError('fullspace result identity changed')
        pre=out/'source-preflight';pre.mkdir();source,geometry=core.prepare(pre,'scan')
        previous=ROOT/'outputs/hpc/x20-capped-subspace-20260929'
        claims=core.v.audited_inputs(previous,ev/'20260929-x20-capped-review.json',ev/'20260929-x20-capped-80925-terminal.json',80925,['declaration.json','summary.json','prediction.json'])
        basis=pipeline.read(previous/'declaration.json')['basis'];seed=basis[2]
        if [basis[i] for i in (1,2,4,5)]!=source['field_pairs']:raise RuntimeError('fixed basis changed')
        claims+=source['claims']+source['code']+basis+[pipeline.claim(p) for p in (ap,rp,dp)]
        claims=list({(c['path'],c['sha256']):c for c in claims}.values())
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_long_chord.sbatch','tests/test_x20_long_chord.py','handoff/protocols/x20-long-chord-v1.md')]
        reused.verify(claims+code)
        plan=dict(cases=source['cases'],claims=claims,code=code,original_basis=basis,seed=seed,
            source_jobs=[80554,80925,81453],maximum_maps=4,maximum_feedback_pairs=0,maximum_field_scans=1,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,candidate_written=False,
            original_acceptance_gates_changed=False,coefficient_l1_cap=17,new_direction='late19 minus late15; true map pair late19 to late20',environment=pipeline.environment())
        reused.immutable(out/'declaration.json',plan);reused.LIMITS=dict(chord=4)
        with core.prior.fixed.relay_dispatch():
            folder,cfg,state=reused.child(out,'chord','control',seed,plan)
            core.prior.fixed.same_trial(core.v.load_arrays(folder/'trial_material.npz'),core.v.load_arrays(ROOT/source['cases']['control']['trial']['path']))
            advance_four(folder,cfg,state,core.prior.old.recovery.original.driver,lambda n:mark('mapping',completed_maps=n,target_maps=4))
        if state['history'][0]['input_sha256']!=seed['sha256'] or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(state['history'],state['history'][1:])):raise RuntimeError('new map lineage changed')
        reused.checkpoint();mark('retaining_endpoints',completed_maps=4);core.prior.fixed.retain_pair(folder,state)
        retained=pipeline.read(folder/'endpoints-map04/manifest.json');pair=[retained['endpoints'][k] for k in ('final','mapped_final')]
        row=state['history'][-1]
        if [c['sha256'] for c in pair]!=[row['input_sha256'],row['output_sha256']]:raise RuntimeError('new pair changed')
        reused.immutable(out/'expanded-basis.json',dict(original_basis=basis,new_pair=pair,source_map=row,new_history=state['history']))
        mark('collecting_expanded_basis',completed_maps=4)
        gram,spectra,slabs=collect([ROOT/c['path'] for c in basis+pair],pipeline.SHAPE,geometry)
        oldgram=np.asarray(pipeline.read(previous/'prediction.json')['gram'])
        if not np.allclose(gram[:4,:4],oldgram,rtol=2e-12,atol=0):raise RuntimeError('unchanged Gram prefix mismatch')
        np.savez(out/'expanded-system.npz',gram=gram,spectra=spectra)
        reused.immutable(out/'collection.json',dict(slabs=slabs,gram=gram.tolist(),prefix_consistent=True,all_frequency_groups=9632,unweighted_field_defect_not_physical_energy=True))
        reused.verify(claims+code+pair)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        reused.immutable(out/'summary.json',dict(status='expanded_basis_collected_requires_review',new_maps=4,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False,candidate_written=False,parent_peak_rss_bytes=peak,wall_s=time.monotonic()-started,coefficient_dimension=4,predicted_benefit_not_yet_evaluated=True))
        mark('expanded_basis_collected_requires_review',completed_maps=4);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,args.run))
