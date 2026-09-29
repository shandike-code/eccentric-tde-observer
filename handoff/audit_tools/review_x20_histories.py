"""Independent full-vector/energy/ownership review of the 80554 history experiment."""
import json, math, tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools import review_refreshed_directions as prior
cw,read,arrays=prior.cw,prior.read,prior.arrays
ROOT=Path('outputs/review-20260925')
OUT=ROOT/'x20-history-80554-received'
BASE='complete-1790662541581257528'
TARGET=Path('handoff/evidence/20260929-x20-history-review')


def comparison(current,previous,r20,mass,scale):
    scale=np.asarray(scale)
    if scale.shape!=(3,) or not np.isfinite(scale).all() or np.any(scale<=0):raise ValueError('invalid signal scale')
    frozen=cw.recompute_window(current,previous,r20,mass)
    rows={a+'_vs_'+b:(cw.independent_norms(x-y,mass)/scale).tolist() for a,x in current.items() for b,y in previous.items()}
    passed=all(z<.1 for row in rows.values() for z in row)
    return dict(frozen_r20=frozen,vector_difference_over_frozen_80195_signal=rows,signal_tolerance=.1,
        signal_pass=passed,passed=frozen['passed'] and passed,strict_error_bound=False,baseline_replaced=False)


def localization(delta,mass):
    """Partition the squared mass norm, keeping all 128 cells and 4 components."""
    v=np.asarray(delta).reshape(128,4)
    squared=mass[:,None]*v*v/math.fsum(mass)
    total=math.fsum(squared.ravel())
    if total<=0:raise ValueError('zero diagnostic difference')
    cells=squared.sum(axis=1)/total;components=squared.sum(axis=0)/total
    return dict(mass_norm_squared=total,component_fractions=components.tolist(),
        cell_fractions=cells.tolist(),largest_cells=[dict(cell_index=int(i),fraction=float(cells[i])) for i in np.argsort(cells)[-8:][::-1]],
        cell_index_is_not_geometrical_depth=True)


def source_archive(folder,evidence,archive_root):
    a=read(Path('handoff/evidence')/evidence);c=a['archive'];arc=archive_root/Path(c['path']).name
    prior.verify_claim(c,arc)
    with tarfile.open(arc) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(folder/'ARCHIVE_MANIFEST.json')
    cw.verified_inventory(folder)


def main():
    inventory=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert inventory==read(ROOT/(BASE+'.json'))
    d=read(OUT/'declaration.json');s=read(OUT/'summary.json');terminal=read(Path('handoff/evidence/20260929-x20-history-80554-terminal.json'))
    assert terminal['job_id']==80554 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='80554'
    assert d['source_jobs']==[76727,80195,80542] and d['maximum_maps']==48 and d['maximum_feedback_pairs']==4
    assert d['child_limits']==dict(historical=24,late=24) and d['cadence']==[16,24]
    assert d['window_r20_tolerance']==.001 and d['window_signal_tolerance']==.1
    assert d['both_branches_identical_x20'] and d['first_window_cross_history_is_measurement_only']
    assert not any(d[k] for k in ('automatic_promotion','baseline_replacement_authorized','physical_dt_changed'))
    expected='stopped_at_historical_map24_eight_map_window_unresolved'
    assert s['status']==read(OUT/'status.json')['status']==expected and s['maps']==40
    assert s['map_counts']==dict(historical=24,late=16) and s['accepted_outer_steps']==20 and s['new_material_steps']==0
    assert not any(s[k] for k in ('baseline_replaced','strict_error_bound','reference_calibration_eligible'))
    assert s['historical_failures_retained'] and s['independent_review_required'] and not (OUT/'late/pair24').exists()
    for c in d['code']:prior.verify_claim(c,Path(c['path']))
    current=ROOT/'boundary-response-80195-received';accepted=Path('outputs/review-20260924/common-confirmation20-76727-received')
    source_archive(current,'20260929-boundary-response-review.json',ROOT)
    source_archive(accepted,'20260924-common-confirmation20-review.json',accepted.parent)
    reference=ROOT/'common-step21-76808-received/inputs'
    physical_old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    assert np.array_equal(r20,arrays(accepted/'confirm2/common-feedback/final_response.npz')['residual'])
    currentp=read(current/'control/pair10/feedback_protocol.json')
    hp=read(accepted/'confirm2/common-feedback/feedback_protocol.json')
    seeds=dict(historical=hp['sources']['final_radiation'],late=read(current/'control/endpoints-map10/manifest.json')['endpoints']['mapped_final'])
    assert d['seeds']==seeds==read(OUT/'seed-claims.json')
    t=arrays(OUT/'inputs/trial_material.npz');b=arrays(reference/'outer_base_material.npz');a=arrays(accepted/'confirm2/trial_material.npz')
    assert set(t)==set(b) and all(np.array_equal(t[k],b[k]) for k in t)
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(t[k],a[k])
    assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    assert prior.digest(OUT/'inputs/trial_material.npz')==prior.digest(current/'control/trial_material.npz')
    origins=dict(historical={e:arrays(accepted/f'confirm2/common-feedback/{e}_response.npz')['residual'] for e in ('previous','final')},
        late={e:arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')})
    pop={e:arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    scale=np.min([cw.independent_norms(p-c,mass) for p in pop.values() for c in origins['late'].values()],axis=0)
    np.testing.assert_allclose(scale,list(d['frozen_signal_scale'].values()),rtol=1e-12,atol=0)
    for c in d['cases']['control'].values():prior.verify_claim(c,OUT/'inputs'/Path(c['path']).name)
    assert read(OUT/'inputs/config.json')==read(current/'control/config.json')
    maps={};peaks=[];roundoff={};results={};vectors={};feedbacks={}
    for child,nmaps in s['map_counts'].items():
        cfg=read(OUT/child/'config.json');state=read(OUT/child/'state.json')
        assert cfg['warm_seed']==seeds[child] and cfg['workers']==16 and cfg['maximum_maps']==24 and cfg['radiation_threshold']==1e-4
        assert len(state['history'])==nmaps and state['history'][0]['input_sha256']==seeds[child]['sha256']
        assert prior.digest(OUT/child/'trial_material.npz')==prior.digest(OUT/'inputs/trial_material.npz')
        maps[child],resources=prior.audit_maps(OUT,child,max_maps=24);peaks+=resources
        for row in state['history']:
            rs=[read(OUT/child/f"map{row['iteration']:04d}/block{i:02d}.json") for i in range(76)]
            assert [(z['core_group_start'],z['core_group_stop']) for z in rs]==[(128*i,min(128*(i+1),9632)) for i in range(76)]
            before,after=[math.fsum(z[k] for z in rs) for k in ('current_boundary_bolometric','mapped_boundary_bolometric')]
            bol=abs(after-before)/max(abs(before),abs(after));eps=np.finfo(float).eps;gamma=76*eps/(1-76*eps)
            bound=4*gamma*math.fsum(abs(z[k]) for z in rs for k in ('current_boundary_bolometric','mapped_boundary_bolometric'))/max(abs(before),abs(after))*(1+bol)
            assert abs(bol-row['boundary_bolometric'])<=bound
            l1=math.fsum(z['boundary_spectrum_l1_numerator'] for z in rs)/max(math.fsum(z['current_boundary_absolute_scale'] for z in rs),math.fsum(z['mapped_boundary_absolute_scale'] for z in rs))
            np.testing.assert_allclose(l1,row['boundary_l1'],rtol=4*gamma,atol=0)
            roundoff[f"{child}{row['iteration']:02d}"]=dict(fsum_bolometric=bol,reported=row['boundary_bolometric'],roundoff_bound=bound)
    map_receipts=len(peaks)
    for child,n in [('historical',16),('late',16),('historical',24)]:
        folder=OUT/child/f'pair{n:02d}';p=read(folder/'feedback_protocol.json');dec=read(folder/'decision.json')
        assert s['cases'][child][str(n)]==dec and dec['feedback_evaluated'] and dec['zero_pair_stable']
        assert not dec['physical_response_failures'] and not dec['baseline_replaced'] and not dec['accepted_material_step']
        assert p['diagnostic_scope']==dict(same_state_history_calibration=True,radiation_history=child,baseline_replacement_authorized=False)
        for k in ('acceptance_gates','formal_state_gates'):assert p[k]==currentp[k]
        for k,path in [('refreshed_direction_declaration',OUT/'declaration.json'),('retained_manifest',OUT/child/f'endpoints-map{n:02d}/manifest.json')]:prior.verify_claim(p['sources'][k],path)
        for c in p['common_code_claims']:prior.verify_claim(c,Path(c['path']))
        report,vec,resources=prior.audit_pair(OUT,n,reference,physical_old,OUT/'inputs/trial_material.npz',child,material_kind='control',max_maps=24)
        assert dec['original_zero_gates']==report['gate_checks'];peaks+=resources
        assert dec['parent_peak_rss_bytes']<6*1024**3
        for e in vec:np.testing.assert_allclose(cw.independent_norms(vec[e],mass),[report['endpoints'][e]['norms'][k] for k in cw.NAMES],rtol=1e-12,atol=0)
        own=comparison(vec,origins[child],r20,mass,scale);prior.same_record(own,dec['from_own_source'])
        report['from_own_source']=own;vectors[child,n]=vec;feedbacks[child,n]={e:arrays(folder/f'{e}_feedback.npz') for e in vec}
        if n==24:
            window=comparison(vec,vectors[child,16],r20,mass,scale);prior.same_record(window,dec['eight_map_window'])
            assert not window['passed'] and not dec['continuation_pass'] and dec['reason']=='eight_map_window_unresolved'
            report['eight_map_window']=window
        else:assert dec['continuation_pass'] and dec['reason']=='pass'
        results[f'{child}{n}']=report
    cross=comparison(vectors['late',16],vectors['historical',16],r20,mass,scale)
    cross_rates={a+'_vs_'+b:prior.pair._feedback_stability_gate_checks(prior.pair._feedback_stability_comparison(x,y),currentp['acceptance_gates']) for a,x in feedbacks['late',16].items() for b,y in feedbacks['historical',16].items()}
    row=dict(residual_comparison=cross,all_four_rate_gate_checks=cross_rates,cross_rate_pass=all(all(g.values()) for g in cross_rates.values()))
    prior.same_record(row,s['cross_history']['16']);prior.same_record(row,read(OUT/'late/pair16/decision.json')['cross_history'])
    assert set(s['cross_history'])=={'16'} and not cross['passed']
    extra=comparison(vectors['late',16],vectors['historical',24],r20,mass,scale)
    components={k:localization(v,mass) for k,v in dict(historical_window=vectors['historical',24]['final']-vectors['historical',16]['final'],
        cross_history16=vectors['late',16]['final']-vectors['historical',16]['final'],
        cross_history_unequal24_16=vectors['late',16]['final']-vectors['historical',24]['final']).items()}
    result=dict(job_id=80554,archive=read(ROOT/(BASE+'-receipt.json')),verified_files=len(inventory['files']),verified_code_claims=len(d['code']),
        status=expected,maps=maps,pairs=results,cross_history16=row,unequal_age_cross_24_16=extra,localization=components,
        map_process_receipts=map_receipts,feedback_process_receipts=len(peaks)-map_receipts,maximum_proc_kib=max(peaks),
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,reference_calibration_eligible=False,
        frozen_signal_scale=dict(zip(cw.NAMES,scale.tolist())),physical_state_x20_unchanged=True,all_zero_pair_gates_passed=True,
        independent_vector_reduction=True,original_gate_kernels_reused=True,material_ode_recomputed_on_mac=False,
        full_large_fields_recomputed_on_mac=False,boundary_reduction_roundoff=roundoff)
    TARGET.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for child,rows in maps.items():axes[0].semilogy([r['iteration'] for r in rows],[r['residual'] for r in rows],'.-',label=child)
    axes[0].axhline(1e-4,color='k',ls='--');axes[0].set(xlabel='New maps per history',ylabel='Original radiation map residual');axes[0].legend()
    comparisons=[results['historical24']['eight_map_window'],cross,extra]
    for i,k in enumerate(cw.NAMES):axes[1].plot(range(3),[max(x[i] for x in c['frozen_r20']['vector_difference_over_frozen_r20_norms'].values()) for c in comparisons],'o-',label=k)
    axes[1].set_yscale('log');axes[1].axhline(.001,color='k',ls='--');axes[1].set_xticks(range(3),['H24-H16','L16-H16','L16-H24\nunequal ages']);axes[1].set_ylabel('Full response-vector difference / frozen r20');axes[1].legend()
    fig.savefig(TARGET.with_suffix('.png'),dpi=150);plt.close(fig)
    print(json.dumps({k:result[k] for k in ('job_id','verified_files','verified_code_claims','map_process_receipts','feedback_process_receipts','maximum_proc_kib','status')},indent=2))

if __name__=='__main__':main()
