"""Audit the 85861-seeded windows; saved reference, prior origin and scheduler evidence remain distinct."""
import argparse,json,subprocess,hashlib
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_x20_accelerated_pair08 as first
history,prior,cw,arrays=first.history,first.prior,first.cw,first.arrays
from handoff.audit_tools.review_x20_85861_true import local_path

def read(path):return json.loads(Path(path).read_text())
ROOT=first.ROOT
ORDER=[('historical',8),('historical',16)]


def verify_pair(dec,name,n):
    assert dec['feedback_evaluated'] and dec['zero_pair_stable'] and not dec['physical_response_failures']
    assert len(dec['original_zero_gates'])==7 and all(dec['original_zero_gates'].values())
    assert not dec['baseline_replaced'] and not dec['accepted_material_step']
    assert dec['continuation_pass'] and dec['reason']=='pass'
    assert ('eight_map_window' in dec)==(n==16)
    assert 'vs_saved_reference' in dec


def localization(delta,mass):
    # 完全相同的向量没有可定义的贡献份额，保留零范数和null，不能加floor。
    delta=np.asarray(delta);mass=np.asarray(mass)
    if delta.shape!=(512,) or mass.shape!=(128,) or not np.isfinite(delta).all() or not np.isfinite(mass).all() or np.any(mass<=0):
        raise ValueError('invalid vector or mass')
    if np.array_equal(delta,np.zeros_like(delta)):
        return dict(mass_norm_squared=0.,component_fractions=None,cell_fractions=None,largest_cells=[],cell_index_is_not_geometrical_depth=True)
    return history.localization(delta,mass)


def verify_plan(d,seeds,job):
    assert job==85875
    assert d['source_85821_scheduler_terminal_verified'] is True and d['source_84026_scheduler_terminal_verified'] is False
    assert d['git_commit']==d['environment']['git_commit'] and d['git_clean'] is True
    assert len(d['seed_stats_before'])==1
    q=d['seed_stats_before'][0];seed=seeds['historical']
    assert q['path']==seed['path'] and q['size_bytes']==seed['size_bytes'] and type(q['inode']) is int and q['inode']>0 and type(q['mtime_ns']) is int and q['mtime_ns']>0
    assert d['maximum_maps']==16 and d['maximum_feedback_pairs']==2
    assert d['cadence']==[8,16] and d['child_limits']==dict(historical=16)
    assert d['case_order']==['historical'] and d['seeds']==seeds
    assert d['accepted_outer_steps']==20 and d['new_material_steps']==0
    assert d['source_jobs']==[76727,80195,82518,84026,85821,85856,85859,85861]
    assert d['window_r20_tolerance']==.001 and d['window_signal_tolerance']==.1
    assert d['first_window_cross_history_is_measurement_only'] and d['drift_failure_does_not_skip_second_window']
    assert d['saved_and_new_identical_x20'] and d['historical_failures_retained']
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))
    assert not d['matched_new_two_branch_experiment'] and not d['reference_calibration_eligible']
    assert d['saved_reference']['job_id']==82518 and d['saved_reference']['case']=='accelerated' and d['saved_reference']['map']==16
    assert d['saved_reference']['new_maps']==d['saved_reference']['new_feedback_pairs']==0
    assert d['environment']['git_commit']=='4bace16902cbc2ef6f9f584f26f07a2928eecb93'
    assert not d['environment']['tracked_worktree_dirty']
    e=d['environment']['scheduler']
    assert e['SLURM_JOB_ID']==str(job) and e['SLURM_CPUS_PER_TASK']=='32' and e['SLURM_MEM_PER_NODE']=='131072'


def settled_entries(out):
    entries=[(name,n) for name,n in ORDER if (out/name/f'pair{n:02d}/decision.json').exists()]
    assert entries and entries==ORDER[:len(entries)], 'non-prefix or empty feedback archive'
    for name,n in entries:
        dec=read(out/name/f'pair{n:02d}/decision.json')
        if dec.get('physical_response_failures') or not dec.get('zero_pair_stable') or not dec.get('continuation_pass'):
            raise ValueError('hard-failed pair requires dedicated failure audit; no success verdict: '+name+str(n))
    return entries


def execution_evidence(term,batch,summary,job):
    assert job==term['job_id']==85875
    assert batch['job_id']==str(job) and type(batch['child_exit_status']) is int and batch['child_exit_status']==0
    assert batch['scheduler_terminal_verified'] is False
    assert term['summary']==summary and term['batch_exit']==batch
    tokens=dict(t.split('=',1) for t in term['scontrol'].split() if '=' in t)
    if term['state']=='COMPLETED':
        assert all(tokens.get(k)==v for k,v in dict(JobId=str(job),JobState='COMPLETED',ExitCode='0:0',NumCPUs='32',QOS='qos_stu_cpu_long',TimeLimit='04:00:00').items())
        verified=True
    else:
        assert term['state'] in ('RUNNING','COMPLETING','UNKNOWN')
        if tokens:
            assert tokens.get('JobId')==str(job) and tokens.get('JobState')==term['state']
        verified=False
    return dict(numerical_artifacts_complete=True,child_exit_status=0,
                scheduler_terminal_verified=verified,scheduler_terminal_state='COMPLETED' if verified else None)


def source_binding(audit,origin,seeds,full):
    expected={'full_l2_benefit','full_linf_nonincrease','half_l2_nonincrease','half_linf_nonincrease',
        'full_radiation','full_boundary_l1','full_boundary_bolometric','half_radiation','half_boundary_l1',
        'half_boundary_bolometric','independent_half_affinity','independent_half_linf_affinity',
        'full_l2_affinity','full_linf_affinity','half_l2_affinity','half_linf_affinity'}
    assert audit['job_id']==85861 and audit['numerical_commit']=='68452895c7953a4540d285a02e200b61f5b0cf3d'
    assert audit['execution']['scheduler_terminal_verified'] is True and audit['execution']['numerical_artifacts_complete'] is True
    assert type(audit['execution']['child_exit_status']) is int and audit['execution']['child_exit_status']==0
    assert audit['map_process_receipts']==152
    assert audit['true_maps_independently_validated'] and audit['independent_small_statistic_reduction']
    assert set(audit['actual']['checks'])==expected and all(v is True for v in audit['actual']['checks'].values())
    assert audit['actual_maps']['full']==full
    assert full['output_sha256']=='64992a047808bc99eed6463d11fba4cff655970b426f1141ee2efbdf164135de'
    assert seeds==dict(historical=dict(path=full['output_path'],sha256=full['output_sha256'],size_bytes=10099884032))
    for a in (audit,origin):
        assert a['accepted_outer_steps']==20 and a['new_material_steps']==0 and a['baseline_replaced'] is False
    assert origin['job_id']==85821 and origin['completed_experiment'] is True
    assert origin['numerical_commit']=='16ad4d6fabdec1e9e958d7168ead0828f25792c7'
    assert origin['numerical_artifacts_complete'] is True and origin['independent_vector_reduction'] is True
    assert origin['all_original_zero_gates_passed'] is True
    assert origin['scheduler_terminal_verified'] is True and origin['scheduler_terminal_state']=='COMPLETED'
    assert type(origin['child_exit_status']) is int and origin['child_exit_status']==0
    assert origin['map_process_receipts']==1216 and origin['feedback_process_receipts']==304
    assert origin['source_84026_scheduler_terminal_verified'] is False
    assert audit['field_stats_verified'] is True and audit['git_clean_verified'] is True
    assert audit['source_85821_scheduler_terminal_verified'] is True and audit['source_84026_scheduler_terminal_verified'] is False


def claim_path(path,out):
    prefixes={'outputs/hpc/x20-85861-seed-feedback-20261006/':out,
        'outputs/hpc/x20-85859-true-validation-20261006/':ROOT/'x20-85859-true-85861-received',
        'outputs/hpc/x20-global-window-feedback-20261001/':ROOT/'x20-global-feedback-82518-complete-received',
        'outputs/hpc/x20-85800-seed-feedback-20261006/':ROOT/'x20-85800-feedback-85821-received',
        'outputs/hpc/step21-boundary-seed-response-20260929/':ROOT/'boundary-response-80195-received',
        'outputs/hpc/common-confirmation20-20260924/':Path('outputs/review-20260924/common-confirmation20-76727-received')}
    if '/archives/' in path:return ROOT/Path(path).name
    for prefix,folder in prefixes.items():
        if path.startswith(prefix):return folder/path[len(prefix):]
    return local_path(path)


def review(base,out,target,job,terminal_path=None):
    inventory=cw.receive(ROOT/(base+'.tar.gz'),ROOT/(base+'-receipt.json'),out)
    assert inventory==read(ROOT/(base+'.json'))
    entries=settled_entries(out)
    d=read(out/'declaration.json');seeds=read(out/'seed-claims.json');verify_plan(d,seeds,job)
    source=ROOT/'x20-85859-true-85861-received';oldhistory=ROOT/'x20-global-feedback-82518-complete-received'
    originhistory=ROOT/'x20-85800-feedback-85821-received'
    current=ROOT/'boundary-response-80195-received';accepted=Path('outputs/review-20260924/common-confirmation20-76727-received')
    for folder,evidence,arcroot in [(source,'20261006-x20-85859-true-85861-review.json',ROOT),
        (oldhistory,'20261001-x20-82518-final-review.json',ROOT),
        (originhistory,'20261006-x20-85821-final-review.json',ROOT),
        (current,'20260929-boundary-response-review.json',ROOT),
        (accepted,'20260924-common-confirmation20-review.json',accepted.parent)]:history.source_archive(folder,evidence,arcroot)
    source_audit=read('handoff/evidence/20261006-x20-85859-true-85861-review.json')
    assert source_audit['true_maps_independently_validated'] and len(source_audit['actual']['checks'])==16 and all(source_audit['actual']['checks'].values())
    ot=read('handoff/evidence/20261006-x20-85821-terminal.json')
    assert ot['job_id']==85821 and ot['state']=='COMPLETED' and 'JobState=COMPLETED' in ot['scontrol'] and 'ExitCode=0:0' in ot['scontrol']
    source_decl=read(source/'declaration.json');full=read(source/'validation.json')['actual_maps']['full']
    expected=dict(historical=dict(path=full['output_path'],sha256=full['output_sha256'],size_bytes=10099884032))
    assert seeds==expected and read(source/'full/state.json')['history']==[full]
    source_binding(source_audit,read('handoff/evidence/20261006-x20-85821-final-review.json'),seeds,full)
    for c in d['code']:
        data=subprocess.check_output(['git','show',d['environment']['git_commit']+':'+c['path']])
        assert len(data)==c['size_bytes'] and hashlib.sha256(data).hexdigest()==c['sha256']
    assert job==85875
    assert d['prior_feedback_origins']==dict(historical='85821 historical pair16, prior to candidate acceleration')
    assert source_decl['basis'][:2]==[read(originhistory/'historical/endpoints-map16/manifest.json')['endpoints'][k] for k in ('previous','final')]
    assert prior.digest(source/'full/trial_material.npz')==prior.digest(originhistory/'historical/trial_material.npz')
    saved_summary=read(oldhistory/'summary.json')
    assert d['saved_reference']['eight_map_window']==saved_summary['cases']['accelerated']['16']['eight_map_window']
    assert d['saved_reference']['eight_map_window']['passed']
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
    exact={currentp['sources']['physical_old_time_level']['path']:physical_old,
        currentp['sources']['outer_base_material']['path']:reference/'outer_base_material.npz',
        currentp['sources']['base_residual']['path']:reference/'base_residual.npy'}
    known=source_decl['claims']+source_decl['code']+read(oldhistory/'declaration.json')['claims']+list(seeds.values())
    verified=0;external=[]
    for c in d['claims']:
        f=exact.get(c['path'],claim_path(c['path'],out))
        if f.is_file():prior.verify_claim(c,f);verified+=1
        else:
            assert c['path'].endswith('.dat') and c in known,c['path']
            external.append(c)
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
    refvec={e:arrays(oldhistory/f'accelerated/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    reffb={e:arrays(oldhistory/f'accelerated/pair16/{e}_feedback.npz') for e in ('previous','final')}
    vectors={};feedbacks={};pairs={};decisions={name:{} for name in counts};cross={};cross_details={};fbpeaks=[];localizations={}
    for name,n in entries:
        folder=out/name/f'pair{n:02d}';p=read(folder/'feedback_protocol.json');dec=read(folder/'decision.json');verify_pair(dec,name,n)
        assert p['diagnostic_scope']==dict(same_state_seed_response_windows=True,saved_reference_job=82518,reference_recomputed=False,radiation_history=name,baseline_replacement_authorized=False)
        for k in ('acceptance_gates','formal_state_gates'):assert p[k]==currentp[k]
        for k,f in [('refreshed_direction_declaration',out/'declaration.json'),('retained_manifest',out/name/f'endpoints-map{n:02d}/manifest.json')]:prior.verify_claim(p['sources'][k],f)
        for c in p['common_code_claims']:prior.verify_claim(c,Path(c['path']))
        result,vec,peaks=prior.audit_pair(out,n,reference,physical_old,trial,name,material_kind='control',max_maps=16);fbpeaks+=peaks
        assert dec['original_zero_gates']==result['gate_checks'] and dec['parent_peak_rss_bytes']<6*1024**3
        for e in vec:prior.same_record(dict(zip(cw.NAMES,cw.independent_norms(vec[e],mass).tolist())),result['endpoints'][e]['norms'])
        origin_name,origin_n=name,16
        origin={e:arrays(originhistory/f'{origin_name}/pair{origin_n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
        result['from_prior_feedback']=history.comparison(vec,origin,r20,mass,scale);prior.same_record(result['from_prior_feedback'],dec['from_prior_feedback'])
        result['within_pair_spread']=history.comparison(vec,vec,r20,mass,scale)
        vectors[name,n]=vec;feedbacks[name,n]={e:arrays(folder/f'{e}_feedback.npz') for e in vec}
        if n==16:
            result['eight_map_window']=history.comparison(vec,vectors[name,8],r20,mass,scale)
            prior.same_record(result['eight_map_window'],dec['eight_map_window'])
            localizations[name+'_window']=localization(vec['final']-vectors[name,8]['final'],mass)
        if name=='historical':
            # 两种初值的每个previous/final组合均保留，不能只挑差最小的一组。
            residual=history.comparison(vec,refvec,r20,mass,scale)
            comps={a+'_vs_'+b:prior.pair._feedback_stability_comparison(x,y) for a,x in feedbacks[name,n].items() for b,y in reffb.items()}
            rates={k:prior.pair._feedback_stability_gate_checks(v,p['acceptance_gates']) for k,v in comps.items()}
            cross[str(n)]=dict(residual_comparison=residual,all_four_rate_gate_checks=rates,cross_rate_pass=all(all(g.values()) for g in rates.values()),
                saved_reference_job=82518,saved_reference_case='accelerated',saved_reference_map=16,reference_recomputed=False,strict_error_bound=False)
            prior.same_record(cross[str(n)],dec['vs_saved_reference'])
            cross_details[str(n)]={k:{kk:vv.tolist() if isinstance(vv,np.ndarray) else vv for kk,vv in v.items()} for k,v in comps.items()}
            localizations['cross'+str(n)]=localization(vec['final']-refvec['final'],mass)
        pairs[name+str(n)]=result;decisions[name][str(n)]=dec
    terminal=terminal_path is not None;eligible=False
    execution=dict(numerical_artifacts_complete=False,child_exit_status=None,scheduler_terminal_verified=False,scheduler_terminal_state=None)
    if terminal:
        term=read(terminal_path);s=read(out/'summary.json')
        assert not (ROOT/'85875-stderr.log').read_bytes()
        execution=execution_evidence(term,read(ROOT/'85875-batch-exit.json'),s,job)
        assert 0<s['wall_s']<14400
        assert s['seed_stats_after']==d['seed_stats_before'] and s['git_commit_after']==d['git_commit']
        assert s['git_clean_after'] is True and s['all_hashes_verified_before_after'] is True
        assert s['status']==read(out/'status.json')['status']=='historical_seed_windows_complete_requires_review'
        assert s['maps']==16 and s['map_counts']==counts and s['feedback_pair_count']==2 and s['cases']==decisions
        prior.same_record(cross,s['vs_saved_reference']);assert s['reference_calibration_eligible']==eligible
        assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and s['baseline_replaced'] is False and s['strict_error_bound'] is False
        assert s['parent_peak_rss_bytes']<6*1024**3
        assert not s['reference_recomputed'] and not s['matched_new_two_branch_experiment']
    else:
        assert not (out/'summary.json').exists()
        st=read(out/'status.json');assert st['status']=='feedback' and (st['case'],st['after_maps'])==entries[-1]
    result=dict(job_id=job,archive=read(ROOT/(base+'-receipt.json')),verified_files=len(inventory['files']),verified_source_claims=verified,verified_code_claims=len(d['code']),external_claims_bound_to_prior_audits=external,source_jobs=d['source_jobs'],numerical_commit=d['environment']['git_commit'],source_85821_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,
        completed_experiment=terminal,**execution,reference_recomputed=False,matched_new_two_branch_experiment=False,map_counts=counts,maps=maps,pairs=pairs,vs_saved_reference=cross,cross_feedback_comparisons=cross_details,localization=localizations,
        map_process_receipts=len(mappeaks),feedback_process_receipts=len(fbpeaks),maximum_proc_kib=max(mappeaks+fbpeaks),boundary_reduction_roundoff=roundoff,
        all_original_zero_gates_passed=True,reference_calibration_eligible=eligible,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
        independent_vector_reduction=True,original_gate_kernels_reused=True,material_ode_recomputed_on_mac=False,large_fields_recomputed_on_mac=False,strict_error_bound=False)
    with target.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('job_id','verified_files','map_counts','map_process_receipts','feedback_process_receipts','maximum_proc_kib','reference_calibration_eligible','vs_saved_reference')},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True,type=int);p.add_argument('--base',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--target',type=Path,required=True);p.add_argument('--terminal',type=Path);a=p.parse_args()
    review(a.base,a.out,a.target,a.job,a.terminal)
