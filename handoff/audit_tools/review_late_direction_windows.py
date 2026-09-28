"""Independent late-window reductions and archive audit; no production reducer."""
import argparse
import json
from pathlib import Path
import tarfile
import numpy as np
from handoff.audit_tools import review_refreshed_directions as previous

cw=previous.cw
read,digest,arrays=previous.read,previous.digest,previous.arrays
NAMES=previous.NAMES


def verify_plan(d,seeds):
    assert d['source_job']==78950 and d['source']=='outputs/hpc/step21-refreshed-directions-20260928'
    assert d['seeds']==seeds and d['maximum_maps']==48 and d['maximum_feedback_pairs']==6
    assert d['limits']==dict.fromkeys(NAMES,16) and d['cadence']==[8,16]
    assert d['source_maps_per_case']==16 and d['absolute_feedback_maps']==[24,32]
    assert d['case_order']==list(NAMES) and set(d['cases'])==set(NAMES)
    assert d['amplitudes']==dict(control=0.,thermal=1/256,population=1/256)
    assert d['control_window_tolerance']==.001 and d['signal_tolerance']==.1
    assert d['cumulative_anchor']=='78950 map16' and d['accepted_outer_steps']==20
    assert all(d[k] is True for k in ('own_successor_continuation','stop_on_first_failed_late_window',
        'historical_78594_drift_reported','old_8_to_16_verdicts_retained'))
    assert all(d[k] is False for k in ('matched_initial_radiation','historical_78594_gate_controls_dispatch',
        'automatic_promotion','baseline_replacement_authorized','physical_dt_changed','strict_error_bound'))


def control_metrics(vectors,last,origin,historical,r20,mass,stable):
    # 先独立计算三段完整向量漂移；历史超门不被新窗口覆盖。
    w=cw.recompute_window(vectors,last,r20,mass)
    total=cw.recompute_window(vectors,origin,r20,mass)
    history=cw.recompute_window(vectors,historical,r20,mass)
    return dict(window=w,cumulative=total,historical=history,
        control_pass=bool(stable and w['passed'] and total['passed']),
        historical_78594_cumulative_pass=history['passed'],
        original_78594_cumulative_stability_claim=bool(stable and history['passed']))


def direction_metrics(vectors,control,mass,last,origin):
    w,signals=previous.independent_signals(vectors,control,mass,last)
    total,_=previous.independent_signals(vectors,control,mass,origin)
    passed=all(v['endpoint_signal_resolved'] and v['eight_map_signal_persistent'] for v in (w,total))
    return dict(response_measurement=w,from_78950_map16_signal=total,late_direction_pass=passed),signals


def verify_schedule(events,passes,complete,status):
    expected=[(n,k) for n in (8,16) for k in NAMES]
    assert events and events==expected[:len(events)] and len(passes)==len(events)
    assert all(passes[:-1]),'work continued after an earlier failed late window'
    if complete:
        if all(passes):assert events==expected and status=='late_direction_windows_complete_requires_review'
        else:
            n,k=events[-1]
            assert status in (f'stopped_at_{k}_map{n:02d}_late_window_not_confirmed',
                              f'stopped_at_{k}_map{n:02d}_inner_not_ready')


def verify_prior_archive(audit,source,archive_parent,job):
    assert audit['job_id']==job and audit['final_summary_present']
    path=archive_parent/Path(audit['archive']['path']).name
    previous.verify_claim(audit['archive'],path)
    with tarfile.open(path) as tar:
        assert json.load(tar.extractfile('ARCHIVE_MANIFEST.json'))==read(source/'ARCHIVE_MANIFEST.json')
    cw.verified_inventory(source)


def review(archive,receipt,received,source,historical,reference,physical_old,accepted,output,terminal=None):
    manifest=cw.receive(archive,receipt,received);out=received;d=read(out/'declaration.json')
    source_audit=read(Path('handoff/evidence/20260928-refreshed-directions-complete-review.json'))
    verify_prior_archive(source_audit,source,archive.parent,78950)
    history_audit=read(Path('handoff/evidence/20260928-stationarity-complete-review.json'))
    verify_prior_archive(history_audit,historical,archive.parent,78594)
    seeds={k:read(source/k/'endpoints-map16/manifest.json')['endpoints']['mapped_final'] for k in NAMES}
    verify_plan(d,seeds)
    status=read(out/'status.json');assert status['accepted_outer_steps']==20 and status['new_material_steps']==0
    for claim in d['code']:previous.verify_claim(claim,Path(claim['path']))
    old=arrays(physical_old);mass=old['cell_mass_g_cm2'];r20=np.load(reference/'base_residual.npy',allow_pickle=False)
    base=arrays(reference/'outer_base_material.npz');x20=arrays(accepted/'trial_material.npz')
    for k in ('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(base[k],x20[k])
    assert np.array_equal(r20,arrays(accepted/'common-feedback/final_response.npz')['residual'])
    zero=read(source/'control/pair16/feedback_protocol.json')
    origins={k:{e:arrays(source/k/f'pair16/{e}_response.npz')['residual'] for e in ('previous','final')} for k in NAMES}
    historical_vectors={e:arrays(historical/f'control/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    origin_signals={k:previous.independent_signals(origins[k],origins['control'],mass)[1] for k in NAMES[1:]}
    last_signals=origin_signals.copy();last_control=origins['control']
    controls={};maps={};peaks=[];results={};events=[];passes=[];fb_receipts=0
    for k in NAMES:
        for claim in d['cases'][k].values():previous.verify_claim(claim,out/'inputs'/k/Path(claim['path']).name)
        assert digest(out/'inputs'/k/'trial_material.npz')==digest(source/k/'trial_material.npz')
        assert digest(out/'inputs'/k/'config.json')==digest(source/k/'config.json')
        if not (out/k/'state.json').exists():continue
        cfg=read(out/k/'config.json');state=read(out/k/'state.json')
        assert cfg['warm_seed']==seeds[k] and cfg['workers']==16 and cfg['maximum_maps']==16 and cfg['radiation_threshold']==1e-4
        assert state['history'][0]['input_sha256']==seeds[k]['sha256']
        assert digest(out/k/'trial_material.npz')==digest(out/'inputs'/k/'trial_material.npz')
        maps[k],resources=previous.audit_maps(out,k);peaks+=resources
    map_receipts=len(peaks)
    for n,k in [(n,k) for n in (8,16) for k in NAMES]:
        folder=out/k/f'pair{n:02d}';dp=folder/'decision.json';missing=out/k/f'inner-not-ready-map{n:02d}.json'
        if not dp.exists():
            if missing.exists():
                row=read(missing);assert row==dict(feedback_evaluated=False,inner_pair_ready=False,promoted=False)
                rows=read(out/k/'state.json')['history'][n-2:n];assert len(rows)==2
                assert not all(v['residual']<1e-4 and v['boundary_l1']<1e-3 and v['boundary_bolometric']<1e-3 for v in rows)
                results[f'{k}{n:02d}']=row;events.append((n,k));passes.append(False)
            continue
        decision=read(dp);p=read(folder/'feedback_protocol.json')
        assert decision['absolute_maps']==16+n and decision['feedback_evaluated']
        assert not decision['promoted'] and not decision['baseline_replaced']
        assert not decision['physical_response_failures'],'physical-domain failure needs dedicated audit'
        assert decision['parent_peak_rss_bytes']<6*1024**3
        for key in ('acceptance_gates','formal_state_gates'):assert p[key]==zero[key]
        for key,path in [('late_direction_declaration',out/'declaration.json'),('refreshed_direction_declaration',out/'declaration.json'),
                         ('retained_manifest',out/k/f'endpoints-map{n:02d}/manifest.json')]:
            previous.verify_claim(p['sources'][key],path)
        for claim in p['common_code_claims']:previous.verify_claim(claim,Path(claim['path']))
        report,vectors,resources=previous.audit_pair(out,n,reference,physical_old,out/'inputs'/k/'trial_material.npz',k)
        peaks+=resources;fb_receipts+=len(resources)
        assert decision['original_gates']==report['gate_checks']
        if k=='control':
            stable=all(report['gate_checks'].values());assert decision['zero_control_stable']==stable
            data=control_metrics(vectors,last_control,origins['control'],historical_vectors,r20,mass,stable)
            for actual,saved in [('window','window_comparison'),('cumulative','from_78950_map16_comparison'),('historical','from_78594_comparison')]:
                cw.verify_window(data[actual],decision[saved])
            for key in ('control_pass','historical_78594_cumulative_pass','original_78594_cumulative_stability_claim'):assert data[key]==decision[key]
            passed=data['control_pass'];controls[n]=vectors;last_control=vectors
        else:
            data,signals=direction_metrics(vectors,controls[n],mass,last_signals[k],origin_signals[k])
            for key in data:previous.same_record(data[key],decision[key])
            saved=arrays(folder/'direction_response_vectors.npz')
            assert set(saved)==set(signals) and all(np.array_equal(saved[key],signals[key]) for key in signals)
            cross=previous.independent_cross(vectors,controls[n],mass);previous.same_record(cross,decision['fresh_baseline_comparison'])
            data['fresh_baseline_comparison']=cross
            assert decision['all_16_pair_gates']==all(report['gate_checks'].values())
            passed=data['late_direction_pass'];last_signals[k]=signals
        report.update(data);results[f'{k}{n:02d}']=report;events.append((n,k));passes.append(passed)
    complete=(out/'summary.json').exists();job=int(d['environment']['scheduler']['SLURM_JOB_ID'])
    verify_schedule(events,passes,complete,status['status'])
    if complete:
        assert terminal is not None;term=read(terminal)
        assert term['job_id']==job and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        summary=read(out/'summary.json');assert summary['status']==status['status']
        assert summary['maps']==sum(len(v) for v in maps.values())<=48
        assert summary['accepted_outer_steps']==20 and summary['new_material_steps']==0
        assert summary['late_windows_only'] and summary['old_8_to_16_verdicts_retained']
        assert not summary['baseline_replaced'] and not summary['strict_error_bound']
        for n,k in events:
            f=out/k/f'pair{n:02d}/decision.json'
            assert summary['cases'][k][str(n)]==read(f if f.exists() else out/k/f'inner-not-ready-map{n:02d}.json')
        expected_counts={}
        for n,k in events:expected_counts[k]=n
        assert {k:len(v) for k,v in maps.items()}==expected_counts,'extra maps beyond the declared stop'
    result=dict(job_id=job,archive=read(receipt),verified_files=len(manifest['files']),verified_code_claims=len(d['code']),
        maps=maps,pairs=results,events=events,final_summary_present=complete,map_process_receipts=map_receipts,
        feedback_process_receipts=fb_receipts,maximum_proc_kib=max(peaks),accepted_outer_steps=20,new_material_steps=0,
        baseline_replaced=False,strict_error_bound=False,late_windows_only=True,old_8_to_16_verdicts_retained=True,
        production_signal_reducer_reused=False,original_gate_kernels_reused=True,
        material_ode_recomputed_on_mac=False,full_large_fields_recomputed_on_mac=False)
    output.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    denom=cw.independent_norms(r20,mass)
    for i,metric in enumerate(cw.NAMES):
        ax.plot(range(len(results)),[v['endpoints']['final']['norms'][metric]/denom[i] if 'endpoints' in v else np.nan for v in results.values()],'o-',label=metric)
    ax.set_xticks(range(len(results)),list(results));ax.axhline(1,color='black',ls='--')
    ax.set(ylabel='Residual norm / original r20 norm',title='Late windows only; no material promotion');ax.legend()
    fig.savefig(output.with_suffix('.png'),dpi=150);plt.close(fig)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('archive','receipt','received','source','historical','reference','physical-old','accepted','output'):
        p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--terminal',type=Path)
    r=review(**vars(p.parse_args()))
    print(json.dumps({k:r[k] for k in ('job_id','verified_files','events','map_process_receipts','feedback_process_receipts','maximum_proc_kib')},indent=2))
