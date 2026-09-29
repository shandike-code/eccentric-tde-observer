"""Independent complete-vector and per-cell audit of diagnostic response job 80195."""
import json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_refreshed_directions as previous
from handoff.audit_tools.review_late_direction_windows import verify_prior_archive
cw=previous.cw
read,digest,arrays=previous.read,previous.digest,previous.arrays


def quadratic_ledger(candidate,control,reference,mass):
    """Algebraic norm budget; does not replace the frozen reference residual."""
    p,c,r=[cw.independent_norms(v,mass) for v in (candidate,control,reference)]
    # 恒等式拆开两种贡献，不据此把新control偷偷替换成r20。
    return dict(candidate_over_original=(p/r).tolist(),control_over_original=(c/r).tolist(),
        candidate_over_control=(p/c).tolist(),control_squared_excess_over_reference=((c/r)**2-1).tolist(),
        candidate_squared_change_from_control=((p/r)**2-(c/r)**2).tolist(),
        candidate_squared_excess_over_reference=((p/r)**2-1).tolist(),baseline_replaced=False)


def main():
    root=Path('outputs/review-20260925');out=root/'boundary-response-80195-received'
    receipt=root/'complete-1790619089081269974-receipt.json'
    manifest=cw.receive(root/'complete-1790619089081269974.tar.gz',receipt,out)
    source=root/'late-direction-79151-complete-received';rejected=root/'boundary-global-80052-received'
    reference=root/'common-step21-76808-received/inputs'
    physical_old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    accepted=Path('outputs/review-20260924/common-confirmation20-76727-received/confirm2')
    verify_prior_archive(read(Path('handoff/evidence/20260928-late-direction-complete-review.json')),source,root,79151)
    ra=read(Path('handoff/evidence/20260928-boundary-global-review.json'));c=ra['archive'];ap=root/Path(c['path']).name
    previous.verify_claim(c,ap)
    with tarfile.open(ap) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(rejected/'ARCHIVE_MANIFEST.json')
    cw.verified_inventory(rejected)
    d=read(out/'declaration.json');s=read(out/'summary.json');status=read(out/'status.json')
    assert d['source_job']==79151 and d['rejected_job']==80052 and d['accepted_outer_steps']==20
    assert d['diagnostic_only'] and d['historical_acceleration_veto_retained'] and not d['rejected_source_validated']
    assert d['rejected_source_checks']==ra['checks'] and [k for k,v in ra['checks'].items() if not v]==['prior_q_half_boundary_l1']
    assert d['coefficients']==dict(a=.4892755093069306,b=1.)
    assert d['maximum_maps']==20 and d['maximum_feedback_pairs']==4 and d['child_limits']==dict(control=10,population=10)
    assert d['cadence']==[2,10] and not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed','matched_initial_radiation'))
    assert s['status']==status['status']=='diagnostic_response_windows_complete_requires_review'
    assert s['diagnostic_only'] and s['historical_acceleration_veto_retained'] and s['maps']==20 and s['map_counts']==dict(control=10,population=10)
    assert s['accepted_outer_steps']==status['accepted_outer_steps']==20 and s['new_material_steps']==status['new_material_steps']==0
    assert not s['baseline_replaced'] and not s['strict_error_bound'] and not (out/'half').exists()
    terminal=read(Path('handoff/evidence/20260929-boundary-response-80195-terminal.json'))
    assert terminal['job_id']==80195 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='80195'
    for c in d['code']:previous.verify_claim(c,Path(c['path']))
    val=read(rejected/'population/validation.json');row=val['actual_map']
    seeds=dict(population=dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=10099884032),
        control=read(source/'control/endpoints-map08/manifest.json')['endpoints']['mapped_final'])
    assert read(out/'seed-claims.json')==seeds and d['population_seed']==seeds['population'] and d['control_seed']==seeds['control']
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    base=arrays(reference/'outer_base_material.npz');x20=arrays(accepted/'trial_material.npz')
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],x20[k])
    assert np.array_equal(r20,arrays(accepted/'common-feedback/final_response.npz')['residual'])
    origins={k:{e:arrays(source/k/f'pair08/{e}_response.npz')['residual'] for e in ('previous','final')} for k in ('control','population')}
    _,original_signals=previous.independent_signals(origins['population'],origins['control'],mass)
    zero=read(source/'control/pair08/feedback_protocol.json');maps={};peaks=[];results={};controls={};roundoff={};ledgers={}
    last_control=origins['control'];last_signals=None
    for name in ('control','population'):
        for c in d['cases'][name].values():previous.verify_claim(c,out/'inputs'/name/Path(c['path']).name)
        assert digest(out/'inputs'/name/'trial_material.npz')==digest(source/name/'trial_material.npz')==digest(out/name/'trial_material.npz')
        assert digest(out/'inputs'/name/'config.json')==digest(source/name/'config.json')
        cfg=read(out/name/'config.json');st=read(out/name/'state.json')
        assert cfg['warm_seed']==seeds[name] and cfg['workers']==16 and cfg['maximum_maps']==10 and cfg['radiation_threshold']==1e-4
        assert len(st['history'])==10 and st['history'][0]['input_sha256']==seeds[name]['sha256']
        maps[name],resources=previous.audit_maps(out,name);peaks+=resources
        for row in st['history']:
            reports=[read(out/name/f"map{row['iteration']:04d}/block{i:02d}.json") for i in range(76)]
            assert [(z['core_group_start'],z['core_group_stop']) for z in reports]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
            a,b=[math.fsum(z[k] for z in reports) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
            bol=abs(a-b)/max(abs(a),abs(b));eps=np.finfo(float).eps;gamma=76*eps/(1-76*eps)
            bound=4*gamma*math.fsum(abs(z[k]) for z in reports for k in ('current_boundary_bolometric','mapped_boundary_bolometric'))/max(abs(a),abs(b))*(1+bol)
            assert abs(bol-row['boundary_bolometric'])<=bound
            roundoff[f"{name}{row['iteration']:02d}"]=dict(fsum_bolometric=bol,reported=row['boundary_bolometric'],gamma_bound=bound)
    map_receipts=len(peaks);fb_receipts=0
    for n,name in [(n,name) for n in (2,10) for name in ('control','population')]:
        folder=out/name/f'pair{n:02d}';decision=read(folder/'decision.json');p=read(folder/'feedback_protocol.json')
        assert s['cases'][name][str(n)]==decision and decision['diagnostic_only'] and decision['historical_acceleration_veto_retained']
        assert decision['feedback_evaluated'] and not decision['promoted'] and not decision['baseline_replaced'] and not decision['physical_response_failures']
        assert decision['parent_peak_rss_bytes']<6*1024**3
        assert p['diagnostic_scope']==dict(diagnostic_only=True,historical_acceleration_veto_retained=True,automatic_promotion=False)
        for k in ('acceptance_gates','formal_state_gates'):assert p[k]==zero[k]
        for key,path in [('refreshed_direction_declaration',out/'declaration.json'),('retained_manifest',out/name/f'endpoints-map{n:02d}/manifest.json'),('rejected_seed_validation',rejected/'population/validation.json')]:
            previous.verify_claim(p['sources'][key],path)
        for c in p['common_code_claims']:previous.verify_claim(c,Path(c['path']))
        report,vectors,resources=previous.audit_pair(out,n,reference,physical_old,out/'inputs'/name/'trial_material.npz',name)
        peaks+=resources;fb_receipts+=len(resources);assert decision['original_gates']==report['gate_checks']
        if name=='control':
            window=cw.recompute_window(vectors,last_control,r20,mass);total=cw.recompute_window(vectors,origins['control'],r20,mass)
            cw.verify_window(window,decision['window_comparison']);cw.verify_window(total,decision['from_79151_control_comparison'])
            passed=all(report['gate_checks'].values()) and window['passed'] and total['passed']
            assert decision['zero_control_stable'] and decision['control_pass']==passed
            report.update(window=window,cumulative=total,control_pass=passed);controls[n]=vectors;last_control=vectors
        else:
            measure,signals=previous.independent_signals(vectors,controls[n],mass,last_signals)
            shift,_=previous.independent_signals(vectors,controls[n],mass,original_signals)
            previous.same_record(measure,decision['response_measurement']);previous.same_record(shift,decision['from_79151_signal_shift'])
            saved=arrays(folder/'direction_response_vectors.npz');assert set(saved)==set(signals) and all(np.array_equal(saved[k],signals[k]) for k in signals)
            cross=previous.independent_cross(vectors,controls[n],mass);previous.same_record(cross,decision['fresh_baseline_comparison'])
            contraction={k for k in report['gate_checks'] if k.startswith('candidate_') and k.endswith('_contraction_pass')}
            required=set(report['gate_checks'])-contraction
            assert len(contraction)==3 and len(required)==13 and sorted(required)==d['required_feedback_gates']
            failures=sorted(k for k in required if not report['gate_checks'][k]);bad=sorted(k for k in contraction if not report['gate_checks'][k])
            assert decision['diagnostic_gate_report']==dict(diagnostic_only=True,required_gate_failures=failures,contraction_gate_failures=bad,
                may_continue_diagnostic=not failures,original_all_16_pass=all(report['gate_checks'].values()),accepted_material_step=False,historical_acceleration_veto_retained=True)
            signal_pass=measure['endpoint_signal_resolved'] and (n==2 or measure['eight_map_signal_persistent'])
            passed=signal_pass and not failures;assert decision['signal_pass']==signal_pass and decision['all_16_pair_gates']==all(report['gate_checks'].values())
            assert decision['comparison_kind']==('post_correction_shift_not_persistence' if n==2 else 'eight_map_signal_persistence')
            report.update(response_measurement=measure,from_79151_signal_shift=shift,fresh_baseline_comparison=cross,contraction_failures=bad)
            ledgers[str(n)]={a+'_vs_'+b:quadratic_ledger(v,controls[n][b],r20,mass) for a,v in vectors.items() for b in controls[n]}
            last_signals=signals
        assert passed and decision['conditional_continuation_pass']==passed
        results[f'{name}{n:02d}']=report
    result=dict(job_id=80195,archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        maps=maps,pairs=results,final_summary_present=True,map_process_receipts=map_receipts,feedback_process_receipts=fb_receipts,
        maximum_proc_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,diagnostic_only=True,
        diagnostic_windows_passed=True,original_all_16_pass=False,historical_acceleration_veto_retained=True,
        baseline_replaced=False,strict_error_bound=False,quadratic_norm_ledger=ledgers,boundary_reduction_roundoff=roundoff,
        production_signal_reducer_reused=False,original_gate_kernels_reused=True,material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    target=Path('handoff/evidence/20260929-boundary-response-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained');denom=cw.independent_norms(r20,mass)
    for i,k in enumerate(cw.NAMES):
        axes[0].plot(range(4),[v['endpoints']['final']['norms'][k]/denom[i] for v in results.values()],'o-',label=k)
        axes[1].plot([2,10],[results[f'population{n:02d}']['response_measurement']['endpoint_spread_over_signal'][k] for n in (2,10)],'o-',label=k+' endpoint spread')
        axes[1].scatter([10],[results['population10']['response_measurement']['eight_map_signal_drift_over_signal'][k]],marker='x',s=70,label=k+' 8-map drift')
    axes[0].set_xticks(range(4),list(results));axes[0].axhline(1,color='black',ls='--');axes[0].set(ylabel='Residual norm / frozen r20',title='Original acceptance still fails');axes[0].legend()
    axes[1].axhline(.1,color='black',ls='--');axes[1].set(xlabel='New maps per case',ylabel='Vector difference / signal norm',title='Diagnostic signal windows pass');axes[1].legend(fontsize=8)
    fig.savefig(target.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:result[k] for k in ('job_id','verified_files','verified_code_claims','map_process_receipts','feedback_process_receipts','maximum_proc_kib','quadratic_norm_ledger')},indent=2))


if __name__=='__main__':main()
