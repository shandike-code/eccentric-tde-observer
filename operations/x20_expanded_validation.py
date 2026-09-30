"""One reviewed four-direction candidate: full-field gates then at most two maps."""
import argparse,math,os,resource,signal,sys,time,shutil
import numpy as np
from operations import x20_history_operator as core
from operations import seven_block_global_fields as actual
from operations.x20_expanded_fields import measure_candidates,write_candidates
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused


def require_candidate(candidate,audit,digest):
    if (not audit.get('independent_70digit_spectral_witness') or audit.get('source_job')!=81647
        or audit.get('result_sha256')!=digest or candidate.get('status')!='small_candidate_requires_full_field_scan'
        or not candidate.get('available_gates_passed') or not all(candidate['checks'].values())
        or candidate.get('full_fraction')!=.9 or candidate.get('half_fraction')!=.45
        or candidate.get('original_science_gates_changed') is not False
        or candidate.get('candidate_written') is not False or candidate.get('accepted_outer_steps')!=20
        or any(candidate.get(k)!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))):raise ValueError('reviewed fixed candidate required')
    raw=np.asarray(candidate['raw_coefficients']);selected=np.asarray(candidate['selected_coefficients'])
    if raw.shape!=(4,) or not np.isfinite(raw).all() or not np.array_equal(selected,.9*raw):raise ValueError('candidate dimension or fraction')
    weights=np.r_[raw[0],1-math.fsum(raw),raw[1:]]
    if math.fsum(abs(weights))>17 or candidate['raw_coefficients']!=audit['raw_coefficients'] or candidate['selected_coefficients']!=audit['selected_coefficients']:raise ValueError('candidate cap or identity')


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0' or os.environ.get('SLURM_CPUS_PER_TASK')!='32':raise RuntimeError('32CPU allocation and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        ev=ROOT/'handoff/evidence';previous=ROOT/'outputs/hpc/x20-long-chord-20260930'
        ap=ev/'20260930-x20-long-chord-review.json';tp=ev/'20260930-x20-long-chord-81647-terminal.json'
        review=pipeline.read(ap)
        if not review.get('scientific_independent_audit_completed') or review['new_maps']!=4 or review['accepted_outer_steps']!=20:raise RuntimeError('audited long chord required')
        claims=core.v.audited_inputs(previous,ap,tp,81647,['declaration.json','summary.json','expanded-basis.json','expanded-system.npz','collection.json'])
        cp=ev/'20260930-x20-expanded-candidate-result.json';ca=ev/'20260930-x20-expanded-candidate-review.json'
        candidate=pipeline.read(cp);audit=pipeline.read(ca)
        require_candidate(candidate,audit,pipeline.sha256(cp))
        expanded=pipeline.read(previous/'expanded-basis.json')
        if expanded!=audit['source_basis']:raise RuntimeError('candidate source basis mismatch')
        basis=expanded['original_basis']+expanded['new_pair']
        pre=out/'source-preflight';pre.mkdir();plan,geometry=core.prepare(pre,'scan')
        if [basis[i] for i in (1,2,4,5)]!=plan['field_pairs']:raise RuntimeError('source operator changed')
        core.prior.fixed.same_trial(core.v.load_arrays(previous/'chord/trial_material.npz'),core.v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
        state=pipeline.read(previous/'chord/state.json');retained=pipeline.read(previous/'chord/endpoints-map04/manifest.json')
        if core.retained_pair(state,retained,4)!=expanded['new_pair']:raise RuntimeError('long chord not settled')
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_expanded_validation.sbatch','tests/test_x20_expanded_fields.py','handoff/protocols/x20-expanded-validation-v1.md')]
        claims+=plan['claims']+plan['code']+basis+[pipeline.claim(p) for p in (cp,ca,previous/'chord/state.json',previous/'chord/endpoints-map04/manifest.json',previous/'chord/trial_material.npz')]
        claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
        declaration=dict(cases=plan['cases'],claims=claims,code=code,basis=basis,source_row=plan['source_rows'][0],source_jobs=[80554,81647],
            maximum_maps=2,maximum_feedback_pairs=0,maximum_field_scans=3,maximum_proposals=1,coefficient_l1_cap=17,coefficient_dimension=4,selected_coefficients=candidate['selected_coefficients'],raw_coefficients=candidate['raw_coefficients'],full_fraction=.9,half_fraction=.45,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,automatic_promotion=False,strict_error_bound=False,
            fixed_material_x20=True,historical_failures_retained=True,environment=pipeline.environment())
        reused.immutable(out/'declaration.json',declaration);paths=[ROOT/c['path'] for c in basis]
        mark('full_field_prediction');measured=measure_candidates(paths,pipeline.SHAPE,candidate['selected_coefficients'],geometry,reused.checkpoint)
        prediction=dict(prediction=measured,selected_coefficients=candidate['selected_coefficients'],all_predicted_checks_passed=measured['passed'],candidate_written=False)
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
