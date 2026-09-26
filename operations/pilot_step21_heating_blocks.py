"""Two bounded fixed-halo source-correction pilots on current x20 heating blocks."""
import argparse,os,resource,signal,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from operations import paired_block_krylov as local
from operations import validate_step21_heating_projection as heat
from eccentric_tde_observer.mixed_frame_ali import mixed_frame_spatial_source_residual_correction
from eccentric_tde_observer.mixed_frame_frequency import lorentz_ray_transform,lorentz_remap_comoving_group_extinction_to_lab
ROOT,pipeline,reused,fresh,v,fixed=heat.ROOT,heat.pipeline,heat.reused,heat.fresh,heat.v,heat.fixed
checked_field,verify_map_replay,evaluate_direction=local.checked_field,local.verify_map_replay,local.evaluate_direction
BLOCKS=(24,48)
SOURCE='outputs/hpc/step21-heating-validation-20260926'


def settled_pair(state,retained):
    rows=state['history']
    if state['active_map'] is not None or len(rows)!=10 or [x['iteration'] for x in rows]!=list(range(1,11)):
        raise RuntimeError('source must be settled ten-map history')
    if retained['history_rows']!=rows[-2:] or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(rows,rows[1:])):
        raise RuntimeError('source lineage mismatch')
    inp,out=retained['endpoints']['final'],retained['endpoints']['mapped_final']
    if inp['sha256']!=rows[-1]['input_sha256'] or out['sha256']!=rows[-1]['output_sha256']:
        raise RuntimeError('not the actual final map pair')
    return inp,out


def worker(out, label, index):
    plan = pipeline.read(out/'declaration.json')
    reused.verify(plan['code'])
    if pipeline.read(out/'declaration.json')['blocks']!=list(BLOCKS):raise RuntimeError('block declaration changed')
    if label!='control' or index not in BLOCKS:raise ValueError('unregistered local case')
    record = plan['cases'][label]
    cfg = pipeline.read(ROOT/record['config']['path'])
    for c in [record['config'], record['trial'], record['state']]:
        if pipeline.sha256(ROOT/c['path']) != c['sha256']:
            raise RuntimeError('worker input declaration changed')
    source = ROOT/record['input']['path']
    native, fixed, template, context = pipeline.configure_native(cfg, source)
    base = native.base
    block = context['blocks'][index]
    if (block.core_group_start, block.core_group_stop) != (128*index, 128*(index+1)):
        raise RuntimeError('selected block frequency ownership changed')
    material = base.phase7b7i._second_full_material(template)
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
    global_state = np.memmap(source, mode='r', dtype='<f8', shape=pipeline.SHAPE)
    active_start = int(context['stencil'].active_outer_group_start)
    active_stop = int(context['stencil'].active_outer_group_stop)
    first = max(block.outer_group_start, active_start)
    last = min(block.outer_group_stop, active_stop)
    if last > first:
        fields['outer'][first-block.outer_group_start:last-block.outer_group_start] = global_state[first-active_start:last-active_start]
    core = slice(block.core_group_start, block.core_group_stop)
    initial = np.array(global_state[core], copy=True)
    del global_state
    old_hash = pipeline.block_hash(source, core.start, core.stop)
    mu, weight = np.asarray(context['mu']), np.asarray(context['weight'])
    width = np.diff(context['stencil'].active_lab_edge_hz)[core]

    def source_map(guess):
        reused.checkpoint()
        result = base.phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
            block.local_stencil, fields['old_edge'], fields['new_edge'], mu, weight,
            fields['initial'], fields['outer'], fields['true_absorption'],
            fields['thermal_emissivity'], fields['scattering'], context['beta'], context['duration_s'],
            propagation_speed_cm_s=base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=guess, diagnostic_fixed_iteration_count=1,
            spatial_scheme='hybrid_step_turning_upwind', source_map_only=True)
        return np.array(result.final_lab_intensity_density, copy=True)

    started = time.perf_counter()
    mapped = source_map(initial)
    map_seconds = time.perf_counter()-started
    archived = np.memmap(ROOT/record['output']['path'], mode='r', dtype='<f8', shape=pipeline.SHAPE)
    replay = verify_map_replay(initial, mapped, archived[core])
    del archived
    transform = lorentz_ray_transform(mu, weight, context['beta'])
    extinction = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to((fields['true_absorption']+fields['scattering'])[:, None, :],
                        (block.local_stencil.comoving_collision_group_count, mu.size, len(context['beta']))),
        block.local_stencil.comoving_collision_edge_hz, block.local_stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving)
    krylov = mixed_frame_spatial_source_residual_correction(
        mapped-initial, fields['old_edge'], fields['new_edge'], block.local_stencil.outer_lab_edge_hz,
        block.local_stencil.comoving_collision_edge_hz, block.local_stencil.active_lab_edge_hz,
        block.local_stencil.active_outer_group_start, block.local_stencil.active_outer_group_stop,
        mu, weight, context['beta'], extinction, fields['scattering'], context['duration_s'],
        gmres_relative_tolerance=1e-5, gmres_restart=8, gmres_maximum_restart_cycles=2,
        allow_turning_ray_upwind=True, allow_incomplete_krylov=True)
    candidate, fresh, result = evaluate_direction(initial, mapped, krylov.correction, source_map)
    raw_boundary = float(np.sum(abs(base._block_flux(mapped, mu, weight, width)-base._block_flux(initial, mu, weight, width))))
    new_boundary = float(np.sum(abs(base._block_flux(fresh, mu, weight, width)-base._block_flux(candidate, mu, weight, width))))
    seconds = time.perf_counter()-started
    rss = base.ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform)/1024**2
    result['checks'].update(boundary_not_worse=new_boundary <= raw_boundary,
                            finite_budget=krylov.gmres_iteration_count <= 16,
                            memory_below_6gib=rss < 6144,
                            time_below_20_maps=seconds <= 20*map_seconds)
    if old_hash != pipeline.block_hash(source, core.start, core.stop):
        raise RuntimeError('source block changed during pilot')
    result.update(label=label, block_index=index, replay=replay, raw_map_s=map_seconds,
                  wall_s=seconds, peak_rss_mib=rss, raw_boundary_absolute=raw_boundary,
                  fresh_boundary_absolute=new_boundary, gmres_iterations=krylov.gmres_iteration_count,
                  gmres_info=krylov.gmres_reported_info, linear_audit_passed=krylov.fixed_point_converged,
                  linear_scaled_linf=krylov.final_scaled_linf_linear_residual,
                  mean_consistency=krylov.final_comoving_mean_consistency_linf,
                  input_block_sha256=old_hash, core_groups=[core.start, core.stop],
                  frequency_edges_hz=[float(context['stencil'].active_lab_edge_hz[core.start]),
                                      float(context['stencil'].active_lab_edge_hz[core.stop])],
                  eligible_for_further_block_review=all(result['checks'].values()),
                  global_candidate_written=False, formal_acceptance_changed=False)
    # 保留局部候选和实际映射，后续若获准组合无需重建方向；不是全局dat。
    saved=out/f'{label}-block{index:02d}-local.npz'
    with saved.open('xb') as f:np.savez(f,candidate=candidate,mapped_candidate=fresh)
    result['local_arrays']=pipeline.claim(saved)
    pipeline.write_json(out/f'{label}-block{index:02d}.json', result)



def prepare(out):
    source=ROOT/SOURCE;ev=ROOT/'handoff/evidence'
    audit=pipeline.read(ev/'20260926-heating-validation-complete-review.json')
    if audit['feedback_rounds']!=[2,10] or not audit['final_summary_present'] or audit['windows']['10']['window']['passed']:
        raise RuntimeError('require reviewed unresolved eight-map drift')
    names=['control/state.json','control/config.json','control/trial_material.npz','control/endpoints-map10/manifest.json',
           'control/pair10/feedback_protocol.json','declaration.json','summary.json']
    claims=v.audited_inputs(source,ev/'20260926-heating-validation-complete-review.json',
        ev/'20260926-heating-validation-77577-terminal.json',77577,names)
    state=pipeline.read(source/names[0]);cfg=pipeline.read(source/names[1]);ret=pipeline.read(source/names[3])
    inp,mapped=settled_pair(state,ret)
    if pipeline.sha256(source/names[1])!=state['config_sha256']:raise RuntimeError('source config changed')
    protocol=pipeline.read(source/names[4]);s=protocol['sources']
    base=v.load_arrays(ROOT/s['outer_base_material']['path']);r=np.load(ROOT/s['base_residual']['path'],allow_pickle=False)
    old=v.load_arrays(ROOT/s['physical_old_time_level']['path']);trial=v.load_arrays(source/names[2])
    fixed.exact_trial(trial,base,r,old,'control');fixed.same_trial(trial,base);fixed.native_identity(protocol)
    local.audit_native_trial(cfg,trial)
    ranking=ev/'20260926-heating-subspace-and-block-ranking.json';selection=pipeline.read(ranking)
    if selection['selected_local_pilot_blocks']!=list(BLOCKS) or selection['affine_proxy_lower_bound']['old_twenty_percent_cost_pass']:
        raise RuntimeError('preregistered route evidence changed')
    record=dict(input=inp,output=mapped,config=pipeline.claim(source/names[1]),trial=pipeline.claim(source/names[2]),state=pipeline.claim(source/names[0]))
    # 输入/输出完整SHA和物理身份必查；旧源全部代码保持原字节，不强迫读取无关历史dat。
    prior=pipeline.read(source/'declaration.json')
    claims+=list(record.values())+prior['code']+[s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]+[pipeline.claim(ranking)]
    claims += [c for c in cfg['sources'] if not c['path'].endswith('.dat')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/pilot_step21_heating_blocks.sbatch',
        'tests/test_pilot_step21_heating_blocks.py','handoff/protocols/step21-heating-block-pilot-v1.md')]
    reused.verify(claims+code)
    plan=dict(cases={'control':record},claims=claims,code=code,blocks=list(BLOCKS),workers=2,
        gmres_restart=8,gmres_cycles=2,gmres_tolerance=1e-5,maximum_source_maps_per_case=3,
        maximum_global_maps=0,maximum_feedback_pairs=0,accepted_outer_steps=20,new_material_steps=0,
        global_candidate_authorized=False,automatic_promotion=False,environment=pipeline.environment(),
        limitation='Fixed frequency halos; local directional test, not global or material convergence')
    reused.immutable(out/'declaration.json',plan);return plan


def bounded_process(command,stdout,stderr):
    process=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
    deadline=time.monotonic()+1800
    while process.poll() is None:
        if pipeline.STOP or time.monotonic()>=deadline:
            # relay和实际worker同组；停止/超时时整个组退出，不能留下后台孤儿计算。
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
            raise RuntimeError('local worker stopped or timed out')
        time.sleep(.2)
    if process.returncode:raise RuntimeError('local worker failed: '+str(process.returncode))


def execute(out):
    pipeline.require_allocation(2)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),accepted_outer_steps=20,new_material_steps=0,new_full_maps=0,**kw))
    mark('preparing')
    try:
        plan=prepare(out);mark('local_pilot')
        def launch(index):
            reused.checkpoint()
            receipt=out/f'control-block{index:02d}.process.json'
            command=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(receipt),'--',
                sys.executable,str(Path(__file__).resolve()),'--run',str(out.relative_to(ROOT)),'--worker','--block',str(index)]
            with (out/f'control-block{index:02d}.out').open('x') as stdout,(out/f'control-block{index:02d}.err').open('x') as stderr:
                bounded_process(command,stdout,stderr)
            result=pipeline.read(receipt)
            if result['returncode'] or not result['memory_guard_passed']:raise RuntimeError('local worker resource failure')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(launch,BLOCKS))
        reused.verify(plan['claims']+plan['code'])
        rows=[pipeline.read(out/f'control-block{i:02d}.json') for i in BLOCKS]
        reused.immutable(out/'summary.json',dict(rows=rows,all_local_cases_passed=all(r['eligible_for_further_block_review'] for r in rows),
            accepted_outer_steps=20,new_material_steps=0,new_full_maps=0,new_feedback_pairs=0,global_candidate_written=False,
            full_frequency_run_authorized=False,source_bytes_unchanged=True))
        mark('complete_requires_review');reused.archive(out,'complete')
    except BaseException as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--worker',action='store_true');p.add_argument('--block',type=int,choices=BLOCKS)
    a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    if a.worker:
        pipeline.require_allocation(1)
        if a.block is None:raise ValueError('worker block required')
        worker(out,'control',a.block)
    else:execute(out)
