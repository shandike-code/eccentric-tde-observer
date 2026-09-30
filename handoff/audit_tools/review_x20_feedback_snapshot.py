"""Audit immutable multi-pair snapshots of 81769, with explicit partial/terminal scope."""
import argparse,json
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_x20_accelerated_pair08 as first
history,prior,cw,read,arrays=first.history,first.prior,first.cw,first.read,first.arrays
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


def review(base,out,target,terminal_path=None):
    inventory=cw.receive(ROOT/(base+'.tar.gz'),ROOT/(base+'-receipt.json'),out)
    assert inventory==read(ROOT/(base+'.json'))
    history.source_archive(first.OUT,'20260930-x20-81769-accelerated08-review.json',ROOT)
    d=read(out/'declaration.json');seeds=read(out/'seed-claims.json');first.verify_plan(d,seeds)
    for f in ('declaration.json','seed-claims.json','source-preflight/declaration.json','source-preflight/inputs/trial_material.npz','source-preflight/inputs/config.json'):
        assert prior.digest(out/f)==prior.digest(first.OUT/f),f
    for c in d['code']+read(out/'source-preflight/declaration.json')['code']:prior.verify_claim(c,Path(c['path']))
    reference=ROOT/'common-step21-76808-received/inputs';physical_old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    current=ROOT/'boundary-response-80195-received';oldhistory=ROOT/'x20-history-80554-received';trial=out/'source-preflight/inputs/trial_material.npz'
    history.source_archive(current,'20260929-boundary-response-review.json',ROOT);history.source_archive(oldhistory,'20260929-x20-history-review.json',ROOT)
    currentp=read(current/'control/pair10/feedback_protocol.json')
    control={e:arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    pop={e:arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    scale=np.min([cw.independent_norms(p-c,mass) for p in pop.values() for c in control.values()],axis=0)
    np.testing.assert_allclose(scale,[d['frozen_signal_scale'][k] for k in cw.NAMES],rtol=1e-12,atol=0)
    maps={};mappeaks=[];counts={};roundoff={};states={};configs={}
    for name in ('accelerated','historical'):
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
    assert {k:v for k,v in configs['accelerated'].items() if k not in ignore}=={k:v for k,v in configs['historical'].items() if k not in ignore}
    entries=[(name,n) for name,n in ORDER if (out/name/f'pair{n:02d}/decision.json').exists()]
    assert len(entries)>=2 and entries==ORDER[:len(entries)]
    assert counts==dict(accelerated=max(n for name,n in entries if name=='accelerated'),historical=max(n for name,n in entries if name=='historical'))
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
        origin_name,origin_n=('late',16) if name=='accelerated' else ('historical',24)
        origin={e:arrays(oldhistory/f'{origin_name}/pair{origin_n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
        result['from_prior_feedback']=history.comparison(vec,origin,r20,mass,scale);prior.same_record(result['from_prior_feedback'],dec['from_prior_feedback'])
        result['within_pair_spread']=history.comparison(vec,vec,r20,mass,scale)
        vectors[name,n]=vec;feedbacks[name,n]={e:arrays(folder/f'{e}_feedback.npz') for e in vec}
        if n==16:
            result['eight_map_window']=history.comparison(vec,vectors[name,8],r20,mass,scale)
            prior.same_record(result['eight_map_window'],dec['eight_map_window'])
            localizations[name+'_window']=history.localization(vec['final']-vectors[name,8]['final'],mass)
        if name=='historical':
            # 两种初值的每个previous/final组合均保留，不能只挑差最小的一组。
            residual=history.comparison(vec,vectors['accelerated',n],r20,mass,scale)
            comps={a+'_vs_'+b:prior.pair._feedback_stability_comparison(x,y) for a,x in feedbacks[name,n].items() for b,y in feedbacks['accelerated',n].items()}
            rates={k:prior.pair._feedback_stability_gate_checks(v,p['acceptance_gates']) for k,v in comps.items()}
            cross[str(n)]=dict(residual_comparison=residual,all_four_rate_gate_checks=rates,cross_rate_pass=all(all(g.values()) for g in rates.values()))
            prior.same_record(cross[str(n)],dec['cross_history'])
            cross_details[str(n)]={k:{kk:vv.tolist() if isinstance(vv,np.ndarray) else vv for kk,vv in v.items()} for k,v in comps.items()}
            localizations['cross'+str(n)]=history.localization(vec['final']-vectors['accelerated',n]['final'],mass)
        pairs[name+str(n)]=result;decisions[name][str(n)]=dec
    terminal=terminal_path is not None;eligible=qualification(pairs,cross,terminal)
    if terminal:
        term=read(terminal_path);s=read(out/'summary.json');assert term['job_id']==81769 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        assert s['status']==read(out/'status.json')['status']=='paired_seed_windows_complete_requires_review'
        assert s['maps']==32 and s['map_counts']==counts and s['feedback_pair_count']==4 and s['cases']==decisions
        prior.same_record(cross,s['cross_history']);assert s['reference_calibration_eligible']==eligible
        assert s['accepted_outer_steps']==20 and s['new_material_steps']==0 and s['baseline_replaced'] is False and s['strict_error_bound'] is False
        assert s['parent_peak_rss_bytes']<6*1024**3
    else:
        assert not (out/'summary.json').exists()
        st=read(out/'status.json');assert st['status']=='feedback' and (st['case'],st['after_maps'])==entries[-1]
    result=dict(job_id=81769,archive=read(ROOT/(base+'-receipt.json')),verified_files=len(inventory['files']),source_declaration_and_inputs_identical_to_first_audited_snapshot=True,
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
