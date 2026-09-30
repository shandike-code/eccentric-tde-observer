"""Independent first-pair audit for ongoing 81769; no window or eligibility verdict."""
import json,math
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_x20_histories as history
prior,cw,read,arrays=history.prior,history.cw,history.read,history.arrays
ROOT=Path('outputs/review-20260925')
OUT=ROOT/'x20-feedback-81769-accelerated08-received'
BASE='accelerated-map08-feedback-1790738511205873976'
TARGET=Path('handoff/evidence/20260930-x20-81769-accelerated08-review.json')


def verify_plan(d,seeds):
    assert d['maximum_maps']==32 and d['maximum_feedback_pairs']==4
    assert d['cadence']==[8,16] and d['child_limits']==dict(accelerated=16,historical=16)
    assert d['case_order']==['accelerated','historical'] and d['seeds']==seeds
    assert d['accepted_outer_steps']==20 and d['new_material_steps']==0
    assert d['source_jobs']==[76727,80195,80554,81679]
    assert d['window_r20_tolerance']==.001 and d['window_signal_tolerance']==.1
    assert d['first_window_cross_history_is_measurement_only'] and d['drift_failure_does_not_skip_other_matched_case']
    assert d['both_branches_identical_x20'] and d['historical_failures_retained']
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))


def verify_pair_scope(dec):
    assert dec['feedback_evaluated'] and dec['zero_pair_stable']
    assert not dec['physical_response_failures'] and not dec['baseline_replaced'] and not dec['accepted_material_step']
    assert len(dec['original_zero_gates'])==7 and all(dec['original_zero_gates'].values())
    assert dec['continuation_pass'] and dec['reason']=='pass'
    assert 'eight_map_window' not in dec and 'cross_history' not in dec
    # 与旧late16反馈的差不是本轮16-8窗口；其失败不应被冒充为本轮终止/通过。
    assert dec['from_prior_feedback']['baseline_replaced'] is False


def boundary_check(out,child,rows):
    results={};eps=np.finfo(float).eps;gamma=76*eps/(1-76*eps)
    for row in rows:
        bs=[read(out/child/f"map{row['iteration']:04d}/block{i:02d}.json") for i in range(76)]
        assert [(b['core_group_start'],b['core_group_stop']) for b in bs]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
        before,after=[math.fsum(b[k] for b in bs) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
        den=max(abs(before),abs(after));assert den>0
        bol=abs(after-before)/den
        bound=4*gamma*math.fsum(abs(b[k]) for b in bs for k in ('current_boundary_bolometric','mapped_boundary_bolometric'))/den*(1+bol)
        assert abs(bol-row['boundary_bolometric'])<=bound
        l1=math.fsum(b['boundary_spectrum_l1_numerator'] for b in bs)/max(math.fsum(b['current_boundary_absolute_scale'] for b in bs),math.fsum(b['mapped_boundary_absolute_scale'] for b in bs))
        np.testing.assert_allclose(l1,row['boundary_l1'],rtol=4*gamma,atol=0)
        results[str(row['iteration'])]=dict(fsum_bolometric=bol,reported=row['boundary_bolometric'],roundoff_bound=bound)
    return results


def main():
    inventory=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert inventory==read(ROOT/(BASE+'.json'))
    d=read(OUT/'declaration.json');pre=read(OUT/'source-preflight/declaration.json')
    assert read(OUT/'status.json')['status']=='feedback' and not (OUT/'summary.json').exists()
    assert not (OUT/'historical').exists() # 本归档只冻结首对完成时的快照，不读仍在写的远端目录。
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='81769'
    assert d['environment']['scheduler']['SLURM_CPUS_PER_TASK']=='32' and d['environment']['scheduler']['SLURM_MEM_PER_NODE']=='131072'
    source=ROOT/'x20-expanded-81679-received';oldhistory=ROOT/'x20-history-80554-received'
    current=ROOT/'boundary-response-80195-received';accepted=Path('outputs/review-20260924/common-confirmation20-76727-received')
    for folder,evidence in [(source,'20260930-x20-expanded-validation-review.json'),(oldhistory,'20260929-x20-history-review.json'),(current,'20260929-boundary-response-review.json')]:history.source_archive(folder,evidence,ROOT)
    history.source_archive(accepted,'20260924-common-confirmation20-review.json',accepted.parent)
    full=read(source/'validation.json')['actual_maps']['full']
    seeds=dict(accelerated=dict(path=full['output_path'],sha256=full['output_sha256'],size_bytes=10099884032),historical=read(oldhistory/'historical/endpoints-map24/manifest.json')['endpoints']['mapped_final'])
    verify_plan(d,seeds);assert read(OUT/'seed-claims.json')==seeds
    for c in d['code']+pre['code']:prior.verify_claim(c,Path(c['path']))
    reference=ROOT/'common-step21-76808-received/inputs';physical_old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    assert np.array_equal(r20,arrays(accepted/'confirm2/common-feedback/final_response.npz')['residual'])
    trial=OUT/'source-preflight/inputs/trial_material.npz';t=arrays(trial);b=arrays(reference/'outer_base_material.npz')
    assert set(t)==set(b) and all(np.array_equal(t[k],b[k]) for k in t)
    assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    assert prior.digest(trial)==prior.digest(source/'full/trial_material.npz')==prior.digest(oldhistory/'late/trial_material.npz')
    for c in d['cases']['control'].values():prior.verify_claim(c,trial.parent/Path(c['path']).name)
    assert read(trial.parent/'config.json')==read(oldhistory/'late/config.json')
    p=read(OUT/'accelerated/pair08/feedback_protocol.json');currentp=read(current/'control/pair10/feedback_protocol.json')
    assert p['diagnostic_scope']==dict(same_state_seed_response_windows=True,radiation_history='accelerated',baseline_replacement_authorized=False)
    for k in ('acceptance_gates','formal_state_gates'):assert p[k]==currentp[k]
    for k,f in [('refreshed_direction_declaration',OUT/'declaration.json'),('retained_manifest',OUT/'accelerated/endpoints-map08/manifest.json')]:prior.verify_claim(p['sources'][k],f)
    for c in p['common_code_claims']:prior.verify_claim(c,Path(c['path']))
    # 消费的非大态输入逐字节复核；外部大态仅绑定到已审计来源及本轮batch回执。
    prefixes={'outputs/hpc/x20-accelerated-feedback-windows-20260930/':OUT,'outputs/hpc/x20-expanded-validation-20260930/':source,'outputs/hpc/x20-radiation-history-calibration-20260929/':oldhistory,'outputs/hpc/step21-boundary-seed-response-20260929/':current,'outputs/hpc/common-confirmation20-20260924/':accepted}
    exact={p['sources']['physical_old_time_level']['path']:physical_old,p['sources']['outer_base_material']['path']:reference/'outer_base_material.npz',p['sources']['base_residual']['path']:reference/'base_residual.npy'}
    known=read(oldhistory/'declaration.json')['claims']+read(source/'declaration.json')['claims']+list(seeds.values())
    external=[];verified=0
    for c in d['claims']:
        f=exact.get(c['path'],Path(c['path']))
        for prefix,folder in prefixes.items():
            if c['path'].startswith(prefix):f=folder/c['path'][len(prefix):];break
        if '/archives/' in c['path']:f=ROOT/Path(c['path']).name
        if f.is_file():prior.verify_claim(c,f);verified+=1
        else:assert c in known,c['path'];external.append(c)
    cfg=read(OUT/'accelerated/config.json');state=read(OUT/'accelerated/state.json');native=read(OUT/'accelerated/native_trial_audit.json')
    assert cfg['warm_seed']==seeds['accelerated'] and cfg['workers']==16 and cfg['maximum_maps']==16 and cfg['radiation_threshold']==1e-4
    assert len(state['history'])==8 and state['active_map'] is None and state['history'][0]['input_sha256']==seeds['accelerated']['sha256']
    assert state['current_sha256']==state['history'][-1]['output_sha256'] and state['trial_sha256']==prior.digest(trial)
    prior.verify_claim(native['trial_source'],OUT/'accelerated/trial_material.npz')
    assert native['native_mirrored_material_exact'] and native['physical_phase_and_dt_exact']
    assert read(OUT/'accelerated/initialized_identity.json')['native']==native
    maps,mappeaks=prior.audit_maps(OUT,'accelerated',max_maps=16);roundoff=boundary_check(OUT,'accelerated',state['history'])
    report,vec,peaks=prior.audit_pair(OUT,8,reference,physical_old,trial,'accelerated',material_kind='control',max_maps=16)
    dec=read(OUT/'accelerated/pair08/decision.json');verify_pair_scope(dec);assert dec['original_zero_gates']==report['gate_checks']
    assert dec['parent_peak_rss_bytes']<6*1024**3
    control={e:arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    pop={e:arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    scale=np.min([cw.independent_norms(x-y,mass) for x in pop.values() for y in control.values()],axis=0)
    np.testing.assert_allclose(scale,[d['frozen_signal_scale'][k] for k in cw.NAMES],rtol=1e-12,atol=0)
    origin={e:arrays(oldhistory/f'late/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    own=history.comparison(vec,origin,r20,mass,scale);prior.same_record(own,dec['from_prior_feedback'])
    norms={e:dict(zip(cw.NAMES,cw.independent_norms(v,mass).tolist())) for e,v in vec.items()}
    for e in vec:prior.same_record(norms[e],report['endpoints'][e]['norms'])
    result=dict(job_id=81769,scope='accelerated pair08 only; ongoing experiment',archive=read(ROOT/(BASE+'-receipt.json')),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),verified_source_claims=verified,external_claims_bound_to_prior_audits=external,
        maps=maps,pair=report,from_prior_feedback=own,independent_response_norms=norms,within_pair_spread=history.comparison(vec,vec,r20,mass,scale),
        map_process_receipts=len(mappeaks),feedback_process_receipts=len(peaks),maximum_proc_kib=max(mappeaks+peaks),parent_peak_rss_bytes=dec['parent_peak_rss_bytes'],boundary_reduction_roundoff=roundoff,
        all_zero_pair_gates_passed=True,physical_state_x20_unchanged=True,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
        reference_calibration_eligible=None,eight_map_window_evaluated=False,cross_seed_comparison_evaluated=False,independent_vector_reduction=True,original_gate_kernels_reused=True,
        material_ode_recomputed_on_mac=False,large_fields_recomputed_on_mac=False,strict_error_bound=False)
    TARGET.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ['job_id','verified_files','verified_source_claims','map_process_receipts','feedback_process_receipts','maximum_proc_kib','pair','independent_response_norms','from_prior_feedback']},indent=2))


if __name__=='__main__':main()
