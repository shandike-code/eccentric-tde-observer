"""New-protocol fixed-state feedback reassessment after common-window source audit."""
from copy import deepcopy
from dataclasses import asdict
import re
import shutil
from operations.common_frequency_audit import *
from diagnostics.material_energy_ledger import ledger
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
COMMON='outputs/hpc/common-frequency-pair-20260923'
FORMAL='source_formal_heating_erg_s_cm3'


def bridge_state_gates(historical):
    expected=pair._formal_state_gates()
    # HPC历史协议仅将墙钟资源预算改为7200s；科学门必须完全一致。
    inherited=dict(expected);inherited['each_state_wall_time_strictly_below_s']=7200.
    if historical!=inherited:raise RuntimeError('historical HPC thresholds changed')
    return expected  # 本桥显式采用更严格的900s，不修改历史协议。


def validate_identity(trial,base,residual,old):
    alpha=float(trial['relaxation']);phase=int(trial['phase_index'])
    if alpha!=1/64:raise RuntimeError('unexpected candidate amplitude')
    if (float(base['relaxation'])!=0 or not np.array_equal(base['encoded_state'],base['base_encoded_state'])
        or not np.array_equal(base['base_residual'],residual)):
        raise RuntimeError('outer baseline is not the frozen zero control')
    for key,expected in [('base_encoded_state',base['encoded_state']),('base_residual',residual),
                         ('finite_direction',residual),('encoded_state',base['encoded_state']+alpha*residual)]:
        if not np.array_equal(trial[key],expected):raise RuntimeError('candidate identity changed: '+key)
    for key in ('density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(trial[key],base[key]):raise RuntimeError('base physical identity changed: '+key)
    if (float(trial['step_duration_s'])!=float(old['step_duration_s'][phase])
        or not np.array_equal(trial['density_g_cm3'],old['density_g_cm3'][phase])):
        raise RuntimeError('physical old time level changed')
    codec=pair.GroundStateLogSimplexCodec(len(trial['temperature_k']));decoded=codec.decode(trial['encoded_state'])
    for key in ('temperature_k','hydrogen_fraction','helium_fraction'):
        if not np.array_equal(trial[key],getattr(decoded,key)):raise RuntimeError('exact native decode changed: '+key)


def replace_partial(old,common):
    if common.shape!=old[FORMAL].shape or not np.isfinite(common).all():raise ValueError('invalid new formal source')
    result={k:np.array(v,copy=True) for k,v in old.items()};result[FORMAL]=np.array(common,copy=True)
    return result


def assembled_feedback(combined,width):
    if np.asarray(width).shape!=(4096,):raise ValueError('wrong radiation depth grid')
    result={'subcell_width_cm':np.array(width,copy=True)}
    for key,v in combined.items():
        if v.shape[0]!=4096:raise ValueError('partial depth axis changed')
        result[key]=v
        # 与旧适配器完全相同的4096->256->128几何映射。
        parent=v.reshape(256,16,*v.shape[1:]).mean(axis=1)
        result['parent_'+key]=parent;result['half_'+key]=parent[:128]
    return result


def state_checks(fb,records,ownership,wall,peak,gates):
    w=fb['subcell_width_cm'];rate=fb['atomic_rate_heating_erg_s_cm3']
    direct=native.phase7b7f._source_metrics(rate,fb['source_direct_heating_erg_s_cm3'],w)
    formal=native.phase7b7f._source_metrics(rate,fb[FORMAL],w)
    mirrors=[native._mirror_residual(v) for k,v in fb.items() if k.startswith('parent_')]
    checks={
        'block_count':len(records)==gates['block_count_exactly'],
        'frequency_ownership':len(ownership)==gates['owned_frequency_group_count_exactly'] and bool(np.all(ownership==1)),
        'positive_intensity':min(r['minimum_owned_comoving_mean_intensity'] for r in records)>=gates['minimum_comoving_mean_intensity_at_least'],
        'finite_arrays':all(np.isfinite(v).all() for v in fb.values()),
        'positive_width':bool(np.all(w>0)),
        'nonnegative_atomic_rates':all(np.all(fb[k]>=0) for k in ('photoionization_s1','spontaneous_recombination_cm3_s','stimulated_recombination_cm3_s','total_recombination_cm3_s')),
        'direct_volume':direct[0]<gates['atomic_rate_vs_direct_comoving_heating_volume_l1_below'],
        'formal_volume':formal[0]<gates['atomic_rate_vs_inverse_four_force_volume_l1_below'],
        'formal_global':formal[1]<gates['atomic_rate_vs_inverse_four_force_global_fraction_below'],
        'mirror':max(mirrors)<gates['maximum_parent_mirror_residual_below'],
        'memory':peak<gates['each_process_peak_rss_strictly_below_mib'],
        'wall':wall<gates['each_state_wall_time_strictly_below_s']}
    return {k:bool(v) for k,v in checks.items()},direct,formal,max(mirrors)


def require_complete_states(manifests):
    if len(manifests)!=2 or any(m['status']!='complete' or not m['state_gate_passed'] for m in manifests.values()):
        raise RuntimeError('new common-domain formal state gate failed; no material response')


def verify_response_ledger(book,response):
    # 独立账本拆分热能与电离能，不以正温度代替总能量/布居一致性。
    if not all(np.isfinite(v).all() for v in book.values()):raise RuntimeError('nonfinite response ledger')
    if not np.all(book['remaining']>0):raise RuntimeError('response ledger disagrees with physical domain')
    for key,value in (('target',response.target_specific_material_energy_erg_g),
                      ('new_h',response.hydrogen_fraction),('new_he',response.helium_fraction)):
        if not np.allclose(book[key],value,rtol=1e-12,atol=0):raise RuntimeError('response ledger mismatch: '+key)


def build_state(out,label,proto,origin_sha,started,common_wall):
    original=pipeline.read(ROOT/SOURCE/f'feedback/{label}_manifest.json')
    cfolder=ROOT/COMMON/label;plan=pipeline.read(cfolder/'common_declaration.json');summary=pipeline.read(cfolder/'summary.json')
    if plan['source']!=SOURCE or plan['endpoint']!=label or plan['selected_blocks']!=list(range(76)):
        raise RuntimeError('common-source endpoint declaration changed')
    if not summary['all_76_blocks'] or summary['status']!='common_source_consistent':raise RuntimeError('common source not fully validated')
    reused.verify([summary['arrays']])
    if original['status']!='gate_failed' or original['protocol_sha256']!=pipeline.sha256(ROOT/SOURCE/'feedback_protocol.json'):
        raise RuntimeError('historical verdict or lineage changed')
    rad=proto['sources'][label+'_radiation']
    if original['state_path']!=rad['path'] or original['state_sha256']!=rad['sha256']:raise RuntimeError('radiation identity mismatch')
    oldfb=load_arrays(ROOT/original['feedback_artifact_path']);common=load_arrays(ROOT/summary['arrays']['path'])
    folder=out/'feedback'/label;folder.mkdir(parents=True,exist_ok=False)
    combined={};old_combined={};records=[];ownership=np.zeros(9632,dtype=np.int64);peaks=[]
    for i,row in enumerate(original['completed_blocks']):
        if row['block_index']!=i:raise RuntimeError('source block sequence changed')
        old=load_arrays(ROOT/row['partial_path']);report=pipeline.read(cfolder/f'block{i:02d}.json')
        data=load_arrays(ROOT/report['arrays']['path']);receipt=pipeline.read(cfolder/f'block{i:02d}.process.json')
        if not report['original_source_bitwise_replayed'] or receipt['returncode']!=0 or not receipt['memory_guard_passed']:
            raise RuntimeError('source reproduction or resource receipt failed')
        reused.verify([report['arrays']])
        if pipeline.sha256(ROOT/row['partial_path'])!=row['partial_sha256']:raise RuntimeError('old partial changed')
        for k in KEYS:
            if not np.array_equal(data['original_'+k],old[STORED[k]]):raise RuntimeError('source block replay mismatch')
        if (row['core_group_start'],row['core_group_stop'])!=(report['core_group_start'],report['core_group_stop']):raise RuntimeError('ownership indices changed')
        ownership[row['core_group_start']:row['core_group_stop']]+=1
        new=replace_partial(old,data['common_formal_erg_s_cm3'])
        if not combined:
            combined={k:np.zeros_like(v) for k,v in new.items()};old_combined={k:np.zeros_like(v) for k,v in old.items()}
        if set(new)!=set(combined):raise RuntimeError('partial field schema changed')
        for k in combined:combined[k]+=new[k];old_combined[k]+=old[k]
        path=folder/f'block{i:02d}.npz';np.savez(path,**new);claim=pipeline.claim(path)
        peak=max(row['peak_process_rss_mib'],report['native_peak_mib']);peaks.append(peak)
        records.append({**row,'partial_path':claim['path'],'partial_sha256':claim['sha256'],
                        'peak_process_rss_mib':peak,'runtime_s':row['runtime_s']+report['wall_s'],
                        'legacy_partial_path':row['partial_path'],'legacy_partial_sha256':row['partial_sha256'],
                        'common_source_arrays':report['arrays'],'new_formal_computed_independently':True})
    for k,v in old_combined.items():
        if not np.array_equal(v,oldfb[k]):raise RuntimeError('old full feedback mismatch')
    if not np.array_equal(combined[FORMAL],common['common_formal_erg_s_cm3']):raise RuntimeError('common full feedback mismatch')
    fb=assembled_feedback(combined,oldfb['subcell_width_cm'])
    changed={FORMAL,'parent_'+FORMAL,'half_'+FORMAL}
    if set(fb)!=set(oldfb):raise RuntimeError('feedback schema changed')
    for k,v in fb.items():
        if k not in changed and not np.array_equal(v,oldfb[k]):raise RuntimeError('nonformal field changed: '+k)
    # 保守上界：旧态实测耗时+整个双态common作业耗时+当前桥至今耗时。
    wall=float(original['accumulated_wall_runtime_s'])+common_wall+time.monotonic()-started
    rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    peak=max(*peaks,rss);checks,direct,formal,mirror=state_checks(fb,records,ownership,wall,peak,proto['formal_state_gates'])
    path=out/f'{label}_feedback.npz';np.savez(path,**fb);claim=pipeline.claim(path)
    manifest={'status':'complete' if all(checks.values()) else 'gate_failed','state_gate_passed':all(checks.values()),
              'protocol_sha256':origin_sha,'state_path':rad['path'],'state_sha256':rad['sha256'],
              'completed_blocks':records,'feedback_artifact_path':claim['path'],'feedback_artifact_sha256':claim['sha256'],
              'gate_checks':checks,'rate_direct_volume_l1':direct[0],'rate_formal_volume_l1':formal[0],
              'rate_formal_global_fraction':formal[1],'integrated_atomic_rate_heating_erg_s_cm2':formal[2],
              'integrated_formal_heating_erg_s_cm2':formal[3],'maximum_parent_mirror_residual':mirror,
              'maximum_process_peak_rss_mib':peak,'accumulated_wall_runtime_s':wall,
              'wall_is_conservative_upper_bound':True,'historical_state_gate_passed':False,
              'physical_frequency_window':'same comoving window for atomic/direct/lab four-force',
              'unchanged_fields_verified_bitwise':sorted(set(fb)-changed)}
    reused.immutable(out/'feedback'/f'{label}_manifest.json',manifest);return manifest


def run_bridge(out):
    pipeline.require_allocation(1);started=time.monotonic()
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    pipeline.write_json(out/'status.json',{'status':'verifying_sources','material_step_promoted':False})
    try:
        source=ROOT/SOURCE/'feedback_protocol.json';proto=pipeline.read(source)
        historical_gates=deepcopy(proto['formal_state_gates'])
        proto['formal_state_gates']=bridge_state_gates(historical_gates)
        proto['resource_change']='Common bridge uses a conservative 900 s state bound; historical HPC budget was 7200 s. Science gates unchanged.'
        pair._require_exact_acceptance_gates({'gates':proto['acceptance_gates'],'authorization':{
            'accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass':True,
            'reject_this_trial_if_any_gate_fails':True,'accept_dynamic_nlte_solution':False}})
        claims=[pipeline.claim(source)];terminal=ROOT/'outputs/review-20260923/scheduler-75908/scheduler-terminal.json'
        status=pipeline.read(terminal);match=re.search(r'\bRunTime=(\d+):(\d+):(\d+)\b',status['scontrol'])
        if status['state']!='COMPLETED' or status['job_id']!=75908 or not match:raise RuntimeError('common job terminal evidence invalid')
        common_wall=sum(int(v)*scale for v,scale in zip(match.groups(),(3600,60,1)))
        for label in ('previous','final'):
            folder=ROOT/COMMON/label;plan=pipeline.read(folder/'common_declaration.json')
            claims.extend(plan['claims'])
            for f in folder.iterdir():
                if f.suffix in ('.json','.npz'):claims.append(pipeline.claim(f))
        claims.append(pipeline.claim(terminal))
        for f in ('operations/common_feedback_bridge.py','operations/common_feedback_bridge.sbatch','tests/test_common_feedback_bridge.py','handoff/protocols/common-frequency-feedback-v1.md'):
            claims.append(pipeline.claim(ROOT/f))
        unique={}
        for c in claims:
            if c['path'] in unique and unique[c['path']]!=c:raise RuntimeError('conflicting claims')
            unique[c['path']]=c
        claims=list(unique.values());reused.verify(claims)
        origin={'phase':'common-frequency-feedback-origin-v1','source_protocol':pipeline.claim(source),'claims':claims,
                'common_frequency_equations':'handoff/protocols/common-frequency-source-v1.md','environment':pipeline.environment(),
                'formal_state_gates':proto['formal_state_gates'],'historical_formal_state_gates':historical_gates,
                'old_verdicts_immutable':True,'new_maps':0,
                'material_step_promoted':False,'source_job_full_wall_seconds':common_wall}
        origin_path=out/'origin_protocol.json';reused.immutable(origin_path,origin);origin_sha=pipeline.sha256(origin_path)
        inputs=out/'inputs';inputs.mkdir()
        for key in ('trial_material','base_residual','outer_base_material','physical_old_time_level'):
            old=proto['sources'][key];target=inputs/(key+Path(old['path']).suffix);shutil.copy2(ROOT/old['path'],target)
            new=pipeline.claim(target)
            if (new['sha256'],new['size_bytes'])!=(old['sha256'],old['size_bytes']):raise RuntimeError('input snapshot changed')
            proto['sources'][key]=new
        t=load_arrays(ROOT/proto['sources']['trial_material']['path']);base=load_arrays(ROOT/proto['sources']['outer_base_material']['path'])
        residual=np.load(ROOT/proto['sources']['base_residual']['path'],allow_pickle=False);old=load_arrays(ROOT/proto['sources']['physical_old_time_level']['path'])
        validate_identity(t,base,residual,old)
        template=pair._validate_worker_template_sources(proto);adapted=pair.adapt_phase7b7j_worker_protocol(proto,template,'final')
        ctx=native.phase7b7f.phase7b7e.phase7b5x._context(adapted);material=native.phase7b7i._second_full_material(adapted)
        for field,key in (('density_g_cm3','density_parent'),('temperature_k','temperature_parent'),('hydrogen_fraction','hydrogen_parent'),('helium_fraction','helium_parent')):
            if not np.array_equal(material[key],np.concatenate((t[field],t[field][::-1]))):raise RuntimeError('native candidate mismatch')
        if ctx['phase']!=int(t['phase_index']) or ctx['duration_s']!=float(t['step_duration_s']):raise RuntimeError('native time level changed')
        reused.immutable(out/'identity.json',{'alpha':float(t['relaxation']),'phase':int(t['phase_index']),'duration_s':float(t['step_duration_s']),'native_and_encoded_exact':True,'sources':proto['sources']})
        manifests={label:build_state(out,label,proto,origin_sha,started,common_wall) for label in ('previous','final')}
        require_complete_states(manifests)
        cfg=proto['configuration'];cfg.update(reuse_completed_feedback_manifests=True,feedback_origin_protocol_sha256=origin_sha,maximum_concurrent_processes=1)
        paths={'summary_path':'feedback_summary.json','figure_path':'feedback.png','target_material_output':'target_material.npz',
               'encoded_residual_output':'material_residual.npy','feedback_work_directory':'feedback',
               'previous_feedback_output':'previous_feedback.npz','final_feedback_output':'final_feedback.npz'}
        for k,name in paths.items():cfg[k]=str((out/name).relative_to(ROOT))
        proto['phase']='common-frequency-feedback-reassessment-v1'
        proto['sources']['common_origin_protocol']=pipeline.claim(origin_path)
        for label in manifests:
            proto['sources'][label+'_feedback_manifest']=pipeline.claim(out/'feedback'/f'{label}_manifest.json')
            proto['sources'][label+'_feedback_artifact']=pipeline.claim(out/f'{label}_feedback.npz')
        proto['authorization'].update(reuse_only_after_bytewise_reproduction_audit=True,
            accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass=True,reject_this_trial_if_any_gate_fails=True)
        protocol=out/'feedback_protocol.json';reused.immutable(protocol,proto)
        result=pair.run_pair(protocol,pipeline.sha256(protocol))
        responses={};phase=int(t['phase_index'])
        for label in manifests:
            fb=load_arrays(out/f'{label}_feedback.npz')
            book=ledger(fb,t['density_g_cm3'],float(t['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            np.savez(out/f'{label}_energy_ledger.npz',**book)
            responses[label]={'minimum_gas_heat_erg_g':float(np.min(book['remaining']))}
            if label not in result.get('material_response_failures',{}):
                response,vector,context=pair._material_response_residual(proto,fb)
                np.savez(out/f'{label}_response.npz',residual=vector,temperature_k=response.temperature_k,
                         hydrogen_fraction=response.hydrogen_fraction,helium_fraction=response.helium_fraction,
                         target_specific_material_energy_erg_g=response.target_specific_material_energy_erg_g)
                verify_response_ledger(book,response)
                if label=='final' and not result.get('material_response_failures') and not np.array_equal(vector,np.load(out/'material_residual.npy')):raise RuntimeError('native response replay differs')
                responses[label]['norms']=asdict(encoded_residual_norms(vector,context['cell_mass']))
        reused.verify(claims)
        rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
        if rss>=6144:raise RuntimeError('bridge native memory guard failed')
        reused.immutable(out/'reassessment.json',{'responses':responses,'pair_gate_checks':result['gate_checks'],
            'pair_decision':result['decision'],'native_peak_mib':rss,'wall_s':time.monotonic()-started,
            'material_step_promoted':False,'accepted_outer_steps_remain':15,'independent_proc_review_required':True,
            'frequency_truncation_convergence_established':False})
        pipeline.write_json(out/'status.json',{'status':'response_evaluated_requires_review','material_step_promoted':False})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc),'material_step_promoted':False});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run_bridge(pipeline.safe_path(ROOT,a.run))


if __name__=='__main__':main()
