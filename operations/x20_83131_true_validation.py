"""Two true maps of the independently audited historical half-step candidate."""
import argparse,hashlib,os,resource,shutil,signal,sys,tarfile,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import seven_block_global_fields as actual
from operations.x20_boundary_validation_fields import write_candidates,prediction_error
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused


def validate_prediction(audit,decl):
    expected={'full_field_nonnegative','full_l2_benefit','full_linf_nonincrease','half_l2_nonincrease','half_linf_nonincrease',
              'full_radiation','full_boundary_l1','full_boundary_bolometric','half_radiation','half_boundary_l1','half_boundary_bolometric'}
    z=audit.get('result',{})
    if (audit.get('job_id')!=83131 or audit.get('independent_slab_reduction') is not True
        or audit.get('source_and_code_verified') is not True or z.get('passed') is not True
        or set(z.get('checks',{}))!=expected or not all(v is True for v in z['checks'].values())):
        raise ValueError('complete independent 83131 prediction audit required')
    c=audit.get('coefficients')
    if c!=[-2.5857236634643006,-1.0142763365356995,.45] or decl.get('global_coefficients')!=c or decl.get('step_multiplier')!=.5:
        raise ValueError('halved global coefficient identity')
    if decl.get('source_job')!=83111 or decl.get('sign_audit_job')!=83075 or decl.get('shape')!=[9632,32,4096] or len(decl.get('fields',[]))!=8:
        raise ValueError('wrong historical source')
    if any(audit[k]!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) or audit['baseline_replaced']:
        raise ValueError('prediction scope')


def previous_pair_row(manifest,fields):
    # 本次锚点是previous -> final，即第15次映射，不能误用第16次final -> mapped_final。
    rows=manifest['history_rows'];ep=manifest['endpoints']
    if len(rows)!=2 or [r['iteration'] for r in rows]!=[15,16]:raise ValueError('wrong historical pair')
    if fields!=[ep['previous'],ep['final']]:raise ValueError('wrong retained input/output pair')
    a,b=rows
    if a['input_sha256']!=fields[0]['sha256'] or a['output_sha256']!=fields[1]['sha256'] or a['output_sha256']!=b['input_sha256']:
        raise ValueError('broken previous-to-final lineage')
    return a


def source_plan(out):
    ev=ROOT/'handoff/evidence';ap=ev/'20261002-x20-half-prediction-83131-review.json';a=pipeline.read(ap)
    prev=ROOT/'outputs/hpc/x20-83111-half-prediction-20261002';decl=pipeline.read(prev/'declaration.json')
    validate_prediction(a,decl)
    arc=ROOT/'outputs/review-20260925/83131-half-prediction-review.tar.gz';receipt=a['receipt']
    if pipeline.sha256(arc)!=receipt['sha256'] or arc.stat().st_size!=receipt['size_bytes']:raise ValueError('83131 archive')
    ix={c['path']:c for c in receipt['files']};claims=[pipeline.claim(ap),pipeline.claim(arc)]
    for name in ('declaration.json','prediction.json','summary.json','status.json'):
        c=pipeline.claim(prev/name)
        if c['sha256']!=ix[name]['sha256'] or c['size_bytes']!=ix[name]['size_bytes']:raise ValueError('live prediction differs')
        claims.append(c)
    reused.verify(decl['source_claims']+decl['code']);claims+=decl['source_claims']
    oldap=ev/'20261001-x20-82989-final-review.json';old_a=pipeline.read(oldap);original=old_a['archive'];oldarc=ROOT/original['path']
    if old_a['job_id']!=82989 or not old_a['completed_experiment'] or not old_a['all_original_zero_gates_passed']:raise ValueError('82989 source not audited')
    if oldarc.stat().st_size!=original['size_bytes'] or pipeline.sha256(oldarc)!=original['sha256']:raise ValueError('82989 archive')
    src=ROOT/'outputs/hpc/x20-historical-seed-feedback-20261001';folder=src/'historical'
    names=['historical/'+n for n in ('config.json','state.json','trial_material.npz','endpoints-map16/manifest.json','pair16/feedback_protocol.json')]
    with tarfile.open(oldarc) as tar:
        for name in names:
            if hashlib.sha256(tar.extractfile(name).read()).hexdigest()!=pipeline.sha256(src/name):raise ValueError('82989 source changed '+name)
            claims.append(pipeline.claim(src/name))
    cfg=pipeline.read(folder/'config.json');state=pipeline.read(folder/'state.json');manifest=pipeline.read(folder/'endpoints-map16/manifest.json')
    if state['config_sha256']!=pipeline.sha256(folder/'config.json') or state['history'][-2:]!=manifest['history_rows'] or state['active_map'] is not None:raise ValueError('source config/history')
    row=previous_pair_row(manifest,decl['fields'][:2])
    trial=core.v.load_arrays(folder/'trial_material.npz');protocol=pipeline.read(folder/'pair16/feedback_protocol.json')
    if protocol['sources']['previous_radiation']!=decl['fields'][0] or protocol['sources']['final_radiation']!=decl['fields'][1]:raise ValueError('feedback endpoint identity')
    needed=[protocol['sources'][k] for k in ('outer_base_material','base_residual','physical_old_time_level')]
    reused.verify(needed);claims+=needed
    base=core.v.load_arrays(ROOT/needed[0]['path']);r20=np.load(ROOT/needed[1]['path'],allow_pickle=False);old=core.v.load_arrays(ROOT/needed[2]['path'])
    core.prior.fixed.exact_trial(trial,base,r20,old,'control')
    native=core.prior.reused.audit_native_trial(cfg,trial)
    if not native['native_mirrored_material_exact'] or not native['physical_phase_and_dt_exact']:raise ValueError('native identity')
    if int(trial['phase_index'])!=1367 or float(trial['step_duration_s'])!=889.419892762322:raise ValueError('phase/dt')
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(folder/'trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfg);core.prior.fixed.same_trial(trial,core.v.load_arrays(inputs/'trial_material.npz'))
    reused.verify([decl['geometry']]);claims.append(decl['geometry'])
    with np.load(ROOT/decl['geometry']['path'],allow_pickle=False) as z:geometry={k:z[k] for k in ('mu','weight','width')}
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    claims += [pipeline.claim(oldap),pipeline.claim(oldarc),*cases['control'].values(),*decl['fields']]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    c=decl['global_coefficients']
    return dict(cases=cases,claims=claims,basis=decl['fields'],source_row=row,candidate=dict(selected_coefficients=c),coefficients=[c]*76,geometry=geometry)
def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('SLURM_CPUS_PER_TASK')!='32' or os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('32CPU and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,unix=time.time(),**kw))
    mark('preparing')
    try:
        plan=source_plan(out);c=plan['candidate'];coefficients=plan['coefficients'];paths=[ROOT/x['path'] for x in plan['basis']]
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_83131_true_validation.sbatch','tests/test_x20_83131_true_validation.py','handoff/protocols/x20-83131-true-validation-v1.md')]
        reused.verify(plan['claims']+code);reused.checkpoint()
        declaration=dict(cases=plan['cases'],claims=plan['claims'],code=code,basis=plan['basis'],source_row=plan['source_row'],
            source_jobs=[81769,82273,82518,82989,83063,83075,83104,83111,83131],selected_coefficients=coefficients,global_coefficients=c['selected_coefficients'],coefficient_mode='one_global_triple_repeated',coefficient_selection='joint_objective_constrained_reviewed_half',
            maximum_maps=2,maximum_feedback_pairs=0,maximum_candidates=1,full_fraction=1.,half_fraction=.5,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            environment=pipeline.environment())
        reused.immutable(out/'declaration.json',declaration)
        if shutil.disk_usage(out).free<10*pipeline.STATE_BYTES:raise RuntimeError('insufficient disk')
        full,half=out/'full.dat',out/'half.dat';mark('writing_candidates')
        write_candidates(paths,pipeline.SHAPE,coefficients,full,half,reused.checkpoint)
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
        affinity=prediction_error(paths+[ROOT/measured[n]['output_path'] for n in ('full','half')],pipeline.SHAPE,coefficients,reused.checkpoint)
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
