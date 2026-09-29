"""Joint cap/equality solve, followed by full-field gates and at most two maps.

The rejected 80862 run remains immutable. This changes the constrained optimizer,
not its coefficient cap, physics, trial, acceptance gates or source state basis.
"""
import argparse,os,resource,signal,sys,time,shutil
import numpy as np
from operations import x20_history_operator as core
from operations import seven_block_global_fields as actual
from operations.x20_boundary_subspace import basis_fields,weights,positive_upper,bounded_coefficients,measure_candidates,write_candidates
from operations.x20_capped_solver import solve
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused
RCOND=1e-12
CAP=17.


def propose(paths,shape,geometry,source_prediction,checkpoint=lambda:None):
    # Gram/边界系数只复用已审计且SHA固定的80862；新系数须重新扫描每个场单元。
    c,solution=solve(source_prediction['gram'],source_prediction['boundary_coefficients'],CAP)
    limits=[]
    for start,aa in core.chunks(paths,shape):
        checkpoint();q,p=basis_fields(aa,c)
        limits.append(dict(first_group=start,group_count=len(q),upper=min(positive_upper(aa[1],q),positive_upper(aa[2],p)),
            negative_candidate=int(np.count_nonzero(q<0)),negative_prediction=int(np.count_nonzero(p<0))))
    selected,bounds=bounded_coefficients(c,min(r['upper'] for r in limits))
    measured=measure_candidates(paths,shape,selected,geometry,checkpoint)
    passed=measured['passed'] and bounds['selected_fraction']>0 and bounds['coefficient_l1']<=CAP
    return dict(solve=solution,positivity_slabs=limits,bounds=bounds,selected_coefficients=selected.tolist(),
        weights=weights(selected).tolist(),prediction=measured,all_predicted_checks_passed=passed,
        gram=source_prediction['gram'],boundary_coefficients=source_prediction['boundary_coefficients'],
        reused_gram_from_job=80862,candidate_written=False,strict_error_bound=False)


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        ev=ROOT/'handoff/evidence'
        previous=ROOT/'outputs/hpc/x20-boundary-subspace-20260929'
        ap=ev/'20260929-x20-subspace-review.json';tp=ev/'20260929-x20-subspace-80862-terminal.json'
        review=pipeline.read(ap)
        if (review['job_id']!=80862 or not review['independent_small_statistic_reduction'] or review['new_maps']!=0
            or review['new_material_steps']!=0 or review['baseline_replaced'] or review['checks']['full_l2_benefit']):
            raise RuntimeError('audited rejected subspace required')
        claims=core.v.audited_inputs(previous,ap,tp,80862,['declaration.json','summary.json','prediction.json'])
        source_prediction=pipeline.read(previous/'prediction.json')
        for mode,job,run in [('scan',80826,'x20-history-scan-v2-20260929'),('midpoint',80823,'x20-history-midpoint-20260929')]:
            ap=ev/f'20260929-x20-{mode}-review.json';tp=ev/f'20260929-x20-{mode}-{job}-terminal.json';audit=pipeline.read(ap)
            if not audit['independent_small_statistic_reduction'] or audit['new_material_steps']!=0 or audit['baseline_replaced']:raise RuntimeError('independent source review missing')
            if mode=='scan' and audit['feasible']:raise RuntimeError('expected rejected single direction')
            if mode=='midpoint' and not audit['affinity_pass']:raise RuntimeError('midpoint affinity not validated')
            claims+=core.v.audited_inputs(ROOT/'outputs/hpc'/run,ap,tp,job,['declaration.json','summary.json','prediction.json' if mode=='scan' else 'validation.json'])
        pre=out/'source-preflight';pre.mkdir();plan,geometry=core.prepare(pre,'scan')
        basis=[]
        for child,n in [('late',16),('historical',24)]:
            retained=pipeline.read(ROOT/core.SOURCE/child/f'endpoints-map{n:02d}/manifest.json')
            basis += [retained['endpoints'][k] for k in ('previous','final','mapped_final')]
        if basis!=pipeline.read(previous/'declaration.json')['basis'] or [basis[i] for i in (1,2,4,5)]!=plan['field_pairs']:raise RuntimeError('four-map basis identity changed')
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/f) for f in ('operations/x20_capped_subspace.sbatch','tests/test_x20_capped_solver.py','tests/test_x20_capped_proposal.py','handoff/protocols/x20-capped-subspace-v1.md')]
        claims+=plan['claims']+plan['code']+basis;claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
        declaration=dict(cases=plan['cases'],claims=claims,code=code,basis=basis,source_row=plan['source_rows'][0],source_jobs=[80554,80826,80823,80862],
            maximum_maps=2,maximum_feedback_pairs=0,maximum_field_scans=4,maximum_proposals=1,coefficient_l1_cap=CAP,rcond=RCOND,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,automatic_promotion=False,strict_error_bound=False,
            fixed_material_x20=True,historical_failures_retained=True,environment=pipeline.environment())
        reused.immutable(out/'declaration.json',declaration);paths=[ROOT/c['path'] for c in basis]
        mark('two_pass_capped_prediction');prediction=propose(paths,pipeline.SHAPE,geometry,source_prediction,reused.checkpoint)
        reused.immutable(out/'prediction.json',prediction);maps=0;validated=False;status='prediction_rejected'
        if prediction['all_predicted_checks_passed']:
            if shutil.disk_usage(out).free<10*pipeline.STATE_BYTES:raise RuntimeError('insufficient disk')
            full,half=out/'full.dat',out/'half.dat';mark('writing_candidates')
            write_candidates(paths,pipeline.SHAPE,prediction['selected_coefficients'],full,half,reused.checkpoint)
            seeds={n:pipeline.claim(p) for n,p in [('full',full),('half',half)]};reused.immutable(out/'candidate-claims.json',seeds)
            reused.LIMITS=dict(full=1,half=1);measured={}
            with core.prior.fixed.relay_dispatch():
                for name in ('full','half'):
                    mark('mapping',case=name);folder,cfg,state=reused.child(out,name,'control',seeds[name],declaration)
                    core.prior.fixed.same_trial(core.v.load_arrays(folder/'trial_material.npz'),core.v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
                    driver=core.prior.old.recovery.original.driver
                    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
                    if len(state['history'])!=1 or state['active_map'] is not None or state['status'] in driver.FAULT_STATUSES:raise RuntimeError('map state fault')
                    rr=list((folder/'map0001').glob('block*.process-*.json'))
                    if len(rr)!=76:raise RuntimeError('process receipt count')
                    for f in rr:
                        q=pipeline.read(f)
                        if q['returncode'] or not q['memory_guard_passed'] or q['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')
                    measured[name]=state['history'][0];maps+=1
                    if measured[name]['input_sha256']!=seeds[name]['sha256']:raise RuntimeError('candidate identity')
            mark('validating_true_maps')
            report=actual.validate([paths[1],paths[2],full,ROOT/measured['full']['output_path'],half,ROOT/measured['half']['output_path']],pipeline.SHAPE,blocks=tuple(range(76)),checkpoint=reused.checkpoint)
            checks=actual.checks(report,plan['source_rows'][0],measured['full'],measured['half'])
            checks['independent_half_linf_affinity']=report['fixed_scale_linf_ratios'][3]<=1e-6
            validated=all(checks.values());status='true_maps_validated_requires_review' if validated else 'true_map_validation_rejected'
            reused.immutable(out/'validation.json',dict(field_comparison=report,actual_maps=measured,checks=checks,validated=validated,baseline_replaced=False,material_step_promoted=False))
            reused.verify(list(seeds.values())+[dict(path=r['output_path'],sha256=r['output_sha256'],size_bytes=pipeline.STATE_BYTES) for r in measured.values()])
        reused.verify(claims+code);peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        reused.immutable(out/'summary.json',dict(status=status,new_maps=maps,new_feedback_pairs=0,accepted_outer_steps=20,new_material_steps=0,
            baseline_replaced=False,strict_error_bound=False,all_predicted_checks_passed=prediction['all_predicted_checks_passed'],
            validated=validated,parent_peak_rss_bytes=peak,wall_s=time.monotonic()-started,historical_failures_retained=True))
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
