"""At most two true maps of the independently reviewed 82486 candidate."""
import argparse,hashlib,os,resource,shutil,signal,sys,tarfile,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import seven_block_global_fields as actual
from operations.x20_boundary_candidate_prediction import require_candidate
from operations.x20_boundary_validation_fields import write_candidates,prediction_error
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused


def validate_prediction(audit,decl):
    if audit.get('job_id')!=82486 or not audit.get('independent_complete_field_reduction') or not audit.get('passed') or not all(audit['checks'].values()):
        raise ValueError('complete independent prediction audit required')
    if decl['fields']!=audit['fields'] or decl['selected_coefficients']!=audit['selected_coefficients']:
        raise ValueError('prediction identity mismatch')
    if any(audit[k]!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) or audit['baseline_replaced']:raise ValueError('prediction scope')


def source_plan(out):
    ev=ROOT/'handoff/evidence';ap=ev/'20261001-x20-boundary-prediction-82486-review.json';a=pipeline.read(ap)
    prev=ROOT/'outputs/hpc/x20-boundary-candidate-prediction-20261001';decl=pipeline.read(prev/'declaration.json')
    validate_prediction(a,decl);receipt=a['receipt'];arc=ROOT/receipt['path']
    if pipeline.sha256(arc)!=receipt['sha256'] or arc.stat().st_size!=receipt['size_bytes']:raise ValueError('82486 archive')
    ix={c['path']:c for c in receipt['files']}
    claims=[pipeline.claim(ap),pipeline.claim(arc)]
    for name in ('declaration.json','prediction.json','summary.json','status.json'):
        c=pipeline.claim(prev/name)
        if c['sha256']!=ix[name]['sha256'] or c['size_bytes']!=ix[name]['size_bytes']:raise ValueError('live prediction differs')
        claims.append(c)
    cp=ev/'20261001-x20-boundary-constrained-selection.json';ca=ev/'20261001-x20-boundary-candidate-feasibility.json'
    candidate=pipeline.read(cp);require_candidate(candidate,pipeline.read(ca),pipeline.sha256(cp))
    if candidate['selected_coefficients']!=a['selected_coefficients']:raise ValueError('audited coefficient')
    claims += decl['source_claims']+[pipeline.claim(cp),pipeline.claim(ca)]
    reused.verify(decl['code']+decl['source_code'])
    src=ROOT/'outputs/hpc/x20-window-feedback-20260930';oldap=ev/'20260930-x20-82273-final-review.json'
    original=pipeline.read(oldap)['archive'];oldarc=ROOT/original['path']
    if pipeline.sha256(oldarc)!=original['sha256']:raise ValueError('82273 archive')
    names=[]
    names += [f'{case}/{n}' for case in ('accelerated','historical') for n in ('config.json','state.json','trial_material.npz','endpoints-map16/manifest.json','pair16/feedback_protocol.json')]
    with tarfile.open(oldarc) as tar:
        for name in names:
            if hashlib.sha256(tar.extractfile(name).read()).hexdigest()!=pipeline.sha256(src/name):raise ValueError('82273 source changed '+name)
            claims.append(pipeline.claim(src/name))
    cfgs=[];trials=[];rows=[]
    for case in ('accelerated','historical'):
        folder=src/case;cfg=pipeline.read(folder/'config.json');state=pipeline.read(folder/'state.json')
        if state['config_sha256']!=pipeline.sha256(folder/'config.json'):raise ValueError('config identity')
        pair=core.retained_pair(state,pipeline.read(folder/'endpoints-map16/manifest.json'),16)
        expected=a['fields'][:2] if case=='accelerated' else a['fields'][2:4]
        if pair!=expected:raise ValueError('A16/H16 anchor identity')
        trial=core.v.load_arrays(folder/'trial_material.npz');protocol=pipeline.read(folder/'pair16/feedback_protocol.json')
        sources=protocol['sources'];needed=[sources[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]
        reused.verify(needed);claims+=needed
        base=core.v.load_arrays(ROOT/needed[0]['path']);r20=np.load(ROOT/needed[1]['path'],allow_pickle=False);old=core.v.load_arrays(ROOT/needed[2]['path'])
        core.prior.fixed.exact_trial(trial,base,r20,old,'control')
        native=core.prior.reused.audit_native_trial(cfg,trial)
        if not native['native_mirrored_material_exact'] or not native['physical_phase_and_dt_exact']:raise ValueError('native identity')
        if int(trial['phase_index'])!=1367 or float(trial['step_duration_s'])!=889.419892762322:raise ValueError('phase/dt')
        cfgs.append(cfg);trials.append(trial);rows.append(state['history'][-1])
    core.same_operator_config(*cfgs);core.prior.fixed.same_trial(*trials)
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(src/'accelerated/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfgs[0]);core.prior.fixed.same_trial(trials[0],core.v.load_arrays(inputs/'trial_material.npz'))
    gp=ROOT/decl['geometry']['path'];reused.verify([decl['geometry']]);claims.append(decl['geometry'])
    with np.load(gp,allow_pickle=False) as z:geometry={k:z[k] for k in ('mu','weight','width')}
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    claims += [pipeline.claim(oldap),pipeline.claim(oldarc),*cases['control'].values(),*a['fields']]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    return dict(cases=cases,claims=claims,basis=a['fields'],source_row=rows[0],candidate=candidate,geometry=geometry)


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('SLURM_CPUS_PER_TASK')!='32' or os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('32CPU and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,unix=time.time(),**kw))
    mark('preparing')
    try:
        plan=source_plan(out);c=plan['candidate'];paths=[ROOT/x['path'] for x in plan['basis']]
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_boundary_validation.sbatch','tests/test_x20_boundary_validation.py','handoff/protocols/x20-boundary-validation-v1.md')]
        reused.verify(plan['claims']+code);reused.checkpoint()
        declaration=dict(cases=plan['cases'],claims=plan['claims'],code=code,basis=plan['basis'],source_row=plan['source_row'],
            source_jobs=[82273,82441,82486],selected_coefficients=c['selected_coefficients'],coefficient_mode='per_natural_block_with_boundary_scalars',optimization_converged=False,
            maximum_maps=2,maximum_feedback_pairs=0,maximum_candidates=1,full_fraction=1.,half_fraction=.5,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            environment=pipeline.environment())
        reused.immutable(out/'declaration.json',declaration)
        if shutil.disk_usage(out).free<10*pipeline.STATE_BYTES:raise RuntimeError('insufficient disk')
        full,half=out/'full.dat',out/'half.dat';mark('writing_candidates')
        write_candidates(paths,pipeline.SHAPE,c['selected_coefficients'],full,half,reused.checkpoint)
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
                if len(rr)!=76:raise RuntimeError('worker receipt count')
                for f in rr:
                    r=pipeline.read(f)
                    if r['returncode'] or not r['memory_guard_passed'] or r['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')
                measured[name]=state['history'][0]
                if measured[name]['input_sha256']!=seeds[name]['sha256']:raise RuntimeError('candidate input mismatch')
        mark('validating_true_maps')
        report=actual.validate([paths[0],paths[1],full,ROOT/measured['full']['output_path'],half,ROOT/measured['half']['output_path']],pipeline.SHAPE,blocks=tuple(range(76)),checkpoint=reused.checkpoint)
        checks=actual.checks(report,plan['source_row'],measured['full'],measured['half'])
        checks['independent_half_linf_affinity']=report['fixed_scale_linf_ratios'][3]<=1e-6
        affinity=prediction_error(paths+[ROOT/measured[n]['output_path'] for n in ('full','half')],pipeline.SHAPE,c['selected_coefficients'],reused.checkpoint)
        checks.update(affinity['checks'])
        validated=all(checks.values());status='true_maps_validated_requires_review' if validated else 'true_map_validation_rejected'
        reused.immutable(out/'validation.json',dict(field_comparison=report,prediction_affinity=affinity,actual_maps=measured,checks=checks,validated=validated,baseline_replaced=False,material_step_promoted=False))
        reused.verify(plan['claims']+code+list(seeds.values())+[dict(path=r['output_path'],sha256=r['output_sha256'],size_bytes=pipeline.STATE_BYTES) for r in measured.values()])
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent guard')
        reused.immutable(out/'summary.json',dict(status=status,new_maps=2,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,validated=validated,
            baseline_replaced=False,strict_error_bound=False,parent_peak_rss_bytes=peak,wall_s=time.monotonic()-start))
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();execute(pipeline.safe_path(ROOT,a.run))
