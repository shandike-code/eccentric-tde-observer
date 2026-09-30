"""Audit immutable multi-pair snapshots of 82273, with explicit partial/terminal scope."""
import argparse,json
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_x20_accelerated_pair08 as first
history,prior,cw,arrays=first.history,first.prior,first.cw,first.arrays
from handoff.audit_tools.review_x20_window_prediction import local_path

def read(path):return json.loads(Path(path).read_text())
ROOT=first.ROOT
ORDER=[('accelerated',8),('historical',8),('accelerated',16),('historical',16)]


def verify_pair(dec,name,n):
    assert dec['feedback_evaluated'] and dec['zero_pair_stable'] and not dec['physical_response_failures']
    assert len(dec['original_zero_gates'])==7 and all(dec['original_zero_gates'].values())
    assert not dec['baseline_replaced'] and not dec['accepted_material_step']
    assert dec['continuation_pass'] and dec['reason']=='pass'
    assert ('eight_map_window' in dec)==(n==16)
    assert ('cross_history' in dec)==(name=='historical')


def qualification(pairs,cross,terminal):
    # 部分归档不能冒充终态；未评估使用None，不能用false/true代替。
    if not terminal:return None
    assert set(pairs)=={name+str(n) for name,n in ORDER} and set(cross)=={'8','16'}
    return all(pairs[name+'16']['eight_map_window']['passed'] for name in ('accelerated','historical')) and cross['16']['residual_comparison']['passed'] and cross['16']['cross_rate_pass']


def localization(delta,mass):
    # 完全相同的向量没有可定义的贡献份额，保留零范数和null，不能加floor。
    delta=np.asarray(delta);mass=np.asarray(mass)
    if delta.shape!=(512,) or mass.shape!=(128,) or not np.isfinite(delta).all() or not np.isfinite(mass).all() or np.any(mass<=0):
        raise ValueError('invalid vector or mass')
    if np.array_equal(delta,np.zeros_like(delta)):
        return dict(mass_norm_squared=0.,component_fractions=None,cell_fractions=None,largest_cells=[],cell_index_is_not_geometrical_depth=True)
    return history.localization(delta,mass)


def verify_plan(d,seeds):
    assert d['maximum_maps']==32 and d['maximum_feedback_pairs']==4
    assert d['cadence']==[8,16] and d['child_limits']==dict(accelerated=16,historical=16)
    assert d['case_order']==['accelerated','historical'] and d['seeds']==seeds
    assert d['accepted_outer_steps']==20 and d['new_material_steps']==0
    assert d['source_jobs']==[76727,80195,81769,82214]
    assert d['window_r20_tolerance']==.001 and d['window_signal_tolerance']==.1
    assert d['first_window_cross_history_is_measurement_only'] and d['drift_failure_does_not_skip_other_matched_case']
    assert d['both_branches_identical_x20'] and d['historical_failures_retained']
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))
    e=d['environment']['scheduler']
    assert e['SLURM_JOB_ID']=='82273' and e['SLURM_CPUS_PER_TASK']=='32' and e['SLURM_MEM_PER_NODE']=='131072'


def settled_entries(out):
    entries=[(name,n) for name,n in ORDER if (out/name/f'pair{n:02d}/decision.json').exists()]
    assert entries and entries==ORDER[:len(entries)], 'non-prefix or empty feedback archive'
    for name,n in entries:
        dec=read(out/name/f'pair{n:02d}/decision.json')
        if dec.get('physical_response_failures') or not dec.get('zero_pair_stable') or not dec.get('continuation_pass'):
            raise ValueError('hard-failed pair requires dedicated failure audit; no success verdict: '+name+str(n))
    return entries


def review(base,out,target,terminal_path=None):
    inventory=cw.receive(ROOT/(base+'.tar.gz'),ROOT/(base+'-receipt.json'),out)
    assert inventory==read(ROOT/(base+'.json'))
    entries=settled_entries(out)
    d=read(out/'declaration.json');seeds=read(out/'seed-claims.json');verify_plan(d,seeds)
    source=ROOT/'x20-window-82214-received';oldhistory=ROOT/'x20-feedback-81769-complete-received'
    current=ROOT/'boundary-response-80195-received';accepted=Path('outputs/review-20260924/common-confirmation20-76727-received')
    for folder,evidence,arcroot in [(source,'20260930-x20-window-validation-review.json',ROOT),
        (oldhistory,'20260930-x20-81769-final-review.json',ROOT),
        (current,'20260929-boundary-response-review.json',ROOT),
        (accepted,'20260924-common-confirmation20-review.json',accepted.parent)]:history.source_archive(folder,evidence,arcroot)
    source_audit=read('handoff/evidence/20260930-x20-window-validation-review.json')
    assert source_audit['true_maps_independently_validated'] and len(source_audit['actual']['checks'])==16 and all(source_audit['actual']['checks'].values())
    source_decl=read(source/'declaration.json');full=read(source/'validation.json')['actual_maps']['full']
    expected=dict(accelerated=dict(path=full['output_path'],sha256=full['output_sha256'],size_bytes=10099884032),
        historical=read(oldhistory/'historical/endpoints-map16/manifest.json')['endpoints']['mapped_final'])
    assert seeds==expected and seeds['historical']==source_decl['basis'][3]
    assert read(source/'full/state.json')['history']==[full]
    for c in d['code']:prior.verify_claim(c,Path(c['path']))
    reference=ROOT/'common-step21-76808-received/inputs';physical_old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    assert np.array_equal(r20,arrays(accepted/'confirm2/common-feedback/final_response.npz')['residual'])
    trial=out/'inputs/trial_material.npz';t=arrays(trial);b=arrays(reference/'outer_base_material.npz')
    assert set(t)==set(b) and all(np.array_equal(t[k],b[k]) for k in t)
    assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    assert prior.digest(trial)==prior.digest(source/'full/trial_material.npz')==prior.digest(oldhistory/'historical/trial_material.npz')
    for c in d['cases']['control'].values():prior.verify_claim(c,out/'inputs'/Path(c['path']).name)
    assert read(out/'inputs/config.json')==read(source/'full/config.json')
    currentp=read(current/'control/pair10/feedback_protocol.json')
    prefixes={'outputs/hpc/x20-window-feedback-20260930/':out,'outputs/hpc/x20-window-validation-20260930/':source,
        'outputs/hpc/x20-accelerated-feedback-windows-20260930/':oldhistory,
        'outputs/hpc/x20-window-prediction-20260930/':ROOT/'x20-prediction-82187-received',
        'outputs/hpc/step21-boundary-seed-response-20260929/':current,'outputs/hpc/common-confirmation20-20260924/':accepted}
    exact={currentp['sources']['physical_old_time_level']['path']:physical_old,
        currentp['sources']['outer_base_material']['path']:reference/'outer_base_material.npz',
        currentp['sources']['base_residual']['path']:reference/'base_residual.npy'}
    known=source_decl['claims']+source_decl['code']+read(oldhistory/'declaration.json')['claims']+list(seeds.values())
    verified=0;external=[]
    for c in d['claims']:
        f=exact.get(c['path'],local_path(c['path']))
        for prefix,folder in prefixes.items():
            if c['path'].startswith(prefix):f=folder/c['path'][len(prefix):];break
        if '/archives/' in c['path']:f=ROOT/Path(c['path']).name
        if f.is_file():prior.verify_claim(c,f);verified+=1
        else:assert c in known,c['path'];external.append(c)
    control={e:arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    pop={e:arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    scale=np.min([cw.independent_norms(p-c,mass) for p in pop.values() for c in control.values()],axis=0)
    np.testing.assert_allclose(scale,[d['frozen_signal_scale'][k] for k in cw.NAMES],rtol=1e-12,atol=0)
    maps={};mappeaks=[];counts={};roundoff={};states={};configs={}
    for name in dict.fromkeys(name for name,n in entries):
        folder=out/name;state=read(folder/'state.json');cfg=read(folder/'config.json');native=read(folder/'native_trial_audit.json')
        counts[name]=len(state['history']);states[name]=state;configs[name]=cfg
        assert counts[name] in (8,16) and state['active_map'] is None
        assert cfg['warm_seed']==seeds[name] and cfg['workers']==16 and cfg['maximum_maps']==16 and cfg['radiation_threshold']==1e-4
        assert state['history'][0]['input_sha256']==seeds[name]['sha256'] and state['current_sha256']==state['history'][-1]['output_sha256']
        assert prior.digest(folder/'trial_material.npz')==prior.digest(trial)==state['trial_sha256']
        prior.verify_claim(native['trial_source'],folder/'trial_material.npz')
        assert native['native_mirrored_material_exact'] and native['physical_phase_and_dt_exact'] and read(folder/'initialized_identity.json')['native']==native
        maps[name],peaks=prior.audit_maps(out,name,max_maps=16);mappeaks+=peaks
        roundoff[name]=first.boundary_check(out,name,state['history'])
    ignore={'run','warm_seed','sources'}
    if len(configs)==2:
        assert {k:v for k,v in configs['accelerated'].items() if k not in ignore}=={k:v for k,v in configs['historical'].items() if k not in ignore}
    expected_counts={name:max(n for case,n in entries if case==name) for name in counts}
    assert counts==expected_counts
    assert all((out/name).exists()==(name in counts) for name in ('accelerated','historical'))
    vectors={};feedbacks={};pairs={};decisions={name:{} for name in counts};cross={};cross_details={};fbpeaks=[];localizations={}
    for name,n in entries:
        folder=out/name/f'pair{n:02d}';p=read(folder/'feedback_protocol.json');dec=read(folder/'decision.json');verify_pair(dec,name,n)
        assert p['diagnostic_scope']==dict(same_state_seed_response_windows=True,radiation_history=name,baseline_replacement_authorized=False)
        for k in ('acceptance_gates','formal_state_gates'):assert p[k]==currentp[k]
        for k,f in [('refreshed_direction_declaration',out/'declaration.json'),('retained_manifest',out/name/f'endpoints-map{n:02d}/manifest.json')]:prior.verify_claim(p['sources'][k],f)
        for c in p['common_code_claims']:prior.verify_claim(c,Path(c['path']))
        result,vec,peaks=prior.audit_pair(out,n,reference,physical_old,trial,name,material_kind='control',max_maps=16);fbpeaks+=peaks
        assert dec['original_zero_gates']==result['gate_checks'] and dec['parent_peak_rss_bytes']<6*1024**3
        for e in vec:prior.same_record(dict(zip(cw.NAMES,cw.independent_norms(vec[e],mass).tolist())),result['endpoints'][e]['norms'])
        origin_name,origin_n=name,16
        origin={e:arrays(oldhistory/f'{origin_name}/pair{origin_n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
        result['from_prior_feedback']=history.comparison(vec,origin,r20,mass,scale);prior.same_record(result['from_prior_feedback'],dec['from_prior_feedback'])
        result['within_pair_spread']=history.comparison(vec,vec,r20,mass,scale)
        vectors[name,n]=vec;feedbacks[name,n]={e:arrays(folder/f'{e}_feedback.npz') for e in vec}
        if n==16:
            result['eight_map_window']=history.comparison(vec,vectors[name,8],r20,mass,scale)
            prior.same_record(result['eight_map_window'],dec['eight_map_window'])
            localizations[name+'_window']=localization(vec['final']-vectors[name,8]['final'],mass)
        if name=='historical':
            # 两种初值的每个previous/final组合均保留，不能只挑差最小的一组。
            residual=history.comparison(vec,vectors['accelerated',n],r20,mass,scale)
            comps={a+'_vs_'+b:prior.pair._feedback_stability_comparison(x,y) for a,x in feedbacks[name,n].items() for b,y in feedbacks['accelerated',n].items()}
            rates={k:prior.pair._feedback_stability_gate_checks(v,p['acceptance_gates']) for k,v in comps.items()}
            cross[str(n)]=dict(residual_comparison=residual,all_four_rate_gate_checks=rates,cross_rate_pass=all(all(g.values()) for g in rates.values()))
            prior.same_record(cross[str(n)],dec['cross_history'])
            cross_details[str(n)]={k:{kk:vv.tolist() if isinstance(vv,np.ndarray) else vv for kk,vv in v.items()} for k,v in comps.items()}
            localizations['cross'+str(n)]=localization(vec['final']-vectors['accelerated',n]['final'],mass)
        pairs[name+str(n)]=result;decisions[name][str(n)]=dec
    terminal=terminal_path is not None;eligible=qualification(pairs,cross,terminal)
    if terminal:
        term=read(terminal_path);s=read(out/'summary.json');assert term['job_id']==82273 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        assert s['status']==read(out/'status.json')['status']=='paired_seed_windows_complete_requires_review'
        assert s['maps']==32 and s['map_counts']==counts and s['feedback_pair_count']==4 and s['cases']==decisions
        prior.same_record(cross,s['cross_history']);assert s['reference_calibration_eligible']==eligible
        assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and s['baseline_replaced'] is False and s['strict_error_bound'] is False
        assert s['parent_peak_rss_bytes']<6*1024**3
        assert 'NumCPUs=32' in term['scontrol'] and 'QOS=qos_stu_cpu_long' in term['scontrol']
    else:
        assert not (out/'summary.json').exists()
        st=read(out/'status.json');assert st['status']=='feedback' and (st['case'],st['after_maps'])==entries[-1]
    result=dict(job_id=82273,archive=read(ROOT/(base+'-receipt.json')),verified_files=len(inventory['files']),verified_source_claims=verified,verified_code_claims=len(d['code']),external_claims_bound_to_prior_audits=external,source_jobs=[81769,82214],
        completed_experiment=terminal,map_counts=counts,maps=maps,pairs=pairs,cross_history=cross,cross_feedback_comparisons=cross_details,localization=localizations,
        map_process_receipts=len(mappeaks),feedback_process_receipts=len(fbpeaks),maximum_proc_kib=max(mappeaks+fbpeaks),boundary_reduction_roundoff=roundoff,
        all_original_zero_gates_passed=True,reference_calibration_eligible=eligible,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
        independent_vector_reduction=True,original_gate_kernels_reused=True,material_ode_recomputed_on_mac=False,large_fields_recomputed_on_mac=False,strict_error_bound=False)
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('job_id','verified_files','map_counts','map_process_receipts','feedback_process_receipts','maximum_proc_kib','reference_calibration_eligible','cross_history')},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--target',type=Path,required=True);p.add_argument('--terminal',type=Path);a=p.parse_args()
    review(a.base,a.out,a.target,a.terminal)
